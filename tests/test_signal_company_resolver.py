"""Tests for signal_company_resolver."""

from __future__ import annotations

import sqlite3

import pytest
from collectors import signal_company_resolver as scr
from collectors.signal_processor import fuzzy_match_company, resolve_company_from_data


@pytest.mark.operational
def test_extract_domain():
    assert scr.extract_domain("https://www.anthropic.com/news/foo") == "anthropic.com"
    assert scr.extract_domain("") is None


@pytest.mark.operational
def test_resolve_from_url(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO companies (name, slug, website) VALUES ('Acme AI', 'acme-ai', 'https://acme.ai')"
    )
    conn.commit()
    index = scr.build_domain_index(cur)
    hit = scr.resolve_from_url("https://acme.ai/blog/launch", index)
    conn.close()
    assert hit is not None
    assert hit[1] == "Acme AI"


@pytest.mark.operational
def test_resolve_from_github_url(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies (name, slug, github_org)
        VALUES ('GitCo', 'gitco', 'gitco')
        """
    )
    conn.commit()
    index = scr.build_domain_index(cur)
    hit = scr.resolve_from_github_url("https://github.com/gitco/repo", index)
    conn.close()
    assert hit is not None
    assert hit[1] == "GitCo"


@pytest.mark.operational
def test_resolve_company_enhanced_title_blob(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('BlobMatch Inc', 'blobmatch-inc')")
    conn.commit()
    hit = scr.resolve_company_enhanced(
        {"title": "BlobMatch Inc expands into payments"},
        cur,
        fuzzy_match_fn=fuzzy_match_company,
        resolve_from_data_fn=resolve_company_from_data,
    )
    conn.close()
    assert hit is not None
    assert hit[1] == "BlobMatch Inc"
