"""Entity resolution via company_aliases (Track 4 P4-6)."""

from __future__ import annotations

import sqlite3

import pytest
from collectors.entity_resolution import (
    lookup_alias,
    normalize_alias,
    register_alias,
    resolve_company_entity,
)


@pytest.fixture
def alias_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            website TEXT,
            slug TEXT UNIQUE,
            x_handle TEXT,
            industry TEXT,
            status TEXT
        );
        CREATE TABLE company_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            alias_display TEXT NOT NULL,
            alias_normalized TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            confidence REAL DEFAULT 0.9,
            created_at TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO companies (id, name, slug, industry, status) "
        "VALUES (1, 'Stripe', 'stripe', 'fintech', 'active')"
    )
    yield conn
    conn.close()


def test_normalize_alias():
    assert normalize_alias("Stripe, Inc.") == "stripe inc"


def test_register_and_lookup_alias(alias_db):
    register_alias(
        alias_db.cursor(),
        company_id=1,
        alias="Stripe Payments",
        source="test",
        confidence=0.95,
    )
    alias_db.commit()
    hit = lookup_alias(alias_db.cursor(), "Stripe Payments")
    assert hit is not None
    assert hit.company_id == 1
    assert hit.method == "alias"


def test_resolve_fuzzy_fallback(alias_db):
    entity = resolve_company_entity(alias_db.cursor(), "Stripe")
    assert entity is not None
    assert entity.company_id == 1
    assert entity.method == "fuzzy"
