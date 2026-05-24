#!/usr/bin/env python3
"""
Big Deals & Rumors Collector
Extracts high-value funding events from raw signals using keyword/heuristic rules only.

LLM extraction (Grok/Hermes) is NOT done here — use enrich queue or Grok X ingest.
Ollama is reserved for embeddings/rerank elsewhere in this repo.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger("big_deals")

from db.connection import get_conn

from collectors.funding_parse import parse_amount_usd
from collectors.pipeline_guard import (
    strict_pipeline_blocks_funding_events,
    strict_pipeline_blocks_legacy_events,
)

# Keywords indicating high-value or strategic deals
BIG_DEAL_KEYWORDS = [
    "partnership",
    "strategic investment",
    "valuation",
    "rumor",
    "rumoured",
    "billion",
    "mega-round",
    "record",
    "largest",
    "deal",
]


def generate_dedup_key(text: str) -> str:
    """Generate a short deduplication key from text."""
    return hashlib.sha256(text.lower().encode()).hexdigest()[:16]


def keyword_extract(text: str) -> dict | None:
    """Heuristic extraction only — no local LLM."""
    lower = text.lower()
    event_type = "Big Deal"
    if "partnership" in lower or "strategic" in lower:
        event_type = "Strategic Partnership"
    elif "valuation" in lower:
        event_type = "Valuation Update"
    elif "rumor" in lower or "rumoured" in lower:
        event_type = "Rumored Round"
    elif "billion" in lower or "mega" in lower:
        event_type = "Mega-Round"

    amount = parse_amount_usd(text)
    is_rumor = "rumor" in lower or "rumoured" in lower or "reportedly" in lower
    confidence = 0.72 if amount else 0.65
    return {
        "event_type": event_type,
        "company_name": None,
        "amount_usd": amount,
        "valuation_usd": amount if "valuation" in lower else None,
        "counterparty": None,
        "is_rumor": is_rumor,
        "confidence": confidence,
        "summary": text[:200],
    }


def create_event(event: dict) -> bool:
    """Insert a big deal event with deduplication."""
    if strict_pipeline_blocks_funding_events("big_deals_collector"):
        return False
    conn = get_conn()
    cursor = conn.cursor()

    dedup_key = generate_dedup_key(str(event))

    try:
        cursor.execute("SELECT 1 FROM funding_events WHERE source_url = ?", (dedup_key,))
        if cursor.fetchone():
            return False

        cursor.execute(
            """
            INSERT INTO funding_events
            (company_id, event_type, amount_usd, valuation_usd, lead_investor,
             announced_date, source, source_url, is_rumor, counterparty, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("company_id"),
                event.get("event_type", "Big Deal"),
                event.get("amount_usd"),
                event.get("valuation_usd"),
                event.get("counterparty"),
                datetime.now().strftime("%Y-%m-%d"),
                "big_deals_v1",
                dedup_key,
                str(event.get("is_rumor", False)),
                event.get("counterparty"),
                event.get("confidence", 0.7),
            ),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("Database error: %s", e)
        return False
    finally:
        conn.close()


def run() -> int:
    """Run big deals collector using keyword heuristics only."""
    if strict_pipeline_blocks_legacy_events("big_deals_collector"):
        return 0
    logger.info("Running Big Deals & Rumors Collector")
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, data_json FROM raw_signals
        ORDER BY detected_at DESC LIMIT 150
        """
    )
    rows = cursor.fetchall()

    created = 0
    for row in rows:
        try:
            data = json.loads(row["data_json"])
            text = " ".join(str(data.get(k, "")) for k in ["title", "summary", "content"])

            if not any(kw.lower() in text.lower() for kw in BIG_DEAL_KEYWORDS):
                continue

            result = keyword_extract(text)
            if not result:
                continue

            # Try to match company
            company_id = None
            if result.get("company_name"):
                norm = result["company_name"].lower().replace(" ", "").replace(".", "")
                cursor.execute(
                    "SELECT id FROM companies WHERE LOWER(REPLACE(name, ' ', '')) LIKE ?",
                    (f"%{norm}%",),
                )
                match = cursor.fetchone()
                if match:
                    company_id = match["id"]

            event = {
                "company_id": company_id,
                "event_type": result.get("event_type"),
                "amount_usd": result.get("amount_usd"),
                "valuation_usd": result.get("valuation_usd"),
                "counterparty": result.get("counterparty"),
                "is_rumor": result.get("is_rumor", False),
                "confidence": result.get("confidence", 0.7),
            }

            if create_event(event):
                created += 1
                company = result.get("company_name", "Unknown")
                logger.info("Created event: %s — %s", company, result["event_type"])

        except (json.JSONDecodeError, KeyError, TypeError, sqlite3.Error) as e:
            logger.warning("Error processing signal: %s", e)
            continue

    conn.close()
    logger.info("Big Deals collector complete. Created %s high-value events.", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
