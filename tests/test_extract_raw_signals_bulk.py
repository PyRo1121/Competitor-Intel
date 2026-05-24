"""Claim extraction from bulk regulatory / directory raw_signals."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.enrichment.company_data.extract_raw_signals import extract_from_raw_signals


@pytest.fixture
def raw_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            name TEXT,
            website TEXT
        );
        CREATE TABLE raw_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            source TEXT,
            signal_type TEXT,
            data_json TEXT,
            detected_at TEXT
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
        """
    )
    conn.execute(
        "INSERT INTO companies (id, name, website) VALUES (1, 'Stripe', 'https://stripe.com')"
    )
    yield conn
    conn.close()


def test_form_d_bulk_extracts_profile_and_team(raw_db):
    payload = {
        "kind": "form_d_bulk",
        "entity_name": "Stripe Payments Inc",
        "entity_type": "Corporation",
        "headquarters": "San Francisco, CA",
        "jurisdiction": "DE",
        "year_of_inc": "2010",
        "total_offering_amount": "1000000",
        "related_persons": [{"name": "Jane Doe", "relationship": "Executive Officer"}],
        "url": "https://www.sec.gov/example",
    }
    raw_db.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
        VALUES (1, 'sec_edgar', 'form_d_bulk_x', ?, '2026-01-01')
        """,
        (json.dumps(payload),),
    )
    stats = extract_from_raw_signals(raw_db)
    assert stats["profile_claims"] >= 1
    assert stats["team_claims"] == 1


def test_esma_mica_license_claim(raw_db):
    payload = {
        "kind": "mica_casp",
        "commercial_name": "Stripe",
        "lei": "LEI123",
        "home_member_state": "IE",
        "regulator": "Central Bank",
        "services": "custody",
        "authorisation_date": "01/01/2025",
        "url": "https://stripe.com",
    }
    raw_db.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
        VALUES (1, 'esma_mica', 'mica_stripe', ?, '2026-01-01')
        """,
        (json.dumps(payload),),
    )
    stats = extract_from_raw_signals(raw_db)
    assert stats["license_claims"] == 1
