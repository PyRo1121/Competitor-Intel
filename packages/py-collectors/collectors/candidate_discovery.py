#!/usr/bin/env python3
"""
Discover up-and-coming companies from the signal firehose (not a fixed watchlist).

Harvests names from raw_signals + intelligence_events, scores by attention
(volume, velocity, source diversity, hype language), and upserts company_candidates.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from db.connection import get_conn

from collectors.entity_extract import (
    extract_entities_from_text,
    hype_keyword_hits,
    is_plausible_company_name,
    normalize_entity_name,
)
from collectors.signal_processor import fuzzy_match_company

logger = logging.getLogger("candidate_discovery")

LOOKBACK_DAYS = 30
SIGNAL_SCAN_LIMIT = 15000


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _is_tracked_company(cursor: sqlite3.Cursor, name: str) -> bool:
    matched = fuzzy_match_company(name, cursor)
    if not matched:
        return False
    return matched[2] >= 0.72


def _payload_entities(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("entity_name", "commercial_name", "name"):
        val = data.get(key)
        if val and is_plausible_company_name(str(val)):
            names.append(normalize_entity_name(str(val)))
    for item in data.get("mentioned_companies") or []:
        if item and is_plausible_company_name(str(item)):
            names.append(normalize_entity_name(str(item)))
    for item in data.get("companies_detected") or data.get("provisional_entities") or []:
        if item and is_plausible_company_name(str(item)):
            names.append(normalize_entity_name(str(item)))
    title = data.get("title") or ""
    summary = data.get("summary") or data.get("text") or data.get("description") or ""
    names.extend(extract_entities_from_text(f"{title} {summary}"))
    return list(dict.fromkeys(names))


def harvest_signal_mentions(cursor: sqlite3.Cursor) -> dict[str, dict[str, Any]]:
    """
    Aggregate mention stats per entity name from recent raw_signals.
    Returns name -> {signal_ids, sources, hype_hits, last_seen, snippets}.
    """
    cursor.execute(
        f"""
        SELECT id, source, data_json, detected_at, company_id
        FROM raw_signals
        WHERE detected_at >= datetime('now', '-{LOOKBACK_DAYS} days')
        ORDER BY detected_at DESC
        LIMIT ?
        """,
        (SIGNAL_SCAN_LIMIT,),
    )
    buckets: defaultdict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "signal_ids": [],
            "sources": set(),
            "hype_hits": 0,
            "last_seen": None,
            "linked_company_id": None,
        }
    )

    for row in cursor.fetchall():
        sig_id, source, data_json, detected_at, company_id = row
        try:
            data = json.loads(data_json or "{}")
        except json.JSONDecodeError:
            data = {}
        text = " ".join(
            str(data.get(k) or "")
            for k in ("title", "summary", "text", "description", "entity_name")
        )
        hype = hype_keyword_hits(text)

        names: set[str] = set()
        if company_id:
            cursor.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
            crow = cursor.fetchone()
            if crow and crow[0]:
                names.add(normalize_entity_name(crow[0]))
        names.update(_payload_entities(data))

        for name in names:
            if not is_plausible_company_name(name) or _is_tracked_company(cursor, name):
                continue
            bucket = buckets[name]
            if len(bucket["signal_ids"]) < 200:
                bucket["signal_ids"].append(sig_id)
            bucket["sources"].add(source or "unknown")
            bucket["hype_hits"] += hype
            if not bucket["last_seen"] or (detected_at and detected_at > bucket["last_seen"]):
                bucket["last_seen"] = detected_at

    return dict(buckets)


def compute_attention_score(stats: dict[str, Any]) -> tuple[float, dict[str, float]]:
    """0–1 attention score from signal volume, diversity, recency proxy, hype language."""
    n_signals = len(stats.get("signal_ids") or [])
    n_sources = len(stats.get("sources") or [])
    hype = int(stats.get("hype_hits") or 0)

    volume = min(n_signals / 15.0, 1.0)
    diversity = min(n_sources / 5.0, 1.0)
    hype_score = min(hype / 6.0, 1.0)
    # Recent signals weighted via volume; explicit recency in ranker pass.
    composite = volume * 0.45 + diversity * 0.25 + hype_score * 0.30

    breakdown = {
        "signal_volume": round(volume, 4),
        "source_diversity": round(diversity, 4),
        "hype_language": round(hype_score, 4),
    }
    return round(min(composite, 1.0), 4), breakdown


def upsert_candidates(cursor: sqlite3.Cursor, harvested: dict[str, dict[str, Any]]) -> int:
    now = datetime.now(UTC).isoformat()
    upserted = 0
    for name, stats in harvested.items():
        score, breakdown = compute_attention_score(stats)
        if score < 0.08 and len(stats["signal_ids"]) < 2:
            continue
        signals_meta = {
            "signal_ids": stats["signal_ids"][:50],
            "sources": sorted(stats["sources"]),
            "last_seen": stats.get("last_seen"),
        }
        sources_str = ",".join(sorted(stats["sources"]))[:200]
        try:
            cursor.execute(
                """
                INSERT INTO company_candidates (
                    name, description, discovery_source, signals, score,
                    score_breakdown, status, first_seen, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    score = MAX(company_candidates.score, excluded.score),
                    score_breakdown = excluded.score_breakdown,
                    signals = excluded.signals,
                    discovery_source = COALESCE(
                        company_candidates.discovery_source, excluded.discovery_source
                    ),
                    last_updated = excluded.last_updated
                """,
                (
                    name,
                    f"Mentioned in {len(stats['signal_ids'])} signals ({sources_str})",
                    sources_str or "signals",
                    json.dumps(signals_meta),
                    score,
                    json.dumps(breakdown),
                    stats.get("last_seen") or now,
                    now,
                ),
            )
            upserted += 1
        except sqlite3.Error as exc:
            logger.warning("Candidate upsert failed for %s: %s", name, exc)
    return upserted


def run_candidate_discovery() -> dict[str, int]:
    conn = get_conn()
    cursor = conn.cursor()
    harvested = harvest_signal_mentions(cursor)
    upserted = upsert_candidates(cursor, harvested)
    conn.commit()
    conn.close()
    logger.info(
        "Candidate discovery: %s unique names harvested, %s candidates upserted",
        len(harvested),
        upserted,
    )
    return {"names_harvested": len(harvested), "candidates_upserted": upserted}


def run() -> int:
    return run_candidate_discovery()["candidates_upserted"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
