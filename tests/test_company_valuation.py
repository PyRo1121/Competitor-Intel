"""Company-level valuation resolution and sync."""

from __future__ import annotations

import sqlite3

import pytest
from collectors.enrichment.company_valuation import (
    resolve_company_valuation,
    sync_all_company_valuations,
)


@pytest.fixture
def val_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE funding_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            round_type TEXT,
            amount_usd INTEGER,
            valuation_usd INTEGER,
            post_money_valuation_usd INTEGER,
            pre_money_valuation_usd INTEGER,
            announced_date TEXT,
            corroboration_score REAL
        );
        CREATE TABLE intelligence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            valuation_usd INTEGER,
            announced_date TEXT,
            confidence REAL
        );
        CREATE TABLE raw_signals (id INTEGER PRIMARY KEY, company_id INTEGER);
        CREATE TABLE job_postings (id INTEGER PRIMARY KEY, company_id INTEGER, is_active INTEGER);
        CREATE TABLE github_metrics (id INTEGER PRIMARY KEY, company_id INTEGER);
        CREATE TABLE company_valuations (
            company_id INTEGER PRIMARY KEY,
            valuation_usd INTEGER NOT NULL,
            valuation_kind TEXT NOT NULL,
            method TEXT NOT NULL,
            confidence REAL NOT NULL,
            as_of_date TEXT,
            source_funding_round_id INTEGER,
            source_notes TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    yield conn
    conn.close()


def test_reported_post_money_preferred(val_db):
    val_db.execute("INSERT INTO companies (id, name) VALUES (1, 'Acme')")
    val_db.execute(
        """
        INSERT INTO funding_rounds
        (company_id, round_type, amount_usd, post_money_valuation_usd,
         announced_date, corroboration_score)
        VALUES (1, 'Series A', 20000000, 120000000, '2024-06-01', 0.6)
        """
    )
    record = resolve_company_valuation(val_db, 1)
    assert record is not None
    assert record["valuation_usd"] == 120_000_000
    assert record["valuation_kind"] == "reported"
    assert record["method"] == "reported_post_money"


def test_inferred_from_latest_round(val_db):
    val_db.execute("INSERT INTO companies (id, name) VALUES (1, 'Beta')")
    val_db.execute(
        """
        INSERT INTO funding_rounds
        (company_id, round_type, amount_usd, announced_date, corroboration_score)
        VALUES (1, 'Series A', 10000000, '2024-01-01', 0.5)
        """
    )
    record = resolve_company_valuation(val_db, 1)
    assert record is not None
    assert record["valuation_kind"] == "estimated"
    assert record["method"] == "inferred_from_latest_round"
    assert record["valuation_usd"] == 50_000_000  # 10M × 5.0


def test_no_valuation_without_financials(val_db):
    val_db.execute("INSERT INTO companies (id, name) VALUES (1, 'Quiet')")
    val_db.execute(
        "INSERT INTO raw_signals (id, company_id) VALUES (1, 1)",
    )
    assert resolve_company_valuation(val_db, 1) is None


def test_sync_all_companies(val_db):
    val_db.executemany("INSERT INTO companies (id, name) VALUES (?, ?)", [(1, "A"), (2, "B")])
    val_db.execute(
        """
        INSERT INTO funding_rounds
        (company_id, round_type, amount_usd, announced_date, corroboration_score)
        VALUES (1, 'Seed', 2000000, '2023-01-01', 0.4)
        """
    )
    val_db.execute(
        """
        INSERT INTO company_valuations
        (company_id, valuation_usd, valuation_kind, method, confidence, updated_at)
        VALUES (2, 8000000, 'estimated', 'estimated_baseline', 0.2, '2020-01-01')
        """
    )
    stats = sync_all_company_valuations(val_db)
    assert stats["companies"] == 2
    assert stats["estimated"] == 1
    assert stats["cleared"] == 1
    rows = val_db.execute("SELECT company_id FROM company_valuations").fetchall()
    assert [r[0] for r in rows] == [1]
