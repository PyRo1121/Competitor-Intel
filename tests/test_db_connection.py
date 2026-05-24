"""Tests for centralized SQLite connection helpers."""

from __future__ import annotations

import sqlite3

import pytest
from db import connection as db_connection


@pytest.mark.operational
def test_active_db_path_honors_test_override(operational_db, monkeypatch):
    monkeypatch.setenv("CI_DB_PATH", "/tmp/should-not-use-if-override.db")
    assert db_connection.active_db_path() == operational_db


@pytest.mark.operational
def test_get_conn_sets_wal_and_foreign_keys(operational_db):
    conn = db_connection.get_conn()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    mmap = conn.execute("PRAGMA mmap_size").fetchone()[0]
    conn.close()
    assert str(mode).lower() == "wal"
    assert fk == 1
    assert int(busy) >= 1000
    assert int(mmap) >= 1_000_000


def test_ingest_bulk_profile(operational_db):
    conn = db_connection.get_conn(profile="ingest_bulk")
    cache = conn.execute("PRAGMA cache_size").fetchone()[0]
    conn.close()
    assert int(cache) < 0


@pytest.mark.operational
def test_transaction_commits_on_success(operational_db):
    with db_connection.transaction() as conn:
        conn.execute("INSERT INTO companies (name, slug) VALUES ('TxCo', 'txco')")
    conn = sqlite3.connect(operational_db)
    count = conn.execute("SELECT COUNT(*) FROM companies WHERE slug = 'txco'").fetchone()[0]
    conn.close()
    assert count == 1


@pytest.mark.operational
def test_transaction_rolls_back_on_error(operational_db):
    with pytest.raises(sqlite3.OperationalError), db_connection.transaction() as conn:
        conn.execute("INSERT INTO companies (name, slug) VALUES ('Bad', 'bad')")
        conn.execute("INSERT INTO no_such_table (x) VALUES (1)")
    conn = sqlite3.connect(operational_db)
    count = conn.execute("SELECT COUNT(*) FROM companies WHERE slug = 'bad'").fetchone()[0]
    conn.close()
    assert count == 0


@pytest.mark.operational
def test_get_cursor_context(operational_db):
    with db_connection.get_cursor() as cur:
        cur.execute("INSERT INTO companies (name, slug) VALUES ('CurCo', 'curco')")
    conn = sqlite3.connect(operational_db)
    assert conn.execute("SELECT name FROM companies WHERE slug = 'curco'").fetchone()[0] == "CurCo"
    conn.close()
