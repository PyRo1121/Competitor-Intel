"""Tests for signal_repair helpers."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.signal_repair import dedupe_events_by_raw_signal


@pytest.mark.operational
def test_dedupe_events_by_raw_signal_keeps_highest_id(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('DedupeCo', 'dedupeco')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 1)
        """,
        (cid, json.dumps({"title": "dup"})),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (?, 'General News', 'rss', 'https://ex.com/a', ?, datetime('now'), datetime('now'))
        """,
        (cid, sid),
    )
    low_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (?, 'General News', 'rss', 'https://ex.com/b', ?, datetime('now'), datetime('now'))
        """,
        (cid, sid),
    )
    conn.commit()

    deleted = dedupe_events_by_raw_signal(conn)
    remaining = cur.execute(
        "SELECT id FROM intelligence_events WHERE raw_signal_id = ?", (sid,)
    ).fetchall()

    conn.close()
    assert deleted == 1
    assert len(remaining) == 1
    assert remaining[0][0] > low_id
