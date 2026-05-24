"""Operational SQLite pipeline tests (daily path, not enterprise SQLAlchemy)."""

from __future__ import annotations

import inspect
import json
import sqlite3

import pytest


@pytest.mark.operational
def test_schema_migrations_add_intelligence_events(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='intelligence_events'")
    assert cur.fetchone() is not None
    cols = {r[1] for r in cur.execute("PRAGMA table_info(intelligence_events)")}
    assert "raw_signal_id" in cols
    assert "embedding" in cols
    conn.close()


@pytest.mark.operational
def test_signal_processor_creates_event_from_raw_signal(operational_db, monkeypatch):
    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies (name, slug, website)
        VALUES ('Acme Fintech', 'acme-fintech', 'https://acme.example')
        """
    )
    company_id = cur.lastrowid
    payload = {
        "title": "Acme Fintech raises $50 million Series B led by Sequoia",
        "description": "Acme Fintech closes $50 million Series B led by Sequoia Capital",
        "url": "https://news.example/acme-series-b",
    }
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'techcrunch', 'funding_news', ?, 0)
        """,
        (company_id, json.dumps(payload)),
    )
    signal_id = cur.lastrowid
    conn.commit()
    conn.close()

    from collectors.signal_processor import process_signals

    result = process_signals(batch_size=10)
    assert result["created"] >= 1

    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT event_type, amount_usd, raw_signal_id "
        "FROM intelligence_events WHERE raw_signal_id = ?",
        (signal_id,),
    )
    row = cur.fetchone()
    assert row is not None
    assert row["raw_signal_id"] == signal_id
    assert row["event_type"] == "Funding Round"
    assert row["amount_usd"] == 50_000_000
    cur.execute("SELECT processed FROM raw_signals WHERE id = ?", (signal_id,))
    assert cur.fetchone()["processed"] == 1
    conn.close()


@pytest.mark.operational
def test_safe_request_has_no_allow_redirects_kwarg():
    """Regression: collectors must not pass invalid kwargs to safe_request."""

    from utils.http import safe_request

    params = inspect.signature(safe_request).parameters
    assert "allow_redirects" not in params
