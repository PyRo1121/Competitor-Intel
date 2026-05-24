"""Tests for reprocess_raw_signals reset logic."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from db import reprocess as rrs
from db.connection import get_conn
from db.migrations import apply_runtime_migrations


@pytest.mark.operational
def test_count_and_reset_orphans(operational_db, monkeypatch):
    monkeypatch.chdir(ROOT)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('OrphanCo', 'orphan')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 1)
        """,
        (cid, json.dumps({"title": "orphan"})),
    )
    conn.commit()

    assert rrs.count_orphan_processed(conn) == 1
    reset = rrs.reset_orphans(conn, dry_run=False)
    assert reset == 1
    assert conn.execute("SELECT processed FROM raw_signals").fetchone()[0] == 0
    conn.close()


@pytest.mark.operational
def test_migrations_idempotent_on_existing_db(operational_db):
    conn = sqlite3.connect(operational_db)
    apply_runtime_migrations(conn)
    apply_runtime_migrations(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(intelligence_events)")}
    conn.close()
    assert "raw_signal_id" in cols
    assert "embedding" in cols
