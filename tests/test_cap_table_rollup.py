"""Cap table rollup from round_participants (Track 5 P5-1)."""

from __future__ import annotations

import sqlite3

import pytest
from collectors.cap_table_rollup import sync_cap_table_from_rounds


@pytest.fixture
def cap_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE investor_firms (
            id INTEGER PRIMARY KEY,
            name TEXT,
            name_normalized TEXT,
            tier INTEGER DEFAULT 3,
            last_updated TEXT
        );
        CREATE TABLE funding_rounds (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL,
            announced_date TEXT
        );
        CREATE TABLE round_participants (
            id INTEGER PRIMARY KEY,
            funding_round_id INTEGER NOT NULL,
            investor_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            is_lead INTEGER DEFAULT 0,
            corroboration_score REAL DEFAULT 0.5
        );
        CREATE TABLE cap_table_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            holder_name TEXT NOT NULL,
            holder_normalized TEXT NOT NULL,
            ownership_pct REAL,
            share_class TEXT,
            as_of_date TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(company_id, holder_normalized, source_url)
        );
        """
    )
    conn.execute("INSERT INTO companies (id, name) VALUES (1, 'Acme')")
    conn.execute(
        """
        INSERT INTO investor_firms (id, name, name_normalized)
        VALUES (10, 'Sequoia Capital', 'sequoia')
        """
    )
    conn.execute(
        "INSERT INTO funding_rounds (id, company_id, announced_date) VALUES (100, 1, '2025-06-01')"
    )
    conn.execute(
        """
        INSERT INTO round_participants (
            funding_round_id, investor_id, role, is_lead, corroboration_score
        ) VALUES (100, 10, 'lead', 1, 0.9)
        """
    )
    yield conn
    conn.close()


def test_sync_cap_table_from_rounds(cap_db):
    stats = sync_cap_table_from_rounds(cap_db)
    assert stats["holdings_upserted"] >= 1
    row = cap_db.execute(
        "SELECT holder_name, share_class, source, ownership_pct FROM cap_table_holdings"
    ).fetchone()
    assert row is not None
    assert "Sequoia" in row["holder_name"]
    assert row["share_class"] == "lead"
    assert row["source"] == "funding_round"
    assert row["ownership_pct"] is None
