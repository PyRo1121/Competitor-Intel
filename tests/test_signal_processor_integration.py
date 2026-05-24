"""Integration tests for signal_processor — real SQLite, full assertions."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors import signal_processor as sp


def _insert_company(cur, name: str, website: str | None = None) -> int:
    cur.execute(
        "INSERT INTO companies (name, slug, website) VALUES (?, ?, ?)",
        (name, name.lower().replace(" ", "-"), website),
    )
    return cur.lastrowid


def _insert_signal(
    cur,
    *,
    company_id: int | None,
    payload: dict,
    processed: int = 0,
    source: str = "techcrunch",
) -> int:
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, ?, 'news', ?, ?)
        """,
        (company_id, source, json.dumps(payload), processed),
    )
    return cur.lastrowid


@pytest.mark.operational
def test_process_signals_funding_event_fields(operational_db):
    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cid = _insert_company(cur, "FundCo", "https://fundco.example")
    sig_id = _insert_signal(
        cur,
        company_id=cid,
        payload={
            "title": "FundCo raises $50 million Series B led by Sequoia",
            "url": "https://news.example/fundco-b",
        },
    )
    conn.commit()
    conn.close()

    result = sp.process_signals(batch_size=10)
    assert result["created"] >= 1

    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT event_type, amount_usd, company_id, confidence, description,
               source_url, raw_signal_id
        FROM intelligence_events WHERE raw_signal_id = ?
        """,
        (sig_id,),
    ).fetchone()
    proc = conn.execute("SELECT processed FROM raw_signals WHERE id = ?", (sig_id,)).fetchone()
    conn.close()

    assert row is not None
    assert row["event_type"] == "Funding Round"
    assert row["amount_usd"] == 50_000_000
    assert row["company_id"] == cid
    assert row["confidence"] >= sp.EVENT_PATTERNS["funding"]["min_confidence"]
    assert "FundCo" in row["description"]
    assert row["raw_signal_id"] == sig_id
    assert "#rs" in row["source_url"] or row["source_url"].startswith("https://")
    assert proc["processed"] == 1


@pytest.mark.operational
def test_process_signals_resolves_company_from_website(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cid = _insert_company(cur, "DomainCo", "https://domainco.ai")
    sig_id = _insert_signal(
        cur,
        company_id=None,
        payload={
            "title": "DomainCo unveiled enterprise dashboard",
            "url": "https://domainco.ai/blog/dashboard",
        },
    )
    conn.commit()
    conn.close()

    sp.process_signals(batch_size=5)

    conn = sqlite3.connect(operational_db)
    row = conn.execute(
        "SELECT company_id, event_type FROM intelligence_events WHERE raw_signal_id = ?",
        (sig_id,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[0] == cid
    assert row[1] == "Product Launch"


@pytest.mark.operational
def test_integrity_error_links_existing_url(operational_db):
    """Second signal same article URL links row instead of duplicate insert."""
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cid = _insert_company(cur, "UrlCo")
    url = "https://news.example/shared-article"
    sig_a = _insert_signal(
        cur,
        company_id=cid,
        payload={"title": "UrlCo raises $10 million Series A", "url": url},
    )
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, announced_date, created_at)
        VALUES (?, 'Funding Round', 'techcrunch', ?, datetime('now'), datetime('now'))
        """,
        (cid, url),
    )
    conn.commit()
    conn.close()

    sp.process_signals(batch_size=5)

    conn = sqlite3.connect(operational_db)
    linked = conn.execute(
        "SELECT raw_signal_id FROM intelligence_events WHERE source_url = ?",
        (url,),
    ).fetchone()[0]
    count = conn.execute(
        "SELECT COUNT(*) FROM intelligence_events WHERE source_url = ?", (url,)
    ).fetchone()[0]
    conn.close()

    assert linked == sig_a
    assert count == 1


@pytest.mark.operational
def test_duplicate_source_url_suffixes_allow_two_events(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cid = _insert_company(cur, "SharedUrl Inc")
    base = "https://news.example/same-story"
    sig1 = _insert_signal(
        cur,
        company_id=cid,
        payload={"title": "SharedUrl Inc launches API", "url": base},
    )
    sig2 = _insert_signal(
        cur,
        company_id=cid,
        payload={"title": "SharedUrl Inc partners with vendor", "url": base},
        source="rss",
    )
    conn.commit()
    conn.close()

    sp.process_signals(batch_size=10)

    conn = sqlite3.connect(operational_db)
    rows = conn.execute(
        """
        SELECT raw_signal_id, source_url FROM intelligence_events
        WHERE raw_signal_id IN (?, ?)
        ORDER BY raw_signal_id
        """,
        (sig1, sig2),
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]
    assert rows[0][1] != rows[1][1]
    assert base in rows[0][1] and base in rows[1][1]


@pytest.mark.operational
def test_relink_orphan_companies_updates_event(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cid = _insert_company(cur, "Relink Labs", "https://relinklabs.com")
    sig_id = _insert_signal(
        cur,
        company_id=None,
        processed=1,
        payload={
            "title": "Relink Labs announces partnership with BigBank",
            "url": "https://relinklabs.com/news/partnership",
        },
    )
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, confidence,
         description, announced_date, created_at)
        VALUES (NULL, 'General News', 'rss', ?, ?, 0.4,
                'Relink Labs announces partnership', datetime('now'), datetime('now'))
        """,
        (f"https://relinklabs.com/news/partnership#rs{sig_id}", sig_id),
    )
    conn.commit()
    conn.close()

    stats = sp.relink_orphan_companies(batch_size=50)
    assert stats["updated"] >= 1

    conn = sqlite3.connect(operational_db)
    row = conn.execute(
        "SELECT company_id FROM intelligence_events WHERE raw_signal_id = ?",
        (sig_id,),
    ).fetchone()
    conn.close()
    assert row[0] == cid


@pytest.mark.operational
def test_backfill_stops_when_no_signals_left(operational_db, monkeypatch):
    """Backfill stops after one productive batch when the queue is empty."""
    calls = {"n": 0}
    real_process = sp.process_signals

    def counting_process(batch_size=500):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_process(batch_size=batch_size)
        return {"processed": 0, "created": 0, "skipped": 0}

    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cid = _insert_company(cur, "IdleCo")
    _insert_signal(
        cur,
        company_id=cid,
        payload={"title": "IdleCo hiring spree continues", "url": "https://ex.com/1"},
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(sp, "process_signals", counting_process)
    total = sp.backfill_all_signals(max_batches=10)

    assert calls["n"] == 2
    assert total["batches"] == 1
    assert total["created"] >= 1


@pytest.mark.operational
def test_enclosed_does_not_classify_as_funding():
    """Regression: bare 'closed' in funding keywords caused false positives."""
    internal, _ = sp.classify_event("enclosed warehouse renovation delayed after inspection", "rss")
    assert internal == "general"
