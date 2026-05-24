"""Dedup index enforcement under CI_REQUIRE_DEDUP_INDEX / CI_STRICT_PIPELINE (6-A11)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from db.schema import ensure_raw_signals_dedup_index  # noqa: E402


def _db_with_duplicate_rows(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE raw_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            source TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            data_json TEXT NOT NULL DEFAULT '{}',
            detected_at TEXT,
            processed INTEGER DEFAULT 0
        );
        INSERT INTO raw_signals (source, signal_type) VALUES ('a', 'k'), ('a', 'k');
        """
    )
    conn.commit()
    return conn


def test_ensure_dedup_index_warns_on_duplicates(monkeypatch, tmp_path):
    monkeypatch.delenv("CI_STRICT_PIPELINE", raising=False)
    monkeypatch.delenv("CI_REQUIRE_DEDUP_INDEX", raising=False)
    conn = _db_with_duplicate_rows(tmp_path / "dup.db")
    ensure_raw_signals_dedup_index(conn)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_raw_signals_dedup'")
    assert cur.fetchone() is None
    conn.close()


def test_ensure_dedup_index_fails_when_strict(monkeypatch, tmp_path):
    monkeypatch.setenv("CI_STRICT_PIPELINE", "1")
    conn = _db_with_duplicate_rows(tmp_path / "dup_strict.db")
    with pytest.raises(RuntimeError, match="migrate-dedup"):
        ensure_raw_signals_dedup_index(conn)
    conn.close()
