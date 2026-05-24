"""Shared minimal SQLite DDL for company-data / claims tests."""

from __future__ import annotations

import sqlite3

COMPANIES_MINIMAL_SQL = """
CREATE TABLE companies (
    id INTEGER PRIMARY KEY,
    name TEXT,
    website TEXT
);
"""

CLAIM_TABLES_SQL = """
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

RAW_SIGNALS_COLLECTOR_SQL = """
CREATE TABLE raw_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    source TEXT,
    signal_type TEXT,
    data_json TEXT,
    detected_at TEXT
);
"""

COMPANIES_FULL_SQL = """
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
"""

COMPANY_DATA_AGGREGATE_SQL = """
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

INTELLIGENCE_EVENTS_SQL = """
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
"""

RAW_SIGNALS_EVENTS_SQL = """
CREATE TABLE raw_signals (
    id INTEGER PRIMARY KEY,
    data_json TEXT
);
"""


def apply_claims_ingest_schema(conn: sqlite3.Connection) -> None:
    """Companies + claim tables + collector raw_signals (bulk extract tests)."""
    conn.executescript(
        COMPANIES_MINIMAL_SQL + CLAIM_TABLES_SQL + RAW_SIGNALS_COLLECTOR_SQL
    )


def apply_company_data_schema(conn: sqlite3.Connection) -> None:
    """Full company-data rollup schema (profile/team/product aggregators)."""
    conn.executescript(
        COMPANIES_FULL_SQL
        + CLAIM_TABLES_SQL
        + COMPANY_DATA_AGGREGATE_SQL
    )


def apply_events_extract_schema(conn: sqlite3.Connection) -> None:
    """intelligence_events + minimal raw_signals for event-driven extraction."""
    conn.executescript(INTELLIGENCE_EVENTS_SQL + RAW_SIGNALS_EVENTS_SQL)
