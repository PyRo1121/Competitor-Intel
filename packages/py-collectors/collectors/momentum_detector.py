#!/usr/bin/env python3
"""
Momentum Detector - Real-time trending analysis for private companies.
Detects companies gaining momentum across multiple signals: funding, hiring,
product launches, GitHub activity, and media mentions.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger("momentum_detector")

from db.connection import get_conn

MOMENTUM_WEIGHTS = {
    "funding_velocity": 0.25,
    "signal_velocity": 0.20,
    "hiring_velocity": 0.15,
    "github_velocity": 0.15,
    "media_velocity": 0.15,
    "competitor_mentions": 0.10,
}

TRENDING_THRESHOLD = 0.35
BREAKOUT_THRESHOLD = 0.55
RISING_THRESHOLD = 0.2


def compute_funding_velocity(cursor: sqlite3.Cursor, company_id: int, days: int = 30) -> float:
    cursor.execute(
        """
        SELECT COUNT(*) as rounds, COALESCE(SUM(amount_usd), 0) as total
        FROM funding_rounds
        WHERE company_id = ? AND announced_date >= date('now', '-{} days')
        """.format(days),
        (company_id,),
    )
    row = cursor.fetchone()
    if not row or row[0] == 0:
        return 0.0
    rounds, total = row
    round_score = min(rounds / 3, 1.0)
    amount_score = min(total / 100_000_000, 1.0)
    return (round_score * 0.4 + amount_score * 0.6)


def compute_signal_velocity(cursor: sqlite3.Cursor, company_id: int, days: int = 30) -> float:
    cursor.execute(
        """
        SELECT COUNT(*) FROM raw_signals
        WHERE company_id = ? AND detected_at >= datetime('now', '-{} days')
        """.format(days),
        (company_id,),
    )
    count = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM raw_signals
        WHERE company_id = ? AND detected_at >= datetime('now', '-{} days')
        AND detected_at < datetime('now', '-{} days')
        """.format(days, days * 2),
        (company_id,),
    )
    prev_count = cursor.fetchone()[0]
    if prev_count == 0:
        return min(count / 20, 1.0)
    growth = (count - prev_count) / max(prev_count, 1)
    return min(max((growth + 1) / 2, 0), 1.0)


def compute_hiring_velocity(cursor: sqlite3.Cursor, company_id: int, days: int = 30) -> float:
    cursor.execute(
        """
        SELECT COUNT(*) FROM job_postings
        WHERE company_id = ? AND is_active = 1
        """.format(days),
        (company_id,),
    )
    active_jobs = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM team_members
        WHERE company_id = ? AND joined_date >= date('now', '-{} days')
        """.format(days),
        (company_id,),
    )
    new_hires = cursor.fetchone()[0]
    job_score = min(active_jobs / 10, 1.0)
    hire_score = min(new_hires / 5, 1.0)
    return job_score * 0.6 + hire_score * 0.4


def compute_github_velocity(cursor: sqlite3.Cursor, company_id: int, days: int = 30) -> float:
    cursor.execute(
        """
        SELECT commits_last_30d, active_contributors_30d, star_growth_30d
        FROM github_metrics
        WHERE company_id = ?
        ORDER BY extracted_at DESC LIMIT 1
        """,
        (company_id,),
    )
    row = cursor.fetchone()
    if not row:
        return 0.0
    commits, contributors, star_growth = row
    commits = commits or 0
    contributors = contributors or 0
    star_growth = star_growth or 0
    commits_score = min(commits / 100, 1.0)
    contributors_score = min(contributors / 10, 1.0)
    star_score = min(star_growth / 500, 1.0)
    return commits_score * 0.4 + contributors_score * 0.3 + star_score * 0.3


def compute_media_velocity(cursor: sqlite3.Cursor, company_id: int, days: int = 30) -> float:
    cursor.execute(
        """
        SELECT COUNT(*) FROM intelligence_events
        WHERE company_id = ? AND created_at >= datetime('now', '-{} days')
        """.format(days),
        (company_id,),
    )
    recent = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM intelligence_events
        WHERE company_id = ? AND created_at >= datetime('now', '-{} days')
        AND created_at < datetime('now', '-{} days')
        """.format(days, days * 2),
        (company_id,),
    )
    prev = cursor.fetchone()[0]
    if prev == 0:
        return min(recent / 10, 1.0)
    growth = (recent - prev) / max(prev, 1)
    return min(max((growth + 1) / 2, 0), 1.0)


