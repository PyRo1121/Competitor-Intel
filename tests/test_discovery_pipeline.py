"""Discovery → promote → rank operational pipeline."""

from __future__ import annotations

import json
import sqlite3

import pytest


@pytest.mark.operational
def test_discovery_promote_rank_flow(operational_db, monkeypatch):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    sources = ("techcrunch", "hackernews", "rss", "github")
    for i, source in enumerate(sources * 4):
        payload = {
            "title": "Nebula Labs raises $50 million in Series B funding round",
            "summary": "Nebula Labs secured investment led by top investors",
            "url": f"https://news.example/nebula-{source}-{i}",
        }
        cur.execute(
            """
            INSERT INTO raw_signals (
                company_id, source, signal_type, data_json, detected_at, processed
            )
            VALUES (NULL, ?, ?, ?, datetime('now', ?), 0)
            """,
            (source, f"sig_{i}", json.dumps(payload), f"-{i} hours"),
        )
    conn.commit()
    conn.close()

    from collectors.auto_promote import PROMOTION_THRESHOLD, auto_promote_candidates
    from collectors.candidate_discovery import run_candidate_discovery
    from collectors.company_ranker import rank_companies

    discovery = run_candidate_discovery()
    assert discovery["candidates_upserted"] >= 1

    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("SELECT score, status FROM company_candidates WHERE name LIKE '%Nebula Labs%'")
    row = cur.fetchone()
    assert row is not None
    score, status = row
    assert status == "pending"
    if score < PROMOTION_THRESHOLD:
        cur.execute(
            "UPDATE company_candidates SET score = ? WHERE name LIKE '%Nebula Labs%'",
            (PROMOTION_THRESHOLD + 0.05,),
        )
        conn.commit()
    conn.close()

    promoted = auto_promote_candidates()
    assert promoted >= 1

    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("SELECT status FROM company_candidates WHERE name LIKE '%Nebula Labs%'")
    assert cur.fetchone()[0] == "promoted"
    cur.execute("SELECT id, score FROM companies WHERE slug = 'nebula-labs'")
    company = cur.fetchone()
    assert company is not None
    conn.close()

    ranked = rank_companies()
    assert ranked["ranked"] >= 1

    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("SELECT score, last_scored_at FROM companies WHERE slug = 'nebula-labs'")
    scored = cur.fetchone()
    assert scored is not None
    assert scored[0] is not None
    assert scored[1] is not None
    conn.close()


@pytest.mark.operational
def test_auto_promote_idempotent_when_company_exists(operational_db):
    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO companies (name, slug, status, first_seen, last_updated)
        VALUES ('Existing Co', 'existing-co', 'active', datetime('now'), datetime('now'))
        """
    )
    cur.execute(
        """
        INSERT INTO company_candidates (
            name, description, discovery_source, signals, score,
            score_breakdown, status, first_seen, last_updated
        )
        VALUES (
            'Existing Co', 'test', 'unit', '{}', 0.9, '{}', 'pending',
            datetime('now'), datetime('now')
        )
        """
    )
    conn.commit()
    conn.close()

    from collectors.auto_promote import auto_promote_candidates

    assert auto_promote_candidates() == 1

    conn = sqlite3.connect(operational_db)
    cur = conn.cursor()
    cur.execute("SELECT status FROM company_candidates WHERE name = 'Existing Co'")
    assert cur.fetchone()[0] == "promoted"
    cur.execute("SELECT COUNT(*) FROM companies WHERE slug = 'existing-co'")
    assert cur.fetchone()[0] == 1
    conn.close()
