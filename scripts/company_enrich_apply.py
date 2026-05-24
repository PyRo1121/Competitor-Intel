#!/usr/bin/env python3
"""Apply company_enrich_results.jsonl to company_profile_claims."""

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

logger = logging.getLogger("company_enrich_apply")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", type=Path, default=ROOT / "data" / "hermes_enrich")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    results_path = args.in_dir / "company_enrich_results.jsonl"
    if not results_path.is_file():
        logger.error("Missing %s", results_path)
        return 1

    conn = get_conn()
    cur = conn.cursor()
    applied = 0
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        claim_id = raw.get("claim_id")
        if not isinstance(claim_id, int):
            continue
        field_value = raw.get("field_value") or raw.get("value")
        field_key = raw.get("field_key")
        if not field_value and not field_key:
            continue
        if args.dry_run:
            applied += 1
            continue
        sets = []
        params: list[object] = []
        if field_value:
            sets.append("field_value = ?")
            params.append(str(field_value)[:2000])
        if field_key:
            sets.append("field_key = ?")
            params.append(str(field_key)[:128])
        if raw.get("headline"):
            sets.append("headline = ?")
            params.append(str(raw["headline"])[:500])
        if sets:
            params.append(claim_id)
            cur.execute(
                f"UPDATE company_profile_claims SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            applied += cur.rowcount

    if not args.dry_run:
        conn.commit()
    conn.close()
    logger.info("Applied %d company profile claim updates", applied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
