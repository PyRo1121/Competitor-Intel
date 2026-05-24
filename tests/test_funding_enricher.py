"""Tests for structured funding extraction."""

from __future__ import annotations

import sqlite3

import pytest
from collectors.enrichment import funding_enricher as fe


@pytest.mark.operational
def test_extract_round_type_series_b():
    rt, conf = fe.extract_round_type("Startup closes $12M Series B led by Sequoia")
    assert rt == "Series B"
    assert conf >= 0.8


@pytest.mark.operational
def test_extract_investors_led_by():
    lead, co = fe.extract_investors("Round led by Accel with participation from Index")
    assert lead == "Accel"


@pytest.mark.operational
def test_extract_investors_raises_from_list():
    lead, co = fe.extract_investors(
        "Startup raises $20M Series A from Sequoia, Andreessen Horowitz and Index Ventures"
    )
    assert lead == "Sequoia"
    assert "Andreessen Horowitz" in co


@pytest.mark.operational
def test_extract_investors_co_led():
    lead, co = fe.extract_investors(
        "Acme closes $50M Series C co-led by Sequoia and Andreessen Horowitz"
    )
    assert lead == "Sequoia"
    assert "Andreessen Horowitz" in co


@pytest.mark.operational
def test_extract_deal_fields_safe():
    deal = fe.extract_deal_fields("Startup raises $5M on a SAFE at $40M pre-money valuation")
    assert deal["instrument_type"] == "safe"
    assert deal["pre_money_valuation_usd"] == 40_000_000


@pytest.mark.operational
def test_apply_structured_funding_enrichment(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('EnrichCo', 'enrichco')")
    cid = cur.lastrowid
    url = "https://news.example/enrichco-series-b"
    cur.execute(
        """
        INSERT INTO funding_round_claims
        (company_id, round_type, source, source_url, source_tier, source_weight, headline)
        VALUES (?, 'Series B', 'rss', ?, 'tier_2_news', 0.7, 'EnrichCo raises funding')
        """,
        (cid, url),
    )
    claim_id = cur.lastrowid
    conn.commit()
    conn.close()

    ok = fe.apply_structured_funding_enrichment(
        {
            "claim_id": claim_id,
            "lead_investor": "Benchmark",
            "co_investors": ["Index Ventures"],
            "amount_usd": 25_000_000,
            "instrument_type": "equity",
        }
    )
    assert ok is True

    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    claim = conn.execute(
        "SELECT lead_investor, amount_usd FROM funding_round_claims WHERE id = ?",
        (claim_id,),
    ).fetchone()
    parts = conn.execute(
        "SELECT investor_name_raw FROM funding_claim_participants WHERE funding_round_claim_id = ?",
        (claim_id,),
    ).fetchall()
    conn.close()
    assert claim["lead_investor"] == "Benchmark"
    assert claim["amount_usd"] == 25_000_000
    assert len(parts) >= 2


@pytest.mark.operational
def test_extract_from_events_creates_round(operational_db):
    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('FundedCo', 'fundedco')")
    cid = cur.lastrowid
    url = "https://news.example/fundedco-series-a"
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         announced_date, created_at)
        VALUES (?, 'Funding Round', 10000000, 'techcrunch', ?, ?, date('now'), datetime('now'))
        """,
        (
            cid,
            url,
            "FundedCo raises $10 million Series A led by Benchmark",
        ),
    )
    conn.commit()
    conn.close()

    result = fe.extract_from_signals()
    assert result["created"] >= 1

    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT round_type, amount_usd, lead_investor, source_url "
        "FROM funding_rounds WHERE source_url = ?",
        (url,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["amount_usd"] == 10_000_000
    assert row["source_url"] == url


@pytest.mark.operational
def test_store_skips_duplicate_source_url(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('DupFund', 'dupfund')")
    cid = cur.lastrowid
    conn.commit()
    conn.close()

    payload = {
        "company_id": cid,
        "round_type": "Series A",
        "amount_usd": 5_000_000,
        "valuation_usd": None,
        "lead_investor": "VC",
        "co_investors": None,
        "source": "rss",
        "source_url": "https://news.example/dup-fund",
        "confidence": 0.8,
        "announced_date": "2026-01-01",
    }
    claim_id, is_new = fe.store_funding_claim(payload)
    assert claim_id and is_new
    claim_id2, is_new2 = fe.store_funding_claim(payload)
    assert claim_id2 == claim_id and not is_new2

    conn = sqlite3.connect(operational_db)
    n = conn.execute(
        "SELECT COUNT(*) FROM funding_round_claims WHERE source_url = ?",
        (payload["source_url"],),
    ).fetchone()[0]
    conn.close()
    assert n == 1
