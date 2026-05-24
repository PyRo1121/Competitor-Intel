"""Multi-source funding claims and corroboration aggregation."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.enrichment import funding_enricher as fe
from collectors.enrichment.funding_source_trust import classify_source, domain_matches_company
from db.migrations import apply_runtime_migrations


def test_company_official_source_tier():
    tier, weight, official = classify_source(
        "website",
        "https://acme.com/blog/series-b",
        company_website="https://www.acme.com",
    )
    assert tier == "company_official"
    assert official is True
    assert weight >= 0.99


def test_domain_matches_company_subdomain():
    assert domain_matches_company("blog.acme.com", "acme.com")


def test_startup_press_classified_tier1():
    tier, weight, _ = classify_source(
        "EU Startups",
        "https://www.eu-startups.com/2026/05/example/",
    )
    assert tier == "tier1_media"
    assert weight >= 0.72


@pytest.mark.operational
def test_two_outlets_one_canonical_round(operational_db):
    conn = sqlite3.connect(operational_db)
    apply_runtime_migrations(conn)
    conn.commit()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO companies (name, slug, website) VALUES ('MultiSrc', 'multisrc', 'https://multisrc.io')"
    )
    cid = cur.lastrowid
    for src, url in (
        ("techcrunch", "https://techcrunch.com/multisrc-series-a"),
        ("rss", "https://news.example/multisrc-series-a-2"),
    ):
        cur.execute(
            """
            INSERT INTO intelligence_events
            (company_id, event_type, amount_usd, source, source_url, description,
             announced_date, created_at)
            VALUES (?, 'Funding Round', 12000000, ?, ?, ?, date('now'), datetime('now'))
            """,
            (
                cid,
                src,
                url,
                "MultiSrc raises $12 million Series A led by Sequoia",
            ),
        )
    conn.commit()
    conn.close()

    result = fe.extract_from_signals()
    assert result["claims_created"] >= 2

    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    rounds = conn.execute("SELECT * FROM funding_rounds WHERE company_id = ?", (cid,)).fetchall()
    claims = conn.execute(
        "SELECT * FROM funding_round_claims WHERE company_id = ?", (cid,)
    ).fetchall()
    conn.close()

    assert len(claims) >= 2
    assert len(rounds) == 1
    assert rounds[0]["report_count"] >= 2
    assert rounds[0]["corroboration_score"] is not None
    assert float(rounds[0]["corroboration_score"]) > 0.4

    prov = json.loads(rounds[0]["fields_provenance"] or "{}")
    assert "amount_usd" in prov
    assert prov["amount_usd"]["reports"] >= 1
    assert "investors" in prov
    assert "Sequoia" in prov["investors"]


@pytest.mark.operational
def test_official_source_boosts_score(operational_db):
    conn = sqlite3.connect(operational_db)
    apply_runtime_migrations(conn)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO companies (name, slug, website) VALUES ('OfficialCo', 'officialco', 'https://officialco.com')"
    )
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         announced_date, created_at)
        VALUES (?, 'Funding Round', 5000000, 'website', 'https://officialco.com/news/seed',
                'OfficialCo announces $5M seed round', date('now'), datetime('now'))
        """,
        (cid,),
    )
    conn.commit()
    conn.close()

    fe.extract_from_signals()
    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT official_report_count, corroboration_score "
        "FROM funding_rounds WHERE company_id = ?",
        (cid,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["official_report_count"] >= 1
    assert float(row["corroboration_score"]) >= 0.55


@pytest.mark.operational
def test_round_participants_linked(operational_db):
    conn = sqlite3.connect(operational_db)
    apply_runtime_migrations(conn)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO companies (name, slug, website) VALUES ('PartCo', 'partco', 'https://partco.com')"
    )
    cid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         announced_date, created_at)
        VALUES (?, 'Funding Round', 8000000, 'techcrunch', 'https://tc.com/partco-a',
                'PartCo raises $8M Series A led by Sequoia with Index participating',
                date('now'), datetime('now'))
        """,
        (cid,),
    )
    conn.commit()
    conn.close()

    fe.extract_from_signals()
    conn = sqlite3.connect(operational_db)
    conn.row_factory = sqlite3.Row
    parts = conn.execute(
        """
        SELECT rp.*, i.name FROM round_participants rp
        JOIN investor_firms i ON i.id = rp.investor_id
        JOIN funding_rounds fr ON fr.id = rp.funding_round_id
        WHERE fr.company_id = ?
        """,
        (cid,),
    ).fetchall()
    conn.close()
    assert len(parts) >= 2
    leads = [p for p in parts if p["is_lead"]]
    assert len(leads) >= 1


@pytest.mark.operational
def test_company_claim_tables(operational_db: str) -> None:
    """Team/product/license claim tables accept company-data rollup rows."""
    conn = sqlite3.connect(operational_db)
    cid = conn.execute(
        "INSERT INTO companies (name, slug, industry, status) VALUES (?, ?, ?, ?)",
        ("ClaimCo", "claimco", "AI", "active"),
    ).lastrowid
    conn.execute(
        """
        INSERT INTO team_member_claims (
            company_id, name, name_normalized, role, source, source_url,
            source_tier, source_weight, extracted_at
        ) VALUES (?, 'Jane Doe', 'jane-doe', 'CEO', 'test', 'https://example.com/claimco-team',
                  'press', 0.7, datetime('now'))
        """,
        (cid,),
    )
    conn.commit()
    n = conn.execute(
        "SELECT COUNT(*) FROM team_member_claims WHERE company_id = ?", (cid,)
    ).fetchone()[0]
    conn.close()
    assert n == 1
