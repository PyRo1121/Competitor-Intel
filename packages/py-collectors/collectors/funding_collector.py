#!/usr/bin/env python3
"""
Funding Extraction Collector
Extracts funding events from raw signals using regex patterns.
Loads companies dynamically from DB.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("funding_collector")

from db.connection import get_conn, DB_PATH





def extract_amount(text: str):
    """Extract USD amount from text using regex patterns."""
    if not text:
        return None
    patterns = [
        r"\$?\s*([0-9,.]+)\s*(billion|b)",
        r"\$?\s*([0-9,.]+)\s*(million|m)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            num_str = m.group(1).replace(",", "").strip()
            if not num_str:
                continue
            try:
                num = float(num_str)
            except ValueError:
                continue
            unit = m.group(2).lower()
            multiplier = 1_000_000_000 if unit.startswith("b") else 1_000_000
            return int(num * multiplier)
    return None


def get_companies(conn: sqlite3.Connection):
    """Load all companies with normalized name variations for better matching."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM companies")
    companies = {}
    for row in cursor.fetchall():
        cid = row["id"]
        name = row["name"]
        norm = name.lower().replace(" ", "").replace(".", "").replace(",", "")
        companies[norm] = cid
        # Also store original lowercased version
        companies[name.lower()] = cid
    return companies


def create_event(event: dict) -> bool:
    """Insert a funding event with deduplication."""
    conn = get_conn()
    cursor = conn.cursor()
    dedup = event.get("source_url") or hash(str(event))

    try:
        cursor.execute(
            "SELECT 1 FROM intelligence_events WHERE source_url = ?", (dedup,)
        )
        if cursor.fetchone():
            return False

        cursor.execute(
            """
            INSERT INTO intelligence_events
            (company_id, event_type, amount_usd, valuation_usd, lead_investor,
             is_rumor, confidence, source, source_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("company_id"),
                event.get("event_type", "Funding Round"),
                event.get("amount_usd"),
                event.get("valuation_usd"),
                event.get("investor"),
                1 if event.get("is_rumor") else 0,
                event.get("confidence", 0.7),
                event.get("source", "funding_collector"),
                dedup,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("Database error creating event: %s", e)
        return False
    finally:
        conn.close()


def run() -> int:
    """Extract funding events from raw signals."""
    logger.info("Running Funding Extraction Collector")
    conn = get_conn()
    cursor = conn.cursor()
    companies = get_companies(conn)

    cursor.execute(
        "SELECT id, data_json FROM raw_signals ORDER BY detected_at DESC LIMIT 400"
    )
    rows = cursor.fetchall()
    conn.close()

    created = 0
    for row in rows:
        try:
            data = json.loads(row["data_json"])
            text = " ".join(
                str(data.get(k, "")) for k in ["title", "summary", "content"]
            )

            amount = extract_amount(text)
            if not amount or amount < 5_000_000:
                continue

            # Event type detection
            event_type = "Funding Round"
            is_rumor = "rumor" in text.lower() or "rumoured" in text.lower()
            if is_rumor:
                event_type = "Rumored Round"
            elif "partnership" in text.lower() or "strategic" in text.lower():
                event_type = "Strategic Partnership"

            # Improved company matching
            company_id = None
            text_lower = text.lower().replace(" ", "").replace(".", "").replace(",", "")
            for norm_name, cid in companies.items():
                if norm_name in text_lower:
                    company_id = cid
                    break

            event = {
                "company_id": company_id,
                "event_type": event_type,
                "amount_usd": amount,
                "is_rumor": is_rumor,
                "source": "funding_collector",
                "confidence": 0.75,
            }

            if create_event(event):
                created += 1
                logger.info("Created event: %s — %s $%s", company_id, event_type, amount)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Error processing signal %s: %s", row['id'], e)
            continue

    logger.info("Funding extraction complete. Created %s events.", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