def compute_competitor_mentions(cursor: sqlite3.Cursor, company_id: int, days: int = 30) -> float:
    cursor.execute(
        """
        SELECT COUNT(*) FROM competitor_relationships
        WHERE company_id = ? OR competitor_id = ?
        """,
        (company_id, company_id),
    )
    relationships = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*) FROM raw_signals rs
        WHERE rs.company_id = ? AND rs.detected_at >= datetime('now', '-{} days')
        AND (
            SELECT COUNT(*) FROM competitor_relationships cr
            WHERE (cr.company_id = ? OR cr.competitor_id = ?)
            AND (
                rs.data_json LIKE '%' || (SELECT name FROM companies WHERE id = cr.company_id) || '%'
                OR rs.data_json LIKE '%' || (SELECT name FROM companies WHERE id = cr.competitor_id) || '%'
            )
        ) > 0
        """.format(days),
        (company_id, company_id, company_id),
    )
    co_mentions = cursor.fetchone()[0]
    rel_score = min(relationships / 5, 1.0)
    mention_score = min(co_mentions / 10, 1.0)
    return rel_score * 0.4 + mention_score * 0.6


def detect_momentum(window_days: int = 30) -> Dict[str, Any]:
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, industry FROM companies WHERE status = 'active'")
    companies = cursor.fetchall()

    results = []
    for company_id, name, industry in companies:
        scores = {
            "funding_velocity": compute_funding_velocity(cursor, company_id, window_days),
            "signal_velocity": compute_signal_velocity(cursor, company_id, window_days),
            "hiring_velocity": compute_hiring_velocity(cursor, company_id, window_days),
            "github_velocity": compute_github_velocity(cursor, company_id, window_days),
            "media_velocity": compute_media_velocity(cursor, company_id, window_days),
            "competitor_mentions": compute_competitor_mentions(cursor, company_id, window_days),
        }

        composite = sum(scores[k] * MOMENTUM_WEIGHTS[k] for k in scores)

        status = "stable"
        if composite >= BREAKOUT_THRESHOLD:
            status = "breakout"
        elif composite >= TRENDING_THRESHOLD:
            status = "trending"
        elif composite >= RISING_THRESHOLD:
            status = "rising"

        results.append({
            "company_id": company_id,
            "name": name,
            "industry": industry,
            "momentum_score": round(composite, 4),
            "status": status,
            "breakdown": {k: round(v, 4) for k, v in scores.items()},
        })

    results.sort(key=lambda x: x["momentum_score"], reverse=True)

    trending = [r for r in results if r["status"] == "trending"]
    breakout = [r for r in results if r["status"] == "breakout"]

    logger.info(
        "Momentum detection: %d companies analyzed, %d trending, %d breakout",
        len(results), len(trending), len(breakout),
    )

    return {
        "analyzed": len(results),
        "trending": trending,
        "breakout": breakout,
        "all": results[:50],
    }


def run() -> Dict[str, Any]:
    return detect_momentum()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(f"Analyzed: {result['analyzed']}")
    print(f"Trending: {len(result['trending'])}")
    print(f"Breakout: {len(result['breakout'])}")
    if result['breakout']:
        print("\nBreakout companies:")
        for c in result['breakout']:
            print(f"  {c['name']}: {c['momentum_score']:.2f}")
