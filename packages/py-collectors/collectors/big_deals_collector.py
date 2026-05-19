#!/usr/bin/env python3
"""
Big Deals & Rumors Collector
Extracts high-value funding events and strategic partnerships from raw signals.
Uses Ollama LLM via HTTP API when available (bare metal install).
Falls back to keyword heuristics when LLM is unavailable.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("big_deals")

from db.connection import get_conn, DB_PATH

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


def try_llm_extract(text: str) -> dict | None:
    """Attempt to extract structured data using local Ollama LLM via HTTP API."""
    prompt = f"""Extract funding intelligence from this text as JSON:

Text: "{text[:1000]}"

Return ONLY valid JSON:
{{
  "event_type": "Strategic Partnership | Valuation Update | Rumored Round | Commercial Deal | Mega-Round",
  "company_name": "exact name or null",
  "amount_usd": number or null,
  "valuation_usd": number or null,
  "counterparty": "the other company or null",
  "is_rumor": true/false,
  "confidence": 0.0-1.0,
  "summary": "one sentence summary"
}}"""

    # Try HTTP API first (bare metal Ollama)
    try:
        from ollama_client import generate

        response = generate(prompt, model="qwen3.5:9b", temperature=0.1, num_predict=350)
        if response:
            data = json.loads(response)
            if data.get("confidence", 0) >= 0.65:
                return data
    except (ImportError, json.JSONDecodeError, ValueError) as e:
        logger.debug("HTTP LLM extraction failed: %s", e)

    # Fallback to import-based Ollama if available
    try:
        import ollama  # type: ignore # noqa: F811
        import re

        response = ollama.chat(
            model="qwen3.5:9b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1, "num_predict": 350},
        )
        content = response["message"]["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            if data.get("confidence", 0) >= 0.65:
                return data
    except (ImportError, Exception):
        pass

    return None


def create_event(event: dict) -> bool:
    """Insert a big deal event with deduplication."""
    conn = get_conn()
    cursor = conn.cursor()

    # Schema migration (idempotent)
    for col, col_type in [
        ("event_type", "TEXT"),
        ("is_rumor", "TEXT"),
        ("counterparty", "TEXT"),
        ("confidence", "REAL"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE funding_events ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate" in str(e).lower() or "already exists" in str(e).lower():
                pass
            else:
                logger.warning("Schema migration warning: %s", e)

    dedup_key = generate_dedup_key(str(event))

    try:
        cursor.execute(
            "SELECT 1 FROM funding_events WHERE source_url = ?", (dedup_key,)
        )
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
    """Run big deals and rumors collector using LLM + keyword heuristics."""
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
            text = " ".join(
                str(data.get(k, "")) for k in ["title", "summary", "content"]
            )

            if not any(kw.lower() in text.lower() for kw in BIG_DEAL_KEYWORDS):
                continue

            result = try_llm_extract(text)
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
                logger.info("Created event: %s — %s", company, result['event_type'])

        except (json.JSONDecodeError, KeyError, TypeError, sqlite3.Error) as e:
            logger.warning("Error processing signal: %s", e)
            continue

    conn.close()
    logger.info("Big Deals collector complete. Created %s high-value events.", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
