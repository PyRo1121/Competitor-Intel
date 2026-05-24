"""Regulatory license extraction (Track 4 P4-5)."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.enrichment.company_data.regulatory_extract import (
    extract_regulatory_license_claims,
)


@pytest.fixture
def reg_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            website TEXT,
            slug TEXT,
            industry TEXT,
            status TEXT
        );
        CREATE TABLE raw_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            source TEXT,
            signal_type TEXT,
            data_json TEXT,
            detected_at TEXT
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
        """
    )
    conn.execute(
        "INSERT INTO companies (id, name, slug, industry, status) "
        "VALUES (1, 'Acme Pay', 'acme-pay', 'fintech', 'active')"
    )
    yield conn
    conn.close()


def test_form_d_bulk_creates_license_claim(reg_db):
    payload = {
        "kind": "form_d_bulk",
        "entity_name": "Acme Pay Inc",
        "entity_type": "Corporation",
        "jurisdiction": "DE",
        "cik": "0001234567",
        "total_offering_amount": "5000000",
        "total_amount_sold": "1000000",
        "url": "https://www.sec.gov/cgi-bin/browse-edgar",
    }
    reg_db.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
        VALUES (1, 'sec_edgar', 'x', ?, '2026-01-01')
        """,
        (json.dumps(payload),),
    )
    stats = extract_regulatory_license_claims(reg_db)
    assert stats["license_claims"] >= 1
    row = reg_db.execute(
        "SELECT license_type, regulator, jurisdiction FROM license_claims WHERE company_id = 1"
    ).fetchone()
    assert row is not None
    assert "Form D" in row["license_type"]
    assert row["regulator"] == "SEC"
    assert row["jurisdiction"] == "US"


def test_regulatory_rss_creates_license_claim(reg_db):
    payload = {
        "kind": "rss_blog",
        "category": "regulatory",
        "title": "FCA authorizes Acme Pay as payment institution",
        "summary": "The FCA has authorized Acme Pay to operate as a payment institution in the UK.",
        "url": "https://fca.example/news/1",
        "link": "https://fca.example/news/1",
    }
    reg_db.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
        VALUES (1, 'FCA News', 'rss', ?, '2026-01-02')
        """,
        (json.dumps(payload),),
    )
    stats = extract_regulatory_license_claims(reg_db)
    assert stats["license_claims"] >= 1
    assert stats["rss_regulatory_scanned"] >= 1
