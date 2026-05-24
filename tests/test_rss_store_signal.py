"""RSS store_signal high-signal gate (6-COL01)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.rss_collector import store_signal  # noqa: E402


def _entry(*, high_signal: bool, mentions: list[str] | None = None) -> dict:
    return {
        "title": "Test headline",
        "link": "https://example.com/article-1",
        "summary": "Summary text",
        "source": "Test Feed",
        "category": "vc",
        "published": "2026-05-20T12:00:00Z",
        "high_signal": high_signal,
        "mentioned_companies": mentions or [],
    }


def test_store_signal_skips_low_signal_without_mentions(operational_db, monkeypatch):
    calls: list[tuple] = []

    def fake_insert(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr("collectors.rss_collector.insert_raw_signal_dedup", fake_insert)
    conn = sqlite3.connect(operational_db)
    cursor = conn.cursor()
    assert store_signal(_entry(high_signal=False), cursor) == 0
    assert calls == []


def test_store_signal_stores_high_signal_once_without_mentions(operational_db, monkeypatch):
    calls: list[tuple] = []

    def fake_insert(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr("collectors.rss_collector.insert_raw_signal_dedup", fake_insert)
    conn = sqlite3.connect(operational_db)
    cursor = conn.cursor()
    assert store_signal(_entry(high_signal=True), cursor) == 1
    assert len(calls) == 1
