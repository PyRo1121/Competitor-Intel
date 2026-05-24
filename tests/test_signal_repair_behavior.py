"""Behavior tests for signal_repair — each repair step in isolation."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.signal_repair import (
    backfill_funding_amounts,
    ensure_indexes,
    reclassify_general_news_events,
    reclassify_misfunded_events,
    relabel_minimal_general_news,
    seed_company_identifiers,
    sync_company_from_raw_signals,
)


@pytest.mark.operational
def test_sync_company_from_raw_signals(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('SyncCo', 'syncco')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', '{}', 1)
        """,
        (cid,),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (
            NULL, 'General News', 'rss', 'https://ex.com/sync', ?,
            datetime('now'), datetime('now')
        )
        """,
        (sid,),
    )
    conn.commit()

    n = sync_company_from_raw_signals(conn)
    row = cur.execute(
        "SELECT company_id FROM intelligence_events WHERE raw_signal_id = ?", (sid,)
    ).fetchone()
    conn.close()
    assert n == 1
    assert row[0] == cid


@pytest.mark.operational
def test_backfill_funding_amounts_from_description(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         announced_date, created_at)
        VALUES (NULL, 'Funding Round', 0, 'rss', 'https://ex.com/f1', ?,
                datetime('now'), datetime('now'))
        """,
        ("Startup closes $15 million Series A",),
    )
    eid = cur.lastrowid
    conn.commit()

    updated = backfill_funding_amounts(conn)
    amount = cur.execute(
        "SELECT amount_usd FROM intelligence_events WHERE id = ?", (eid,)
    ).fetchone()[0]
    conn.close()
    assert updated == 1
    assert amount == 15_000_000


@pytest.mark.operational
def test_reclassify_misfunded_events_without_money_signals(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         confidence, announced_date, created_at)
        VALUES (NULL, 'Funding Round', 0, 'rss', 'https://ex.com/mis',
                'Company expands into new markets', 0.9,
                datetime('now'), datetime('now'))
        """
    )
    eid = cur.lastrowid
    conn.commit()

    n = reclassify_misfunded_events(conn)
    row = cur.execute(
        "SELECT event_type, confidence FROM intelligence_events WHERE id = ?",
        (eid,),
    ).fetchone()
    conn.close()
    assert n == 1
    assert row[0] == "General News"
    assert row[1] <= 0.4


@pytest.mark.operational
def test_reclassify_leaves_real_funding_with_raised_keyword(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         announced_date, created_at)
        VALUES (NULL, 'Funding Round', 0, 'rss', 'https://ex.com/real',
                'Company raised strategic round', datetime('now'), datetime('now'))
        """
    )
    conn.commit()
    n = reclassify_misfunded_events(conn)
    row = cur.execute(
        "SELECT event_type FROM intelligence_events WHERE source_url = ?",
        ("https://ex.com/real",),
    ).fetchone()
    conn.close()
    assert n == 0
    assert row[0] == "Funding Round"


@pytest.mark.operational
def test_seed_company_identifiers(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies (name, slug, website, x_handle, github_org)
        VALUES ('SeedCo', 'seedco', 'https://www.seedco.io', '@seedco', 'seedco')
        """
    )
    conn.commit()

    inserted = seed_company_identifiers(conn)
    rows = cur.execute(
        "SELECT id_type, id_value FROM company_identifiers ORDER BY id_type, id_value"
    ).fetchall()
    conn.close()
    assert inserted >= 3
    types = {r[0] for r in rows}
    assert "domain" in types
    assert "alias" in types
    assert "github" in types


@pytest.mark.operational
def test_ensure_indexes_creates_when_no_dupes(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('IdxCo', 'idxco')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', '{}', 1)
        """,
        (cid,),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (?, 'General News', 'rss', 'https://ex.com/idx', ?, datetime('now'), datetime('now'))
        """,
        (cid, sid),
    )
    conn.commit()

    created = ensure_indexes(conn)
    dup_count = cur.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='index' AND name='idx_intel_raw_signal_unique'
        """
    ).fetchone()[0]
    conn.close()
    assert created == 1
    assert dup_count == 1


@pytest.mark.operational
def test_ensure_indexes_skips_when_dupes_exist(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('DupIdx', 'dupidx')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', '{}', 1)
        """,
        (cid,),
    )
    sid = cur.lastrowid
    for url in ("https://ex.com/d1", "https://ex.com/d2"):
        cur.execute(
            """
            INSERT INTO intelligence_events
            (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
            VALUES (?, 'General News', 'rss', ?, ?, datetime('now'), datetime('now'))
            """,
            (cid, url, sid),
        )
    conn.commit()
    created = ensure_indexes(conn)
    conn.close()
    assert created == 0


@pytest.mark.operational
def test_reclassify_general_news_events(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('ReclassCo', 'reclassco')")
    cid = cur.lastrowid
    payload = json.dumps(
        {
            "title": "Acme announces strategic partnership with BigCorp",
            "url": "https://ex.com/partnership",
        }
    )
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'techcrunch', 'news', ?, 1)
        """,
        (cid, payload),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id,
         description, announced_date, created_at)
        VALUES (?, 'General News', 'techcrunch', 'https://ex.com/partnership', ?,
                'Acme announces strategic partnership with BigCorp',
                datetime('now'), datetime('now'))
        """,
        (cid, sid),
    )
    eid = cur.lastrowid
    conn.commit()

    n = reclassify_general_news_events(conn)
    row = cur.execute("SELECT event_type FROM intelligence_events WHERE id = ?", (eid,)).fetchone()
    conn.close()
    assert n >= 1
    assert row[0] == "Partnership"


@pytest.mark.operational
def test_relabel_minimal_general_news(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('SparseCo', 'sparseco')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, description, announced_date, created_at)
        VALUES (
            ?, 'General News', 'hackernews', 'https://ex.com/s', 'Arc',
            datetime('now'), datetime('now')
        )
        """,
        (cid,),
    )
    eid = cur.lastrowid
    conn.commit()

    n = relabel_minimal_general_news(conn)
    row = cur.execute("SELECT event_type FROM intelligence_events WHERE id = ?", (eid,)).fetchone()
    conn.close()
    assert n == 1
    assert row[0] == "Unlabeled Signal"
