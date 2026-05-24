"""Unit tests for signal_processor classification and matching."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors import signal_processor as sp


@pytest.mark.operational
def test_levenshtein_edge_cases():
    assert sp.levenshtein("", "abc") == 0.0
    assert sp.levenshtein("same", "same") == 1.0
    assert 0.0 < sp.levenshtein("acme", "acme corp") < 1.0


@pytest.mark.operational
def test_keyword_matches_word_boundary():
    assert sp._keyword_matches("round closed for funding", "closed")
    assert not sp._keyword_matches("enclosed warehouse", "closed")


@pytest.mark.operational
@pytest.mark.parametrize(
    "text,expected",
    [
        ("OpenAI launches new reasoning API for developers", "Product Launch"),
        ("Stripe partners with Shopify on embedded payments", "Partnership"),
        ("Meta acquires small AI startup for undisclosed sum", "Acquisition"),
        ("Anthropic hires former Google research lead as CTO", "Hiring"),
    ],
)
def test_classify_for_storage_golden_headlines(text, expected):
    label, _, _ = sp.classify_for_storage(text, "rss")
    assert label == expected


@pytest.mark.operational
def test_classify_event_funding_and_general():
    event, score = sp.classify_event(
        "Startup raises $50 million Series B led by Sequoia",
        "techcrunch",
    )
    assert event == "funding"
    assert score >= sp.EVENT_PATTERNS["funding"]["min_confidence"]

    general, low = sp.classify_event("weather report today", "rss")
    assert general == "general"
    assert low >= sp.EVENT_PATTERNS["general"]["min_confidence"]


@pytest.mark.operational
def test_parse_signal_data_accepts_python_repr():
    payload = "{'title': 'Acme raises $5M', 'url': 'https://example.com/a'}"
    data = sp.parse_signal_data(payload)
    assert data["title"] == "Acme raises $5M"


@pytest.mark.operational
def test_normalize_source_maps_feed_names():
    assert sp.normalize_source("TechCrunch Startups") == "techcrunch"
    assert sp.normalize_source("https://techcrunch.com/feed/") == "techcrunch"


@pytest.mark.operational
def test_event_type_label_maps_dashboard_strings():
    assert sp.event_type_label("funding") == "Funding Round"
    assert sp.event_type_label("unknown_type") == "Unknown Type"


@pytest.mark.operational
def test_extract_amount_variants():
    assert sp.extract_amount("raised $2.5 billion") == 2_500_000_000
    assert sp.extract_amount("closes $12 million round") == 12_000_000
    assert sp.extract_amount("$50,000") is None  # below 100k threshold for bare $
    assert sp.extract_amount("$2,000,000 seed") == 2_000_000
    assert sp.extract_amount("no money here") is None


@pytest.mark.operational
def test_fuzzy_match_and_resolve_company(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO companies (name, slug, x_handle) VALUES (?, ?, ?)",
        ("Globex AI", "globex-ai", "@globexai"),
    )
    conn.commit()

    matched = sp.fuzzy_match_company("Globex AI", cur)
    assert matched is not None
    assert matched[1] == "Globex AI"
    assert matched[2] == 1.0

    resolved = sp.resolve_company_from_data(
        {"title": "Globex AI launches new API", "channel_company": "Globex AI"},
        cur,
    )
    assert resolved is not None
    conn.close()


@pytest.mark.operational
def test_is_duplicate_within_window(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('DupCo', 'dupco')")
    company_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source_url, source, announced_date, created_at)
        VALUES (?, 'Funding Round', 'https://x.example/a', 'rss', datetime('now'), datetime('now'))
        """,
        (company_id,),
    )
    conn.commit()
    assert sp.is_duplicate(cur, "Funding Round", company_id, "https://x.example/a")
    assert not sp.is_duplicate(cur, "Funding Round", company_id, "https://x.example/b")
    conn.close()


