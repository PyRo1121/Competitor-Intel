"""Claim extraction from bulk regulatory / directory raw_signals."""

from __future__ import annotations

import json
import sqlite3

import pytest
from collectors.enrichment.company_data.extract_raw_signals import extract_from_raw_signals

from tests.fixtures.minimal_schemas import apply_claims_ingest_schema


@pytest.fixture
def raw_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_claims_ingest_schema(conn)
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
