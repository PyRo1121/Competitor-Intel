"""Propagate funding corroboration scores into intelligence_events (and linked signals)."""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from typing import Any

from db.connection import get_conn

from .confidence_scoring import compute_corroboration
from .funding_source_trust import classify_source

logger = logging.getLogger("confidence_sync")

FUNDING_EVENT_TYPES = (
    "Funding Round",
    "Rumored Round",
    "Strategic Investment",
    "Mega Round",
    "Debt Financing",
    "Partnership Deal",
    "Traditional VC",
)


def _event_as_claim(row: sqlite3.Row, company_website: str | None) -> dict[str, Any]:
    tier, weight, official = classify_source(
        row["source"],
        row["source_url"],
        company_website=company_website,
        is_rumor=False,
    )
    return {
        "source": row["source"],
        "source_url": row["source_url"],
        "source_weight": weight,
        "is_official": 1 if official else 0,
        "amount_usd": row["amount_usd"],
        "source_tier": tier,
    }


def sync_event_confidence_from_funding(conn: sqlite3.Connection | None = None) -> int:
    """
    Set intelligence_events.confidence from linked funding_rounds.corroboration_score.
    Returns rows updated.
    """
    own = conn is None
    conn = conn or get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE intelligence_events
        SET confidence = (
            SELECT fr.corroboration_score
            FROM funding_round_claims frc
            JOIN funding_rounds fr ON fr.id = frc.funding_round_id
            WHERE frc.intelligence_event_id = intelligence_events.id
            ORDER BY fr.corroboration_score DESC
            LIMIT 1
        )
        WHERE id IN (
            SELECT frc.intelligence_event_id
            FROM funding_round_claims frc
            WHERE frc.intelligence_event_id IS NOT NULL
              AND frc.funding_round_id IS NOT NULL
        )
        """
    )
    updated = cur.rowcount
    if own:
        conn.commit()
        conn.close()
    logger.info("Synced event confidence from funding rounds: %s rows", updated)
    return updated


def recompute_funding_event_clusters(conn: sqlite3.Connection | None = None) -> int:
    """
    For funding-like events not yet linked to claims, cluster by company + month + amount bucket
    and assign corroboration from the cluster (same rules as funding claims).
    """
    own = conn is None
    conn = conn or get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in FUNDING_EVENT_TYPES)
    cur.execute(
        f"""
        SELECT ie.id, ie.company_id, ie.source, ie.source_url, ie.amount_usd,
               ie.event_type, ie.announced_date, c.website AS company_website
        FROM intelligence_events ie
        JOIN companies c ON c.id = ie.company_id
        WHERE ie.company_id IS NOT NULL
          AND ie.event_type IN ({placeholders})
          AND ie.id NOT IN (
              SELECT intelligence_event_id FROM funding_round_claims
              WHERE intelligence_event_id IS NOT NULL
          )
        """,
        FUNDING_EVENT_TYPES,
    )
    rows = cur.fetchall()
    if not rows:
        if own:
            conn.close()
        return 0

    def cluster_key(row: sqlite3.Row) -> str:
        amt = row["amount_usd"]
        bucket = "undisclosed"
        if amt and int(amt) > 0:
            import math

            bucket = str(int(math.log10(max(int(amt), 1)) * 10))
        month = (row["announced_date"] or "")[:7] or "unknown"
        return f"{row['company_id']}:{row['event_type']}:{bucket}:{month}"

    clusters: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        clusters[cluster_key(row)].append(row)

    updated = 0
    for group in clusters.values():
        claims = [_event_as_claim(r, r["company_website"]) for r in group]
        score, _meta = compute_corroboration(claims)
        for r in group:
            cur.execute(
                "UPDATE intelligence_events SET confidence = ? WHERE id = ?",
                (score, r["id"]),
            )
            updated += 1

    if own:
        conn.commit()
        conn.close()
    logger.info("Recomputed cluster confidence for funding events: %s rows", updated)
    return updated


def sync_all_event_confidence(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """Run full post-aggregation confidence sync."""
    own = conn is None
    conn = conn or get_conn()
    from_funding = sync_event_confidence_from_funding(conn)
    from_clusters = recompute_funding_event_clusters(conn)
    if own:
        conn.commit()
        conn.close()
    return {
        "from_funding_rounds": from_funding,
        "from_event_clusters": from_clusters,
    }
