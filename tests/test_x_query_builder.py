"""Tests for pipeline-derived X query builder."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from collectors.x_query_builder import (
    _dedupe_queries,
    _event_fragment,
    build_query_payload,
    expand_queries_with_xai,
    queries_for_fetch,
)


def test_event_fragment_mapping():
    assert "funding" in _event_fragment("funding")
    assert "launch" in _event_fragment("product_launch")
    assert "acquire" in _event_fragment("acquisition")


def test_dedupe_queries():
    out = _dedupe_queries(['"Acme" funding', '"Acme" funding', "  "])
    assert len(out) == 1


def test_derive_queries_from_empty_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY, name TEXT, x_handle TEXT
        );
        CREATE TABLE intelligence_events (
            id INTEGER PRIMARY KEY, company_id INTEGER, event_type TEXT NOT NULL,
            amount_usd INTEGER, announced_date TEXT, created_at TEXT,
            confidence REAL DEFAULT 0.7, description TEXT
        );
        CREATE TABLE raw_signals (
            id INTEGER PRIMARY KEY, company_id INTEGER, source TEXT,
            signal_type TEXT, data_json TEXT, detected_at TEXT, processed INTEGER DEFAULT 0
        );
        CREATE TABLE product_claims (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, name TEXT NOT NULL,
            extracted_at TEXT NOT NULL
        );
        INSERT INTO companies (name, x_handle) VALUES ('Stripe', 'stripe');
        """
    )
    conn.commit()
    monkeypatch.setenv("CI_DB_PATH", str(db))
    from collectors import x_query_builder as xqb

    targeted, snippets, stats = xqb.derive_queries_from_db(conn=conn, lookback_days=7)
    assert stats["companies_with_handle"] == 1
    assert any("stripe" in q.lower() or "Stripe" in q for q in targeted)
    conn.close()


def test_derive_queries_from_recent_intel(tmp_path, monkeypatch):
    db = tmp_path / "intel.db"
    conn = sqlite3.connect(db)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    conn.executescript(
        f"""
        CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT, x_handle TEXT);
        CREATE TABLE intelligence_events (
            id INTEGER PRIMARY KEY, company_id INTEGER, event_type TEXT NOT NULL,
            amount_usd INTEGER, announced_date TEXT, created_at TEXT,
            confidence REAL DEFAULT 0.9, description TEXT, source TEXT,
            source_url TEXT UNIQUE, raw_signal_id INTEGER
        );
        CREATE TABLE raw_signals (
            id INTEGER PRIMARY KEY, company_id INTEGER, source TEXT,
            signal_type TEXT, data_json TEXT, detected_at TEXT, processed INTEGER DEFAULT 0
        );
        CREATE TABLE product_claims (
            id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, name TEXT NOT NULL,
            extracted_at TEXT NOT NULL
        );
        INSERT INTO companies (id, name, x_handle) VALUES (1, 'Anthropic', 'AnthropicAI');
        INSERT INTO intelligence_events (
            company_id, event_type, amount_usd, announced_date, created_at,
            description, source, source_url
        ) VALUES (
            1, 'funding', 500000000, '{today}', '{today}',
            'Series D', 'rss', 'https://example.com/a'
        );
        """
    )
    conn.commit()
    monkeypatch.setenv("CI_DB_PATH", str(db))
    from collectors import x_query_builder as xqb

    targeted, snippets, _stats = xqb.derive_queries_from_db(conn=conn, lookback_days=7)
    assert any("Anthropic" in q for q in targeted)
    assert any("Anthropic" in s for s in snippets)
    conn.close()


def test_build_query_payload_baseline_only():
    payload = build_query_payload(enriched=False)
    assert payload["enriched"] is False
    assert payload["derived_queries"] == []
    assert len(payload["global_queries"]) >= 5


def test_queries_for_fetch_merges_sections():
    payload = {
        "baseline_queries": ['"Acme" funding min_faves:5'],
        "derived_queries": ['"Beta" launch min_faves:3'],
        "ai_queries": ['"Gamma" acquisition min_faves:4'],
        "global_queries": [
            '"Acme" funding min_faves:5',
            '"Beta" launch min_faves:3',
            '"Gamma" acquisition min_faves:4',
        ],
    }
    merged = queries_for_fetch(payload)
    assert any("Acme" in q for q in merged)
    assert any("Beta" in q for q in merged)
    assert any("Gamma" in q for q in merged)


def test_expand_queries_with_xai_disabled(monkeypatch):
    monkeypatch.delenv("CI_X_QUERY_AI_EXPAND", raising=False)
    assert expand_queries_with_xai(["Acme raised $10M"]) == []


def test_expand_queries_with_xai_mock(monkeypatch):
    monkeypatch.setenv("CI_X_QUERY_AI_EXPAND", "1")

    def fake_post(url, payload, timeout=60.0, headers=None):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            ['"Acme" raised funding min_faves:5 since:2026-01-01']
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("utils.http.post_json", fake_post)
    monkeypatch.setattr(
        "collectors.grok_x_fetcher.resolve_xai_credentials",
        lambda: ("key", "https://api.x.ai/v1", "xai"),
    )
    out = expand_queries_with_xai(["Acme: funding — Series B"])
    assert len(out) == 1
    assert "Acme" in out[0]
