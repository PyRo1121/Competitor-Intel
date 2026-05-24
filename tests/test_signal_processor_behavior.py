"""Behavior tests for signal_processor — edge cases that have caused real bugs."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch

import pytest
from collectors import signal_processor as sp

# --- parse_signal_data / extract_signal_text / fallback ---


@pytest.mark.operational
def test_parse_signal_data_rejects_non_dict_json():
    assert sp.parse_signal_data('["not", "a", "dict"]') == {}
    assert sp.parse_signal_data("") == {}
    assert sp.parse_signal_data(None) == {}


@pytest.mark.operational
def test_parse_signal_data_invalid_literal_returns_empty():
    assert sp.parse_signal_data("{not valid python") == {}


@pytest.mark.operational
def test_extract_signal_text_joins_all_signal_keys():
    data = {
        "title": "Headline",
        "description": "Body",
        "headline": "ignored duplicate key order",
    }
    text = sp.extract_signal_text(data)
    assert "Headline" in text
    assert "Body" in text


@pytest.mark.operational
def test_fallback_signal_text_uses_url_when_no_title():
    text = sp.fallback_signal_text(
        {"url": "https://example.com/x"},
        "rss",
        "news",
        42,
    )
    assert "rss" in text
    assert "https://example.com/x" in text


# --- normalize_source ---


@pytest.mark.operational
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Hacker News", "hackernews"),
        ("hn", "hackernews"),
        ("Product Hunt Daily", "producthunt"),
        ("Crunchbase Feed", "crunchbase"),
        ("https://github.com/org/repo", "github"),
        ("YouTube channel", "youtube"),
        ("AngelList startups", "angellist"),
        ("company website", "website"),
        ("https://feeds.example/rss.xml", "rss"),
        ("", "rss"),
        ("my-custom-source", "my-custom-source"),
    ],
)
def test_normalize_source_branches(raw, expected):
    assert sp.normalize_source(raw) == expected


# --- classify_event / classify_for_storage ---


@pytest.mark.operational
def test_classify_event_amount_promotes_funding_over_weaker_label():
    """$ in text + funding keywords should win over a weak product hit."""
    internal, _ = sp.classify_event(
        "Acme launched portal after raising $30 million Series A",
        "techcrunch",
    )
    assert internal == "funding"


@pytest.mark.operational
def test_classify_event_close_scores_prefers_specific_when_above_min():
    text = "BigCo partners with vendor and also ships new integration"
    internal, score = sp.classify_event(text, "rss")
    assert internal in ("partnership", "product_launch", "general")
    assert score >= sp.EVENT_PATTERNS["general"]["min_confidence"]


@pytest.mark.operational
def test_classify_event_weak_winner_falls_back_to_general():
    """No event keywords → general."""
    internal, _ = sp.classify_event("quarterly weather outlook for the region", "rss")
    assert internal == "general"


@pytest.mark.operational
def test_classify_for_storage_never_returns_empty_label():
    label, internal, conf = sp.classify_for_storage("random industry note", "rss")
    assert label == "General News"
    assert internal == "general"
    assert conf > 0


@pytest.mark.operational
def test_url_only_payload_not_forced_unlabeled(operational_db):
    """URL-only raw_signals classify on merged/fallback text (X-05)."""
    import db.connection as db_connection
    from db.schema import init_database

    db_connection._test_db_override = operational_db
    init_database()
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    payload = json.dumps({"url": "https://techcrunch.com/2026/05/startup-raises-series-a"})
    cur.execute(
        """
        INSERT INTO raw_signals (source, signal_type, data_json, processed)
        VALUES ('techcrunch', 'abc123deadbeef', ?, 0)
        """,
        (payload,),
    )
    conn.commit()
    conn.close()
    db_connection._test_db_override = None

    with patch.object(sp, "process_signals", wraps=sp.process_signals):
        stats = sp.process_signals(batch_size=10)

    assert stats["created"] >= 1
    conn = sqlite3.connect(operational_db)
    row = conn.execute(
        "SELECT event_type FROM intelligence_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] != sp.UNLABELED_EVENT_TYPE


# --- extract_amount ---


@pytest.mark.operational
def test_extract_amount_billion_with_commas():
    assert sp.extract_amount("closed $1,250.5 billion round") == 1_250_500_000_000


@pytest.mark.operational
def test_extract_amount_malformed_number_returns_none():
    assert sp.extract_amount("raised $not-a-number million") is None


# --- resolve_company_from_data / fuzzy / aliases ---


@pytest.mark.operational
def test_resolve_company_from_mentioned_companies_list(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('ListCo', 'listco')")
    conn.commit()
    hit = sp.resolve_company_from_data(
        {"mentioned_companies": ["ListCo", "Other"]},
        cur,
    )
    conn.close()
    assert hit is not None
    assert hit[1] == "ListCo"


@pytest.mark.operational
def test_resolve_company_from_channel_company(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('ChannelCo', 'channelco')")
    conn.commit()
    hit = sp.resolve_company_from_data(
        {"channel_company": "ChannelCo"},
        cur,
    )
    conn.close()
    assert hit is not None
    assert hit[1] == "ChannelCo"


@pytest.mark.operational
def test_fuzzy_match_rejects_embedded_token_without_word_boundary(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('Intel Capital', 'intel-capital')")
    conn.commit()
    hit = sp.fuzzy_match_company("Intelligent Systems raises seed", cur)
    conn.close()
    assert hit is None


@pytest.mark.operational
def test_fuzzy_match_substring_in_longer_name(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('Acme Corporation', 'acme')")
    conn.commit()
    hit = sp.fuzzy_match_company("Acme Corporation", cur)
    conn.close()
    assert hit is not None
    assert hit[1] == "Acme Corporation"
    assert hit[2] == 1.0


@pytest.mark.operational
def test_load_aliases_caches_until_cleared(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('CacheCo', 'cacheco')")
    conn.commit()
    sp.load_aliases(cur)
    cur.execute("INSERT INTO companies (name, slug) VALUES ('NewCo', 'newco')")
    conn.commit()
    second = sp.load_aliases(cur)
    assert "newco" not in second
    sp._aliases_loaded = False
    sp.COMPANY_ALIASES.clear()
    third = sp.load_aliases(cur)
    assert "newco" in third
    conn.close()


# --- is_duplicate / link / resolve_source_url ---


@pytest.mark.operational
def test_is_duplicate_requires_company_and_url():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE intelligence_events (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            event_type TEXT,
            source_url TEXT,
            source TEXT,
            announced_date TEXT,
            created_at TEXT
        )
        """
    )
    assert not sp.is_duplicate(cur, "Funding Round", None, "https://x.com")
    assert not sp.is_duplicate(cur, "Funding Round", 1, "")
    conn.close()