@pytest.mark.operational
def test_process_signals_creates_general_news(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('NewsCo', 'newsco')")
    company_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 0)
        """,
        (
            company_id,
            json.dumps({"title": "Industry outlook for Q3", "url": "https://example.com/q3"}),
        ),
    )
    sig_id = cur.lastrowid
    conn.commit()
    conn.close()

    result = sp.process_signals(batch_size=5)
    assert result["created"] >= 1

    conn = sqlite3.connect(operational_db)
    row = conn.execute(
        "SELECT event_type, company_id FROM intelligence_events WHERE raw_signal_id = ?",
        (sig_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "General News"
    assert row[1] == company_id


@pytest.mark.operational
def test_resolve_company_from_title_token(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('TitleMatch Labs', 'titlematch-labs')")
    conn.commit()
    resolved = sp.resolve_company_from_data(
        {"title": "TitleMatch Labs announces partnership with BigCo"},
        cur,
    )
    assert resolved is not None
    assert resolved[1] == "TitleMatch Labs"
    conn.close()


@pytest.mark.operational
def test_fuzzy_match_returns_none_for_garbage(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    assert sp.fuzzy_match_company("x", cur) is None
    assert sp.fuzzy_match_company("zzzznotacompany", cur) is None
    conn.close()


@pytest.mark.operational
def test_link_existing_event_by_url(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('LinkCo', 'linkco')")
    cid = cur.lastrowid
    url = "https://news.example/link"
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, announced_date, created_at)
        VALUES (?, 'Funding Round', 'rss', ?, datetime('now'), datetime('now'))
        """,
        (cid, url),
    )
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 1)
        """,
        (cid, json.dumps({"title": "ignored", "url": url})),
    )
    sig_id = cur.lastrowid
    assert sig_id is not None
    conn.commit()
    assert sp.link_existing_event_by_url(cur, url, int(sig_id))
    conn.commit()
    row = cur.execute(
        "SELECT raw_signal_id FROM intelligence_events WHERE source_url = ?", (url,)
    ).fetchone()
    assert row[0] == sig_id
    conn.close()


@pytest.mark.operational
def test_resolve_source_url_suffix_per_company(operational_db):
    data = {"url": "https://news.example/shared"}
    cid = 42
    url = sp.resolve_source_url(data, 7, cid)
    assert url == "https://news.example/shared#c42-rs7"


@pytest.mark.operational
def test_process_signals_empty_payload_classifies_as_general_news(operational_db):
    """Empty JSON gets fallback text (X-05) and should not remain Unlabeled Signal."""
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO raw_signals (source, signal_type, data_json, processed)
        VALUES ('rss', 'abc123hash', '{}', 0)
        """
    )
    sig_id = cur.lastrowid
    conn.commit()
    conn.close()

    result = sp.process_signals(batch_size=5)
    assert result["created"] >= 1

    conn = sqlite3.connect(operational_db)
    row = conn.execute(
        "SELECT event_type FROM intelligence_events WHERE raw_signal_id = ?",
        (sig_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "General News"
    assert row[0] != sp.UNLABELED_EVENT_TYPE


@pytest.mark.operational
def test_process_signals_creates_event_when_url_already_used(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('DupEv', 'dupev')")
    cid = cur.lastrowid
    url = "https://news.example/dup"
    payload = json.dumps(
        {
            "title": "DupEv raises $10 million Series A from investors",
            "url": url,
        }
    )
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'techcrunch', 'funding', ?, 0)
        """,
        (cid, payload),
    )
    sig_id = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (?, 'Funding Round', 'techcrunch', ?, NULL, datetime('now'), datetime('now'))
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
    conn.close()
    assert linked == sig_id


@pytest.mark.operational
def test_try_link_on_url_conflict_updates_null_raw_signal_id(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    url = "https://news.example/conflict-exact"
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, announced_date, created_at)
        VALUES (NULL, 'General News', 'rss', ?, NULL, datetime('now'), datetime('now'))
        """,
        (url,),
    )
    conn.commit()
    assert sp._try_link_on_url_conflict(cur, url, 99)
    conn.commit()
    row = cur.execute(
        "SELECT raw_signal_id FROM intelligence_events WHERE source_url = ?", (url,)
    ).fetchone()
    conn.close()
    assert row[0] == 99
