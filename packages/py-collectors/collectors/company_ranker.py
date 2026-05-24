#!/usr/bin/env python3
"""
Rank tracked companies by attention in the signal firehose (volume + velocity + hype).

Writes composite score to companies.score for dashboard top-N ordering.
Sector-agnostic; does not require funding rounds or a fixed CIK list.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from typing import Any

from db.connection import get_conn

from collectors.entity_extract import hype_keyword_hits

logger = logging.getLogger("company_ranker")

WINDOW_DAYS = 30


def _signal_stats(cursor: sqlite3.Cursor, company_id: int) -> dict[str, float]:
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM raw_signals
        WHERE company_id = ? AND detected_at >= datetime('now', '-{WINDOW_DAYS} days')
        """,
        (company_id,),
    )
    recent = cursor.fetchone()[0]
    cursor.execute(
        f"""
        SELECT COUNT(*) FROM raw_signals
        WHERE company_id = ?
          AND detected_at >= datetime('now', '-{WINDOW_DAYS * 2} days')
          AND detected_at < datetime('now', '-{WINDOW_DAYS} days')
        """,
        (company_id,),
    )
    prior = cursor.fetchone()[0]

    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT source) FROM raw_signals
        WHERE company_id = ? AND detected_at >= datetime('now', '-{WINDOW_DAYS} days')
        """,
        (company_id,),
    )
    sources = cursor.fetchone()[0]

    cursor.execute(
        f"""
        SELECT COUNT(*) FROM intelligence_events
        WHERE company_id = ? AND created_at >= datetime('now', '-{WINDOW_DAYS} days')
        """,
        (company_id,),
    )
    events = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT data_json FROM raw_signals
        WHERE company_id = ? ORDER BY detected_at DESC LIMIT 40
        """,
        (company_id,),
    )
    hype_total = 0
    for (data_json,) in cursor.fetchall():
        try:
            data = json.loads(data_json or "{}")
        except json.JSONDecodeError:
            data = {}
        text = " ".join(str(data.get(k) or "") for k in ("title", "summary", "text", "description"))
        hype_total += hype_keyword_hits(text)

    if prior == 0:
        velocity = min(recent / 20.0, 1.0)
    else:
        growth = (recent - prior) / max(prior, 1)
        velocity = min(max((growth + 1) / 2, 0), 1.0)

    volume = min(recent / 25.0, 1.0)
    diversity = min(sources / 6.0, 1.0)
    events_score = min(events / 8.0, 1.0)
    hype = min(hype_total / 8.0, 1.0)

    composite = (
        volume * 0.30 + velocity * 0.30 + diversity * 0.15 + events_score * 0.15 + hype * 0.10
    )
    return {
        "composite": round(min(composite, 1.0), 4),
        "volume": volume,
        "velocity": velocity,
        "diversity": diversity,
        "events": events_score,
        "hype": hype,
        "signal_count_30d": float(recent),
    }


def rank_companies() -> dict[str, Any]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM companies WHERE status = 'active' OR status IS NULL")
    rows = cursor.fetchall()
    now = datetime.now(UTC).isoformat()
    ranked: list[dict[str, Any]] = []

    for company_id, name in rows:
        stats = _signal_stats(cursor, company_id)
        score = stats["composite"]
        cursor.execute(
            "UPDATE companies SET score = ?, last_scored_at = ? WHERE id = ?",
            (score, now, company_id),
        )
        ranked.append({"company_id": company_id, "name": name, "score": score, **stats})

    ranked.sort(key=lambda r: r["score"], reverse=True)
    conn.commit()
    conn.close()

    top = ranked[:10]
    logger.info(
        "Ranked %s companies by attention score. Top: %s",
        len(ranked),
        ", ".join(f"{r['name']} ({r['score']:.2f})" for r in top[:5]),
    )
    return {"ranked": len(ranked), "top10": top}


def run() -> int:
    return rank_companies()["ranked"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
