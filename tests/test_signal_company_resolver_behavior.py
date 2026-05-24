"""Behavior tests for signal_company_resolver — resolution order and URL edge cases."""

from __future__ import annotations

import sqlite3

import pytest
from collectors import signal_company_resolver as scr
from collectors.signal_processor import fuzzy_match_company, resolve_company_from_data


@pytest.mark.operational
def test_extract_domain_adds_scheme_and_strips_www():
    assert scr.extract_domain("acme.ai") == "acme.ai"
    assert scr.extract_domain("https://www.acme.ai/path") == "acme.ai"


@pytest.mark.operational
def test_extract_domain_invalid_returns_none():
    assert scr.extract_domain("   ") is None


@pytest.mark.operational
def test_resolve_from_url_two_part_registrable_domain(operational_db):
    """Subdomain not in index can match base domain when indexed."""
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies (name, slug, website)
        VALUES ('BaseCo', 'baseco', 'https://baseco.com')
        """
    )
    conn.commit()
    index = scr.build_domain_index(cur)
    hit = scr.resolve_from_url("https://blog.baseco.com/post", index)
    conn.close()
    assert hit is not None
    assert hit[1] == "BaseCo"


@pytest.mark.operational
def test_build_domain_index_slug_suffixes(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug, website) VALUES ('SlugCo', 'slugco', NULL)")
    conn.commit()
    index = scr.build_domain_index(cur)
    conn.close()
    assert "slugco.com" in index
    assert index["slugco.com"][1] == "SlugCo"


@pytest.mark.operational
def test_resolve_from_github_url_no_match():
    assert scr.resolve_from_github_url("https://github.com/unknown/repo", {}) is None
    assert scr.resolve_from_github_url("https://example.com/not-github", {}) is None


@pytest.mark.operational
def test_resolve_company_enhanced_prefers_explicit_company_id(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('IdCo', 'idco')")
    cid = cur.lastrowid
    conn.commit()
    hit = scr.resolve_company_enhanced(
        {"company_id": cid, "title": "Unrelated headline"},
        cur,
        fuzzy_match_fn=fuzzy_match_company,
        resolve_from_data_fn=resolve_company_from_data,
    )
    conn.close()
    assert hit == (cid, "IdCo", 1.0)


@pytest.mark.operational
def test_resolve_company_enhanced_company_name_string(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('NameCo', 'nameco')")
    conn.commit()
    hit = scr.resolve_company_enhanced(
        {"company": "NameCo"},
        cur,
        fuzzy_match_fn=fuzzy_match_company,
        resolve_from_data_fn=resolve_company_from_data,
    )
    conn.close()
    assert hit is not None
    assert hit[1] == "NameCo"


@pytest.mark.operational
def test_resolve_company_enhanced_url_beats_title_fuzzy(operational_db):
    """Domain on article URL should win before title-only fuzzy."""
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies (name, slug, website)
        VALUES ('UrlWin', 'urlwin', 'https://urlwin.io'),
               ('OtherCo', 'otherco', NULL)
        """
    )
    conn.commit()
    hit = scr.resolve_company_enhanced(
        {
            "title": "OtherCo announces something unrelated",
            "url": "https://urlwin.io/press/release",
        },
        cur,
        fuzzy_match_fn=fuzzy_match_company,
        resolve_from_data_fn=resolve_company_from_data,
    )
    conn.close()
    assert hit is not None
    assert hit[1] == "UrlWin"


@pytest.mark.operational
def test_resolve_company_enhanced_short_title_skips_fuzzy_tail(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('Short', 'short')")
    conn.commit()
    hit = scr.resolve_company_enhanced(
        {"title": "Hi"},
        cur,
        fuzzy_match_fn=fuzzy_match_company,
        resolve_from_data_fn=resolve_company_from_data,
    )
    conn.close()
    assert hit is None
