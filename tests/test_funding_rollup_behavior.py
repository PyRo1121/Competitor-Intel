"""Operational tests for funding_rollup (P3-4 coverage)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.funding_rollup import main, run  # noqa: E402


@pytest.mark.operational
def test_funding_rollup_run_empty_db(operational_db):
    result = run()
    assert isinstance(result, dict)


@pytest.mark.operational
def test_funding_rollup_main_with_funding_event(operational_db, monkeypatch):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('FundedCo', 'fundedco')")
    cid = cur.lastrowid
    payload = json.dumps(
        {
            "title": "FundedCo raises $10M Series A led by Acme Ventures",
            "url": "https://example.com/fundedco-series-a",
        }
    )
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'funding', ?, 1)
        """,
        (cid, payload),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, confidence,
         description, amount_usd, announced_date, created_at)
        VALUES (?, 'Funding Round', 'rss', 'https://example.com/fundedco-series-a',
                ?, 0.85, 'FundedCo raises $10M Series A', 10000000,
                datetime('now'), datetime('now'))
        """,
        (cid, sid),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        "collectors.enrichment.funding_enricher.extract_from_signals",
        lambda: {"claims_created": 1, "rounds_upserted": 1},
    )
    assert main() == 0
