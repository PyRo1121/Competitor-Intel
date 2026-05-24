"""
Company-level valuation: only when backed by collected financial signals.

No placeholder or baseline numbers. A row is written only when we have a
reported valuation, intel-event valuation, or an estimate derived from known
round amounts or total raised — never from activity heuristics alone.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from typing import Any

from db.connection import get_conn

logger = logging.getLogger("company_valuation")

# Implied post-money ≈ round size × multiple (conservative midpoints).
ROUND_VALUATION_MULTIPLIER: dict[str, float] = {
    "pre-seed": 10.0,
    "seed": 6.0,
    "series a": 5.0,
    "series b": 3.5,
    "series c": 2.8,
    "series d": 2.5,
    "series e": 2.3,
    "series f": 2.2,
    "growth": 2.0,
    "funding round": 5.0,
}

DEFAULT_MULTIPLIER = 5.0
MIN_INFERRED_USD = 3_000_000


def _norm_round_type(round_type: str | None) -> str:
    if not round_type:
        return "funding round"
    rt = str(round_type).strip().lower()
    m = re.search(r"series\s*([a-f])", rt, re.I)
    if m:
        return f"series {m.group(1).lower()}"
    return rt


def _multiplier_for_round(round_type: str | None) -> float:
    key = _norm_round_type(round_type)
    return ROUND_VALUATION_MULTIPLIER.get(key, DEFAULT_MULTIPLIER)


def _estimate_from_amount(amount_usd: int, round_type: str | None) -> int:
    if not amount_usd or amount_usd <= 0:
        return 0
    mult = _multiplier_for_round(round_type)
    return max(int(amount_usd * mult), MIN_INFERRED_USD)


def _pick_int(*values: int | None) -> int | None:
    for v in values:
        if v is not None and int(v) > 0:
            return int(v)
    return None


def resolve_company_valuation(
    conn: sqlite3.Connection,
    company_id: int,
) -> dict[str, Any] | None:
    """
    Choose best valuation for one company. Returns dict ready for upsert, or None if
    company_id missing.
    """
    cur = conn.cursor()

    row = cur.execute(
        """
        SELECT post_money_valuation_usd, valuation_usd, pre_money_valuation_usd,
               amount_usd, round_type, announced_date, corroboration_score, id
        FROM funding_rounds
        WHERE company_id = ?
        ORDER BY
          CASE
            WHEN post_money_valuation_usd IS NOT NULL AND post_money_valuation_usd > 0
            THEN 0 ELSE 1
          END,
          CASE WHEN valuation_usd IS NOT NULL AND valuation_usd > 0 THEN 0 ELSE 1 END,
          corroboration_score DESC,
          announced_date DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()

    if row:
        reported = _pick_int(
            row["post_money_valuation_usd"],
            row["valuation_usd"],
            row["pre_money_valuation_usd"],
        )
        if reported:
            conf = min(0.85, 0.45 + float(row["corroboration_score"] or 0) * 0.45)
            method = (
                "reported_post_money"
                if row["post_money_valuation_usd"]
                else "reported_round_valuation"
            )
            return {
                "company_id": company_id,
                "valuation_usd": reported,
                "valuation_kind": "reported",
                "method": method,
                "confidence": round(conf, 3),
                "as_of_date": row["announced_date"],
                "source_funding_round_id": row["id"],
                "source_notes": None,
            }

        amount = int(row["amount_usd"] or 0)
        if amount > 0:
            inferred = _estimate_from_amount(amount, row["round_type"])
            conf = min(0.55, 0.32 + float(row["corroboration_score"] or 0) * 0.25)
            return {
                "company_id": company_id,
                "valuation_usd": inferred,
                "valuation_kind": "estimated",
                "method": "inferred_from_latest_round",
                "confidence": round(conf, 3),
                "as_of_date": row["announced_date"],
                "source_funding_round_id": row["id"],
                "source_notes": json.dumps({"round_type": row["round_type"], "amount_usd": amount}),
            }

    event = cur.execute(
        """
        SELECT valuation_usd, announced_date, id, confidence
        FROM intelligence_events
        WHERE company_id = ? AND valuation_usd IS NOT NULL AND valuation_usd > 0
        ORDER BY announced_date DESC, confidence DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()
    if event:
        return {
            "company_id": company_id,
            "valuation_usd": int(event["valuation_usd"]),
            "valuation_kind": "reported",
            "method": "reported_intel_event",
            "confidence": round(min(0.75, float(event["confidence"] or 0.5)), 3),
            "as_of_date": event["announced_date"],
            "source_funding_round_id": None,
            "source_notes": json.dumps({"intelligence_event_id": event["id"]}),
        }

    totals = cur.execute(
        """
        SELECT COALESCE(SUM(amount_usd), 0) AS total,
               COUNT(*) AS n,
               MAX(announced_date) AS last_date
        FROM funding_rounds
        WHERE company_id = ? AND amount_usd IS NOT NULL AND amount_usd > 0
        """,
        (company_id,),
    ).fetchone()
    if totals and int(totals["total"] or 0) > 0:
        total = int(totals["total"])
        # Later rounds imply higher implied cap table — conservative 1.6× total raised.
        inferred = max(int(total * 1.6), MIN_INFERRED_USD)
        return {
            "company_id": company_id,
            "valuation_usd": inferred,
            "valuation_kind": "estimated",
            "method": "inferred_from_total_raised",
            "confidence": 0.35,
            "as_of_date": totals["last_date"],
            "source_funding_round_id": None,
            "source_notes": json.dumps({"total_raised_usd": total, "round_count": totals["n"]}),
        }

    return None


def upsert_company_valuation(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO company_valuations (
            company_id, valuation_usd, valuation_kind, method, confidence,
            as_of_date, source_funding_round_id, source_notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            valuation_usd = excluded.valuation_usd,
            valuation_kind = excluded.valuation_kind,
            method = excluded.method,
            confidence = excluded.confidence,
            as_of_date = excluded.as_of_date,
            source_funding_round_id = excluded.source_funding_round_id,
            source_notes = excluded.source_notes,
            updated_at = excluded.updated_at
        """,
        (
            record["company_id"],
            record["valuation_usd"],
            record["valuation_kind"],
            record["method"],
            record["confidence"],
            record.get("as_of_date"),
            record.get("source_funding_round_id"),
            record.get("source_notes"),
            now,
        ),
    )


def clear_company_valuation(conn: sqlite3.Connection, company_id: int) -> None:
    conn.execute("DELETE FROM company_valuations WHERE company_id = ?", (company_id,))


def sync_all_company_valuations(conn: sqlite3.Connection | None = None) -> dict[str, int]:
    """Recompute valuations; remove rows when no financial backing exists."""
    own = conn is None
    conn = conn or get_conn()
    cur = conn.cursor()
    company_ids = [row[0] for row in cur.execute("SELECT id FROM companies").fetchall()]
    reported = 0
    estimated = 0
    cleared = 0
    for cid in company_ids:
        record = resolve_company_valuation(conn, cid)
        if not record:
            clear_company_valuation(conn, cid)
            cleared += 1
            continue
        upsert_company_valuation(conn, record)
        if record["valuation_kind"] == "reported":
            reported += 1
        else:
            estimated += 1
    if own:
        conn.commit()
        conn.close()
    logger.info(
        "Company valuations synced: %s companies (%s reported, %s estimated, %s cleared)",
        len(company_ids),
        reported,
        estimated,
        cleared,
    )
    return {
        "companies": len(company_ids),
        "reported": reported,
        "estimated": estimated,
        "cleared": cleared,
    }
