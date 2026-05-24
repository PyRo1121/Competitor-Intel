"""Canonical funding_rounds read helper."""

from __future__ import annotations

import sqlite3

from db.funding_read import fetch_company_funding_rows


def test_fetch_company_funding_rows_from_rounds(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE funding_rounds (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL,
            round_type TEXT NOT NULL,
            amount_usd INTEGER,
            valuation_usd INTEGER,
            announced_date DATE,
            lead_investor TEXT,
            source TEXT
        );
        INSERT INTO companies (name) VALUES ('Acme');
        INSERT INTO funding_rounds (
            company_id, round_type, amount_usd, valuation_usd,
            announced_date, lead_investor, source
        ) VALUES (1, 'Series A', 10000000, 50000000, '2024-01-01', 'VC Fund', 'sec');
        """
    )
    rows = fetch_company_funding_rows(cur, 1)
    assert len(rows) == 1
    assert rows[0]["round_type"] == "Series A"
    assert rows[0]["amount_usd"] == 10_000_000
    conn.close()