@pytest.mark.operational
def test_link_existing_event_skips_raw_signal_pseudo_url(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    assert not sp.link_existing_event_by_url(cur, "raw_signal:99", 99)
    conn.close()


@pytest.mark.operational
def test_link_existing_event_matches_url_with_hash_suffix(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    base = "https://news.example/article"
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (NULL, 'General News', 'rss', ?, NULL, datetime('now'), datetime('now'))
        """,
        (f"{base}#rs5",),
    )
    conn.commit()
    assert sp.link_existing_event_by_url(cur, base, 5)
    conn.close()


@pytest.mark.operational
def test_link_existing_event_refuses_overwrite_different_raw(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    url = "https://news.example/locked"
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (NULL, 'General News', 'rss', ?, 1, datetime('now'), datetime('now'))
        """,
        (url,),
    )
    conn.commit()
    assert not sp.link_existing_event_by_url(cur, url, 2)
    conn.close()


@pytest.mark.operational
def test_resolve_source_url_without_company_uses_rs_suffix():
    url = sp.resolve_source_url({"url": "https://a.com/x"}, 9, None)
    assert url == "https://a.com/x#rs9"


@pytest.mark.operational
def test_resolve_source_url_no_url_uses_raw_signal_pseudo():
    assert sp.resolve_source_url({}, 3, None) == "raw_signal:3"


@pytest.mark.operational
def test_try_link_on_url_conflict_refuses_when_raw_already_set(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    url = "https://news.example/taken"
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (NULL, 'General News', 'rss', ?, 50, datetime('now'), datetime('now'))
        """,
        (url,),
    )
    conn.commit()
    assert not sp._try_link_on_url_conflict(cur, url, 51)
    conn.close()


# --- process_signals / backfill / relink ---


@pytest.mark.operational
def test_process_signals_marks_processed_when_event_already_exists(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('ExistCo', 'existco')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 0)
        """,
        (cid, json.dumps({"title": "ExistCo update", "url": "https://ex.com/e1"})),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (
            ?, 'General News', 'rss', 'https://ex.com/e1#rs99', ?,
            datetime('now'), datetime('now')
        )
        """,
        (cid, sid),
    )
    conn.commit()
    conn.close()

    result = sp.process_signals(batch_size=5)
    assert result["created"] == 0

    conn = sqlite3.connect(operational_db)
    proc = conn.execute("SELECT processed FROM raw_signals WHERE id = ?", (sid,)).fetchone()[0]
    conn.close()
    assert proc == 1


@pytest.mark.operational
def test_process_signals_research_publication_label(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('LabCo', 'labco')")
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 0)
        """,
        (
            cid,
            json.dumps(
                {
                    "title": "LabCo publishes arxiv benchmark on reasoning models",
                    "url": "https://labco.com/paper",
                }
            ),
        ),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()

    sp.process_signals(batch_size=5)

    conn = sqlite3.connect(operational_db)
    row = conn.execute(
        "SELECT event_type FROM intelligence_events WHERE raw_signal_id = ?",
        (sid,),
    ).fetchone()
    conn.close()
    assert row[0] == "Research Publication"


@pytest.mark.operational
def test_backfill_stops_after_three_stall_batches(operational_db, monkeypatch):
    """Three batches with work but zero new events triggers stall guard."""
    calls = {"n": 0}

    def stall_process(batch_size=100):
        calls["n"] += 1
        return {"processed": 5, "created": 0, "skipped": 0}

    monkeypatch.setattr(sp, "process_signals", stall_process)
    total = sp.backfill_all_signals(max_batches=10)
    assert calls["n"] == 3
    assert total["batches"] == 3
    assert total["created"] == 0


@pytest.mark.operational
def test_relink_orphan_no_candidates(operational_db):
    stats = sp.relink_orphan_companies(batch_size=10)
    assert stats["candidates"] == 0
    assert stats["updated"] == 0


@pytest.mark.operational
def test_process_all_signals_delegates_to_process_signals(operational_db):
    with patch.object(
        sp, "process_signals", return_value={"processed": 1, "created": 0, "skipped": 0}
    ) as mock:
        out = sp.process_all_signals(batch_size=7)
    mock.assert_called_once_with(batch_size=7)
    assert out["processed"] == 1


@pytest.mark.operational
def test_run_returns_created_count(operational_db):
    with patch.object(
        sp, "process_signals", return_value={"processed": 2, "created": 3, "skipped": 0}
    ):
        assert sp.run(batch_size=50) == 3
