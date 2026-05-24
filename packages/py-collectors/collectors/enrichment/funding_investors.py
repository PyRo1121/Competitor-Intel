"""Investor normalization, per-claim participants, and round-level aggregation."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from typing import Any

from db.connection import get_conn

logger = logging.getLogger("funding_investors")

TIER_1_FRAGMENTS = (
    "a16z",
    "andreessen horowitz",
    "sequoia",
    "benchmark",
    "greylock",
    "accel",
    "kleiner perkins",
    "bessemer",
    "lightspeed",
    "index ventures",
    "general catalyst",
    "thrive capital",
    "founders fund",
    "y combinator",
)

TIER_2_FRAGMENTS = (
    "insight partners",
    "tiger global",
    "khosla",
    "menlo ventures",
    "nea",
    "battery ventures",
    "redpoint",
)


def normalize_investor_name(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip())
    n = re.sub(r"\s+(Ventures|Capital|Partners|VC|LLC|Inc\.?|LP)\.?$", "", n, flags=re.I)
    return n.strip()


def investor_slug(name: str) -> str:
    base = normalize_investor_name(name).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return slug or "unknown"


def investor_tier(name: str) -> int:
    n = name.lower()
    if any(t in n for t in TIER_1_FRAGMENTS):
        return 1
    if any(t in n for t in TIER_2_FRAGMENTS):
        return 2
    return 3


def _upsert_investor_cursor(cur: sqlite3.Cursor, name: str, now: str) -> int | None:
    clean = normalize_investor_name(name)
    if len(clean) < 2:
        return None
    slug = investor_slug(clean)
    tier = investor_tier(clean)
    cur.execute("SELECT id, tier FROM investor_firms WHERE name_normalized = ?", (slug,))
    row = cur.fetchone()
    if row:
        inv_id, old_tier = int(row[0]), int(row[1] or 3)
        cur.execute(
            "UPDATE investor_firms SET last_updated = ?, tier = ? WHERE id = ?",
            (now, min(old_tier, tier), inv_id),
        )
        return inv_id
    cur.execute(
        """
        INSERT INTO investor_firms
        (name, name_normalized, investor_type, tier, first_seen, last_updated)
        VALUES (?, ?, 'VC', ?, ?, ?)
        """,
        (clean, slug, tier, now, now),
    )
    return int(cur.lastrowid) if cur.lastrowid else None


def upsert_investor(name: str) -> int | None:
    clean = normalize_investor_name(name)
    if len(clean) < 2:
        return None
    now = datetime.now().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    try:
        inv_id = _upsert_investor_cursor(cur, clean, now)
        conn.commit()
        return inv_id
    except sqlite3.Error as e:
        logger.error("upsert_investor failed for %s: %s", clean, e)
        return None
    finally:
        conn.close()


def _participants_from_claim(claim: dict[str, Any]) -> list[tuple[str, str, int]]:
    """(name, role, is_lead) tuples from parsed claim fields."""
    out: list[tuple[str, str, int]] = []
    lead = claim.get("lead_investor")
    if lead:
        out.append((lead, "lead", 1))

    co_raw = claim.get("co_investors")
    names: list[str] = []
    if isinstance(co_raw, str) and co_raw.strip():
        try:
            names = json.loads(co_raw)
        except json.JSONDecodeError:
            names = [co_raw]
    elif isinstance(co_raw, list):
        names = co_raw

    for name in names:
        if not name:
            continue
        if lead and normalize_investor_name(name).lower() == normalize_investor_name(lead).lower():
            continue
        out.append((str(name), "participant", 0))
    return out


def sync_claim_participants(
    claim_id: int,
    claim: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Persist per-source investor rows for one claim."""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cur.execute(
            "DELETE FROM funding_claim_participants WHERE funding_round_claim_id = ?",
            (claim_id,),
        )
        excerpt = (claim.get("snippet") or claim.get("headline") or "")[:400]
        written = 0
        for name, role, is_lead in _participants_from_claim(claim):
            inv_id = _upsert_investor_cursor(cur, name, now)
            cur.execute(
                """
                INSERT INTO funding_claim_participants
                (funding_round_claim_id, investor_id, investor_name_raw, role, is_lead, excerpt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (claim_id, inv_id, name, role, is_lead, excerpt),
            )
            written += 1
        if own_conn:
            conn.commit()
        return written
    except sqlite3.Error as e:
        logger.error("sync_claim_participants failed claim %s: %s", claim_id, e)
        return 0
    finally:
        if own_conn:
            conn.close()


def sync_round_participants(
    funding_round_id: int,
    claims: list[sqlite3.Row],
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    """
    Merge claim-level participants into round_participants + attributions.
    Corroboration per investor = distinct source domains reporting them.
    """
    if not claims:
        return 0

    claim_ids = [c["id"] for c in claims]
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    placeholders = ",".join("?" * len(claim_ids))
    cur.execute(
        f"""
        SELECT fcp.*, frc.source_url, frc.source_tier, frc.is_official, frc.source_weight
        FROM funding_claim_participants fcp
        JOIN funding_round_claims frc ON frc.id = fcp.funding_round_claim_id
        WHERE fcp.funding_round_claim_id IN ({placeholders})
        """,
        claim_ids,
    )
    rows = cur.fetchall()

    by_investor: dict[int, dict[str, Any]] = {}
    for row in rows:
        inv_id = row["investor_id"]
        if inv_id is None:
            continue
        inv_id = int(inv_id)
        bucket = by_investor.setdefault(
            inv_id,
            {
                "roles": [],
                "is_lead": 0,
                "claims": set(),
                "domains": set(),
                "official": 0,
                "attributions": [],
            },
        )
        bucket["roles"].append(row["role"])
        bucket["is_lead"] = max(bucket["is_lead"], int(row["is_lead"] or 0))
        bucket["claims"].add(row["funding_round_claim_id"])
        host = row["source_url"] or ""
        if host:
            from .funding_source_trust import normalize_domain

            dom = normalize_domain(host)
            if dom:
                bucket["domains"].add(dom)
        bucket["official"] = max(bucket["official"], int(row["is_official"] or 0))
        bucket["attributions"].append(row)

    cur.execute(
        "DELETE FROM round_participants WHERE funding_round_id = ?",
        (funding_round_id,),
    )
    now = datetime.now().isoformat()
    synced = 0

    for inv_id, meta in by_investor.items():
        role = (
            "lead"
            if meta["is_lead"]
            else (
                "co_lead"
                if "co_lead" in meta["roles"]
                else meta["roles"][0]
                if meta["roles"]
                else "participant"
            )
        )
        report_count = len(meta["claims"])
        domain_count = len(meta["domains"])
        score = min(
            1.0,
            round(
                0.25 * min(domain_count, 4) / 4
                + 0.20 * min(report_count, 5) / 5
                + (0.25 if meta["official"] else 0)
                + 0.15,
                3,
            ),
        )

        cur.execute(
            """
            INSERT INTO round_participants
            (funding_round_id, investor_id, role, is_lead, report_count,
             source_domain_count, corroboration_score, has_official_source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                funding_round_id,
                inv_id,
                role,
                meta["is_lead"],
                report_count,
                domain_count,
                score,
                meta["official"],
                now,
            ),
        )
        rp_id = cur.lastrowid

        for row in meta["attributions"]:
            cur.execute(
                """
                INSERT INTO participant_source_attributions
                (round_participant_id, funding_round_claim_id, investor_id,
                 role, excerpt, source_url, source_tier, is_official)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(round_participant_id, funding_round_claim_id) DO NOTHING
                """,
                (
                    rp_id,
                    row["funding_round_claim_id"],
                    inv_id,
                    row["role"],
                    row["excerpt"],
                    row["source_url"],
                    row["source_tier"],
                    row["is_official"],
                ),
            )
        synced += 1

    investor_count = len(by_investor)
    cur.execute(
        """
        UPDATE funding_rounds SET total_investor_count = ?, updated_at = ?
        WHERE id = ?
        """,
        (investor_count, now, funding_round_id),
    )
    if own_conn:
        conn.commit()
        conn.close()
    return synced
