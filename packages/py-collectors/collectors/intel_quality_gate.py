#!/usr/bin/env python3
"""Operational DB quality gate for signals → events pipeline."""

from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any

from ci_paths import db_path

from collectors.signal_company_resolver import build_domain_index, resolve_company_enhanced
from collectors.signal_processor import (
    fuzzy_match_company,
    parse_signal_data,
    resolve_company_from_data,
)

THRESHOLDS = {
    "orphan_signals_max": 0,
    "unprocessed_max": 0,
    "null_company_pct_max": 40.0,
    "actionable_null_pct_max": 5.0,
    "general_news_pct_max": 65.0,
    "dup_raw_signal_id_max": 0,
    "pct_funding_no_amount_max": 25.0,
}

_MONEY_KW_SQL = """
    LOWER(COALESCE(description, '')) LIKE '%million%'
    OR LOWER(COALESCE(description, '')) LIKE '%billion%'
    OR LOWER(COALESCE(description, '')) LIKE '%raised%'
    OR LOWER(COALESCE(description, '')) LIKE '%$%'
    OR LOWER(COALESCE(description, '')) LIKE '%series %'
"""


def actionable_null_stats(cur: sqlite3.Cursor) -> tuple[int, int]:
    """Counts of null company_id events that mention a tracked name (actionable, missed link)."""
    cur.execute("SELECT LOWER(name) FROM companies WHERE LENGTH(name) >= 4")
    names = [r[0] for r in cur.fetchall()]
    domain_index = build_domain_index(cur)
    cur.execute(
        """
        SELECT ie.id, ie.description, rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.company_id IS NULL
        """
    )
    actionable = 0
    missed = 0
    for _eid, description, data_json in cur.fetchall():
        data = parse_signal_data(data_json)
        blob = (description or "").lower()
        blob += " ".join(
            str(data.get(k, ""))
            for k in ("title", "headline", "description", "summary", "content", "url", "link")
        ).lower()
        if not any(n in blob for n in names):
            continue
        actionable += 1
        resolved = resolve_company_enhanced(
            data,
            cur,
            domain_index=domain_index,
            fuzzy_match_fn=fuzzy_match_company,
            resolve_from_data_fn=resolve_company_from_data,
        )
        if resolved:
            missed += 1
    return actionable, missed


def actionable_null_pct(cur: sqlite3.Cursor) -> float:
    """Share of null company_id events where resolver could still link a tracked company."""
    actionable, missed = actionable_null_stats(cur)
    if actionable == 0:
        return 0.0
    return 100.0 * missed / actionable


def collect_metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    cur = conn.cursor()

    orphans = cur.execute(
        """
        SELECT COUNT(*) FROM raw_signals rs
        WHERE NOT EXISTS (
            SELECT 1 FROM intelligence_events ie WHERE ie.raw_signal_id = rs.id
        )
        """
    ).fetchone()[0]

    unprocessed = cur.execute("SELECT COUNT(*) FROM raw_signals WHERE processed = 0").fetchone()[0]

    total_ie = cur.execute("SELECT COUNT(*) FROM intelligence_events").fetchone()[0]
    null_co = cur.execute(
        "SELECT COUNT(*) FROM intelligence_events WHERE company_id IS NULL"
    ).fetchone()[0]
    general = cur.execute(
        "SELECT COUNT(*) FROM intelligence_events WHERE event_type = 'General News'"
    ).fetchone()[0]

    funding_no_amt = cur.execute(
        f"""
        SELECT COUNT(*) FROM intelligence_events
        WHERE event_type LIKE '%Funding%'
          AND COALESCE(amount_usd, 0) = 0
          AND ({_MONEY_KW_SQL})
        """
    ).fetchone()[0]
    funding_money_kw = cur.execute(
        f"""
        SELECT COUNT(*) FROM intelligence_events
        WHERE event_type LIKE '%Funding%'
          AND ({_MONEY_KW_SQL})
        """
    ).fetchone()[0]

    dup = cur.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT raw_signal_id FROM intelligence_events
            WHERE raw_signal_id IS NOT NULL
            GROUP BY raw_signal_id HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    null_pct = 100.0 * null_co / total_ie if total_ie else 0.0
    general_pct = 100.0 * general / total_ie if total_ie else 0.0
    funding_no_pct = 100.0 * funding_no_amt / funding_money_kw if funding_money_kw else 0.0
    act_null = actionable_null_pct(cur)

    return {
        "orphans": orphans,
        "unprocessed": unprocessed,
        "null_company_pct": round(null_pct, 1),
        "general_news_pct": round(general_pct, 1),
        "dup_raw_signal_id": dup,
        "pct_funding_no_amount": round(funding_no_pct, 1),
        "actionable_null_pct": round(act_null, 1),
    }


def check_metrics(metrics: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if metrics["orphans"] > THRESHOLDS["orphan_signals_max"]:
        failed.append(f"orphans={metrics['orphans']}")
    if metrics["unprocessed"] > THRESHOLDS["unprocessed_max"]:
        failed.append(f"unprocessed={metrics['unprocessed']}")
    if metrics["null_company_pct"] > THRESHOLDS["null_company_pct_max"]:
        failed.append(f"null_company_pct={metrics['null_company_pct']}")
    if metrics["actionable_null_pct"] > THRESHOLDS["actionable_null_pct_max"]:
        failed.append(f"actionable_null_pct={metrics['actionable_null_pct']}")
    if metrics["general_news_pct"] > THRESHOLDS["general_news_pct_max"]:
        failed.append(f"general_news_pct={metrics['general_news_pct']}")
    if metrics["dup_raw_signal_id"] > THRESHOLDS["dup_raw_signal_id_max"]:
        failed.append(f"dup_raw_signal_id={metrics['dup_raw_signal_id']}")
    if metrics["pct_funding_no_amount"] > THRESHOLDS["pct_funding_no_amount_max"]:
        failed.append(f"pct_funding_no_amount={metrics['pct_funding_no_amount']}")
    return failed


def main() -> int:
    db = str(db_path())
    if not os.path.isfile(db):
        print(f"FAIL: database not found: {db}")
        return 1

    conn = sqlite3.connect(db)
    metrics = collect_metrics(conn)
    conn.close()

    print("Intel quality metrics:", metrics)
    failed = check_metrics(metrics)
    if failed:
        print("FAIL:", ", ".join(failed))
        return 1

    print("PASS: intel quality gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
