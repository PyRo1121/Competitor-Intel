"""Company data claims pipeline (profile / team / products)."""

from __future__ import annotations

import sqlite3

import pytest
from collectors.enrichment.company_data import extract_website as ew
from collectors.enrichment.company_data.aggregate import run_all_aggregators
from collectors.enrichment.company_data.claims import upsert_profile_claim, upsert_team_claim
from collectors.enrichment.company_data.extract_signals import extract_from_events


@pytest.fixture
def co_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            name TEXT,
            website TEXT,
            github_org TEXT,
            industry TEXT,
            status TEXT,
            score REAL,
            notes TEXT,
            last_updated_at TEXT
        );
        CREATE TABLE company_profile_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            field_key TEXT NOT NULL,
            field_value TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            extracted_at TEXT NOT NULL,
            UNIQUE(source_url, field_key)
        );
        CREATE TABLE team_member_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            role TEXT,
            is_founder INTEGER DEFAULT 0,
            joined_date TEXT,
            linkedin_url TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            extracted_at TEXT NOT NULL
        );
        CREATE TABLE product_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT DEFAULT 'active',
            product_url TEXT,
            launch_date TEXT,
            pricing_json TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            raw_signal_id INTEGER,
            extracted_at TEXT NOT NULL
        );
        CREATE TABLE license_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            jurisdiction TEXT NOT NULL,
            license_type TEXT NOT NULL,
            status TEXT NOT NULL,
            regulator TEXT,
            license_number TEXT,
            effective_date TEXT,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL UNIQUE,
            source_tier TEXT NOT NULL,
            source_weight REAL NOT NULL,
            is_official INTEGER DEFAULT 0,
            extraction_confidence REAL,
            headline TEXT,
            snippet TEXT,
            intelligence_event_id INTEGER,
            extracted_at TEXT NOT NULL
        );
        CREATE TABLE company_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL UNIQUE,
            founded_year INTEGER,
            headquarters TEXT,
            team_size INTEGER,
            team_size_source TEXT,
            business_model TEXT,
            tech_stack TEXT,
            description_long TEXT,
            traction TEXT,
            moat TEXT,
            fields_provenance TEXT,
            last_enriched_at TEXT
        );
        CREATE TABLE team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT,
            role TEXT,
            is_founder INTEGER DEFAULT 0,
            joined_date TEXT,
            left_date TEXT,
            source TEXT,
            linkedin_url TEXT,
            source_url TEXT,
            corroboration_score REAL,
            report_count INTEGER,
            fields_provenance TEXT,
            extracted_at TEXT
        );
        CREATE UNIQUE INDEX idx_team_norm ON team_members(company_id, name_normalized);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT,
            description TEXT,
            category TEXT,
            pricing_json TEXT,
            launch_date TEXT,
            status TEXT,
            source TEXT,
            url TEXT,
            corroboration_score REAL,
            report_count INTEGER,
            fields_provenance TEXT,
            extracted_at TEXT
        );
        CREATE UNIQUE INDEX idx_prod_norm ON products(company_id, name_normalized);
        CREATE TABLE regulatory_licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            jurisdiction TEXT NOT NULL,
            license_type TEXT NOT NULL,
            status TEXT NOT NULL,
            regulator TEXT,
            license_number TEXT,
            effective_date TEXT,
            corroboration_score REAL,
            report_count INTEGER,
            fields_provenance TEXT,
            updated_at TEXT,
            UNIQUE(company_id, jurisdiction, license_type)
        );
        """
    )
    conn.execute("INSERT INTO companies (id, name, website) VALUES (1, 'Acme', 'https://acme.com')")
    yield conn
    conn.close()


def test_profile_claim_aggregates(co_db):
    upsert_profile_claim(
        co_db,
        company_id=1,
        field_key="founded_year",
        field_value="2020",
        source="press",
        source_url="https://techcrunch.com/acme-profile#founded",
    )
    upsert_profile_claim(
        co_db,
        company_id=1,
        field_key="founded_year",
        field_value="2021",
        source="blog",
        source_url="https://acme.com/about#founded",
        company_website="https://acme.com",
    )
    stats = run_all_aggregators(co_db)
    assert stats["company_details"] == 1
    row = co_db.execute(
        "SELECT founded_year, fields_provenance FROM company_details WHERE company_id = 1"
    ).fetchone()
    assert row["founded_year"] in (2020, 2021)
    assert row["fields_provenance"]


def test_team_claims_merge(co_db):
    upsert_team_claim(
        co_db,
        company_id=1,
        name="Jane Doe",
        role="CEO",
        source="press",
        source_url="https://reuters.com/acme-ceo",
    )
    upsert_team_claim(
        co_db,
        company_id=1,
        name="Jane Doe",
        role="Chief Executive Officer",
        source="blog",
        source_url="https://ft.com/acme-ceo",
    )
    stats = run_all_aggregators(co_db)
    assert stats["team_members"] == 1
    tm = co_db.execute("SELECT * FROM team_members WHERE company_id = 1").fetchone()
    assert tm["report_count"] == 2
    assert tm["corroboration_score"] > 0.3


def test_extract_from_events_uses_raw_signal_json(co_db):
    co_db.executescript(
        """
        CREATE TABLE intelligence_events (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            event_type TEXT,
            description TEXT,
            source TEXT,
            source_url TEXT,
            announced_date TEXT,
            raw_signal_id INTEGER
        );
        CREATE TABLE raw_signals (
            id INTEGER PRIMARY KEY,
            data_json TEXT
        );
        """
    )
    co_db.execute(
        "INSERT INTO raw_signals (id, data_json) VALUES (1, ?)",
        (
            '{"title": "Acme names Jane Doe as CEO", '
            '"summary": "Jane Doe appointed Chief Executive Officer effective Monday."}',
        ),
    )
    co_db.execute(
        """
        INSERT INTO intelligence_events (
            id, company_id, event_type, description, source, source_url,
            announced_date, raw_signal_id
        ) VALUES (1, 1, 'Hiring', '', 'press', 'https://example.com/acme-ceo', '2026-05-01', 1)
        """
    )
    co_db.commit()
    stats = extract_from_events(co_db)
    assert stats["team_claims"] >= 1
    n = co_db.execute("SELECT COUNT(*) FROM team_member_claims").fetchone()[0]
    assert n >= 1


def test_website_extraction_batches_all_companies(co_db, monkeypatch):
    for i in range(2, 16):
        co_db.execute(
            "INSERT INTO companies (id, name, website, status, score) "
            "VALUES (?, ?, ?, 'active', ?)",
            (i, f"Co{i}", f"https://co{i}.example", float(100 - i)),
        )
    co_db.commit()
    calls: list[int] = []

    def fake_extract(conn, company_id, name, website, github_org):
        calls.append(company_id)
        return {"profile_claims": 0, "team_claims": 0, "product_claims": 0}

    monkeypatch.setattr(ew, "extract_company_website", fake_extract)
    monkeypatch.setattr(ew, "close_http_client", lambda: None)

    stats = ew.run_website_extraction(co_db, batch_size=10)
    assert stats["companies"] == 15
    assert stats["batches"] == 2
    assert len(calls) == 15
