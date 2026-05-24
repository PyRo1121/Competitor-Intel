#!/usr/bin/env python3
"""Apply Hermes enrich_results.jsonl to intelligence_events (validated)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from ci_paths import ensure_app_paths

ensure_app_paths()

from db.connection import get_conn  # noqa: E402

logger = logging.getLogger("enrich_queue_apply")

ALLOWED_TYPES = frozenset(
    {
        "Funding Round",
        "Product Launch",
        "Partnership",
        "Acquisition",
        "Hiring",
        "Research Publication",
        "General News",
        "Unlabeled Signal",
    }
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--in-dir",
        type=Path,
        default=ROOT / "data" / "hermes_enrich",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    results_path = args.in_dir / "enrich_results.jsonl"
    if not results_path.is_file():
        logger.error("Missing %s — run Hermes on enrich_queue.jsonl first", results_path)
        return 1

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM companies")
    valid_ids = {r[0] for r in cur.fetchall()}

    applied = 0
    skipped = 0
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        eid = row.get("event_id")
        etype = row.get("event_type")
        cid = row.get("company_id")
        if not isinstance(eid, int):
            skipped += 1
            continue
        if etype not in ALLOWED_TYPES:
            skipped += 1
            continue
        if cid is not None and cid not in valid_ids:
            skipped += 1
            continue
        if args.dry_run:
            applied += 1
            continue
        # 6-G01: relabel only — do not inflate confidence on Hermes/LLM apply.
        cur.execute(
            """
            UPDATE intelligence_events
            SET event_type = ?, company_id = COALESCE(?, company_id),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (etype, cid, eid),
        )
        if cur.rowcount:
            applied += 1
        else:
            skipped += 1

    if not args.dry_run:
        conn.commit()
    conn.close()
    logger.info("Applied %d, skipped %d (dry_run=%s)", applied, skipped, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
