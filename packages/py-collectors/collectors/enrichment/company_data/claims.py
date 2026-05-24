"""Upsert company-data claims with source tier + weight (funding-style traceability)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from collectors.enrichment.funding_source_trust import classify_source

logger = logging.getLogger("company_data.claims")


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def upsert_profile_claim(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    field_key: str,
    field_value: str,
    source: str,
    source_url: str,
    headline: str | None = None,
    snippet: str | None = None,
    intelligence_event_id: int | None = None,
    raw_signal_id: int | None = None,
    extraction_confidence: float = 0.65,
    company_website: str | None = None,
) -> tuple[int | None, bool]:
    tier, weight, is_official = classify_source(source, source_url, company_website=company_website)
    now = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM company_profile_claims WHERE source_url = ? AND field_key = ?",
        (source_url, field_key),
    )
    existed = cur.fetchone() is not None
    cur.execute(
        """
        INSERT INTO company_profile_claims (
            company_id, field_key, field_value, source, source_url,
            source_tier, source_weight, is_official, extraction_confidence,
            headline, snippet, intelligence_event_id, raw_signal_id, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url, field_key) DO UPDATE SET
            field_value = excluded.field_value,
            source_tier = excluded.source_tier,
            source_weight = excluded.source_weight,
            is_official = excluded.is_official,
            extraction_confidence = excluded.extraction_confidence,
            headline = excluded.headline,
            snippet = excluded.snippet,
            extracted_at = excluded.extracted_at
        """,
        (
            company_id,
            field_key,
            field_value,
            source,
            source_url,
            tier,
            weight,
            1 if is_official else 0,
            extraction_confidence,
            headline,
            snippet,
            intelligence_event_id,
            raw_signal_id,
            now,
        ),
    )
    cur.execute(
        "SELECT id FROM company_profile_claims WHERE source_url = ? AND field_key = ?",
        (source_url, field_key),
    )
    row = cur.fetchone()
    return (int(row[0]) if row else None), not existed


def upsert_team_claim(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    name: str,
    role: str | None,
    source: str,
    source_url: str,
    is_founder: bool = False,
    joined_date: str | None = None,
    linkedin_url: str | None = None,
    headline: str | None = None,
    snippet: str | None = None,
    intelligence_event_id: int | None = None,
    raw_signal_id: int | None = None,
    extraction_confidence: float = 0.6,
    company_website: str | None = None,
) -> tuple[int | None, bool]:
    tier, weight, is_official = classify_source(source, source_url, company_website=company_website)
    now = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM team_member_claims WHERE source_url = ?",
        (source_url,),
    )
    existed = cur.fetchone() is not None
    cur.execute(
        """
        INSERT INTO team_member_claims (
            company_id, name, name_normalized, role, is_founder, joined_date,
            linkedin_url, source, source_url, source_tier, source_weight,
            is_official, extraction_confidence, headline, snippet,
            intelligence_event_id, raw_signal_id, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            name = excluded.name,
            name_normalized = excluded.name_normalized,
            role = COALESCE(excluded.role, role),
            is_founder = excluded.is_founder,
            joined_date = COALESCE(excluded.joined_date, joined_date),
            linkedin_url = COALESCE(excluded.linkedin_url, linkedin_url),
            source_tier = excluded.source_tier,
            source_weight = excluded.source_weight,
            extraction_confidence = excluded.extraction_confidence,
            headline = excluded.headline,
            snippet = excluded.snippet,
            extracted_at = excluded.extracted_at
        """,
        (
            company_id,
            name.strip(),
            _norm_person(name),
            role,
            1 if is_founder else 0,
            joined_date,
            linkedin_url,
            source,
            source_url,
            tier,
            weight,
            1 if is_official else 0,
            extraction_confidence,
            headline,
            snippet,
            intelligence_event_id,
            raw_signal_id,
            now,
        ),
    )
    cur.execute("SELECT id FROM team_member_claims WHERE source_url = ?", (source_url,))
    row = cur.fetchone()
    return (int(row[0]) if row else None), not existed


def upsert_product_claim(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    name: str,
    source: str,
    source_url: str,
    description: str | None = None,
    category: str | None = None,
    status: str = "active",
    product_url: str | None = None,
    launch_date: str | None = None,
    pricing_json: str | None = None,
    headline: str | None = None,
    snippet: str | None = None,
    intelligence_event_id: int | None = None,
    raw_signal_id: int | None = None,
    extraction_confidence: float = 0.6,
    company_website: str | None = None,
) -> tuple[int | None, bool]:
    tier, weight, is_official = classify_source(source, source_url, company_website=company_website)
    now = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute("SELECT id FROM product_claims WHERE source_url = ?", (source_url,))
    existed = cur.fetchone() is not None
    cur.execute(
        """
        INSERT INTO product_claims (
            company_id, name, name_normalized, description, category, status,
            product_url, launch_date, pricing_json, source, source_url,
            source_tier, source_weight, is_official, extraction_confidence,
            headline, snippet, intelligence_event_id, raw_signal_id, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            category = COALESCE(excluded.category, category),
            status = excluded.status,
            product_url = COALESCE(excluded.product_url, product_url),
            source_tier = excluded.source_tier,
            source_weight = excluded.source_weight,
            extraction_confidence = excluded.extraction_confidence,
            extracted_at = excluded.extracted_at
        """,
        (
            company_id,
            name.strip(),
            _norm_product(name),
            description,
            category,
            status,
            product_url,
            launch_date,
            pricing_json,
            source,
            source_url,
            tier,
            weight,
            1 if is_official else 0,
            extraction_confidence,
            headline,
            snippet,
            intelligence_event_id,
            raw_signal_id,
            now,
        ),
    )
    cur.execute("SELECT id FROM product_claims WHERE source_url = ?", (source_url,))
    row = cur.fetchone()
    return (int(row[0]) if row else None), not existed


def upsert_license_claim(
    conn: sqlite3.Connection,
    *,
    company_id: int,
    jurisdiction: str,
    license_type: str,
    status: str,
    regulator: str | None,
    source: str,
    source_url: str,
    license_number: str | None = None,
    effective_date: str | None = None,
    headline: str | None = None,
    snippet: str | None = None,
    intelligence_event_id: int | None = None,
    extraction_confidence: float = 0.7,
) -> tuple[int | None, bool]:
    tier, weight, is_official = classify_source(source, source_url)
    now = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute("SELECT id FROM license_claims WHERE source_url = ?", (source_url,))
    existed = cur.fetchone() is not None
    cur.execute(
        """
        INSERT INTO license_claims (
            company_id, jurisdiction, license_type, status, regulator,
            license_number, effective_date, source, source_url,
            source_tier, source_weight, is_official, extraction_confidence,
            headline, snippet, intelligence_event_id, extracted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            status = excluded.status,
            license_number = COALESCE(excluded.license_number, license_number),
            source_tier = excluded.source_tier,
            source_weight = excluded.source_weight,
            extracted_at = excluded.extracted_at
        """,
        (
            company_id,
            jurisdiction,
            license_type,
            status,
            regulator,
            license_number,
            effective_date,
            source,
            source_url,
            tier,
            weight,
            1 if is_official else 0,
            extraction_confidence,
            headline,
            snippet,
            intelligence_event_id,
            now,
        ),
    )
    cur.execute("SELECT id FROM license_claims WHERE source_url = ?", (source_url,))
    row = cur.fetchone()
    return (int(row[0]) if row else None), not existed


def _norm_person(name: str) -> str:
    return " ".join(name.lower().split())


def _norm_product(name: str) -> str:
    return " ".join(name.lower().split())
