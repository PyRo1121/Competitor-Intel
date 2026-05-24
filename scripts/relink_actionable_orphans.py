#!/usr/bin/env python3
"""Relink intelligence_events where headline names a tracked company but company_id is null."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from ci_paths import ensure_app_paths

ensure_app_paths()

from collectors.signal_company_resolver import (  # noqa: E402
    build_domain_index,
    resolve_company_enhanced,
)
from collectors.signal_processor import (  # noqa: E402
    fuzzy_match_company,
    parse_signal_data,
    resolve_company_from_data,
)
from db.connection import get_conn  # noqa: E402

logger = logging.getLogger("relink_actionable")


def relink_actionable_orphans(batch_size: int = 500) -> dict[str, int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT LOWER(name) FROM companies WHERE LENGTH(name) >= 4")
    names = [r[0] for r in cur.fetchall()]
    if not names:
        conn.close()
        return {"candidates": 0, "updated": 0}

    cur.execute(
        """
        SELECT ie.id, ie.description, rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.company_id IS NULL
        LIMIT ?
        """,
        (batch_size * 3,),
    )
    rows = cur.fetchall()
    domain_index = build_domain_index(cur)
    updated = 0
    candidates = 0

    for event_id, description, data_json in rows:
        blob = (description or "").lower()
        data = parse_signal_data(data_json)
        blob += (
            " "
            + " ".join(
                str(data.get(k, ""))
                for k in ("title", "headline", "description", "summary", "content")
            ).lower()
        )
        if not any(n in blob for n in names):
            continue
        candidates += 1
        matched = resolve_company_enhanced(
            data,
            cur,
            domain_index=domain_index,
            fuzzy_match_fn=fuzzy_match_company,
            resolve_from_data_fn=resolve_company_from_data,
        )
        if not matched:
            continue
        cid = matched[0]
        cur.execute(
            "UPDATE intelligence_events SET company_id = ? WHERE id = ?",
            (cid, event_id),
        )
        if data_json:
            cur.execute(
                """
                UPDATE raw_signals SET company_id = ?
                WHERE id = (SELECT raw_signal_id FROM intelligence_events WHERE id = ?)
                  AND company_id IS NULL
                """,
                (cid, event_id),
            )
        updated += 1
        if updated >= batch_size:
            break

    conn.commit()
    conn.close()
    return {"candidates": candidates, "updated": updated}


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    stats = relink_actionable_orphans()
    logger.info("Actionable relink: %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
