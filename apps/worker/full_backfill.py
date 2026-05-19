#!/usr/bin/env python3
"""
Full Aggressive Backfill — Extract EVERYTHING from all raw_signals
High-recall mode: process every signal, broad matching, lower thresholds.
"""

import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("full_backfill")

from db.connection import get_conn, DB_PATH





def extract_amount(text: str):
    """Aggressive amount extraction from any text."""
    patterns = [
        r"\$?\s*([0-9,.]+)\s*(billion|b)",
        r"\$?\s*([0-9,.]+)\s*(million|m)",
        r"raised\s*\$?\s*([0-9,.]+)\s*(m|million|b|billion)",
        r"valuation\s*(of|at)?\s*\$?\s*([0-9,.]+)\s*(m|million|b|billion)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                groups = [g for g in m.groups() if g is not None]
                num_str = next(
                    (g for g in groups if g.replace(",", "").replace(".", "").isdigit()),
                    None,
                )
                if not num_str:
                    continue
                num = float(num_str.replace(",", ""))
                unit = next(
                    (g.lower() for g in groups if isinstance(g, str) and g.lower() in ["billion", "b", "million", "m"]),
                    "m",
                )
                multiplier = 1_000_000_000 if unit.startswith("b") else 1_000_000
                return int(num * multiplier)
            except (ValueError, IndexError):
                continue
    return None


def get_all_companies():
    """Load all companies from the database for matching."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM companies")
    companies = {row["name"].lower(): row["id"] for row in cursor.fetchall()}
    conn.close()
    return companies


def generate_dedup_key(text: str) -> str:
    """Generate a short deduplication key from text."""
    return hashlib.md5(text.lower().encode()).hexdigest()[:16]


def full_backfill() -> tuple[int, int]:
    """Aggressively extract intelligence events from all raw signals (high-recall mode)."""
    logger.info("FULL AGGRESSIVE BACKFILL — Processing ALL raw signals")
    conn = get_conn()
    cursor = conn.cursor()

    companies = get_all_companies()
    logger.info("Loaded %s companies for matching", len(companies))

    cursor.execute(
        "SELECT id, source, data_json, processed FROM raw_signals ORDER BY id"
    )
    signals = cursor.fetchall()
    logger.info("Processing %s raw signals...", len(signals))

    created = 0
    skipped = 0

    for row in signals:
        sig_id, source, data_json, processed = row
        text = ""

        if data_json:
            try:
                data = json.loads(data_json)
                for key in ["title", "summary", "content", "description", "text"]:
                    if key in data and data[key]:
                        text += str(data[key]) + " "
                text += " ".join(str(v) for v in data.values() if isinstance(v, str))
            except (json.JSONDecodeError, TypeError):
                text = str(data_json)

        amount = extract_amount(text)
        if not amount:
            skipped += 1
            continue

        # Broad company matching against DB
        company_id = None
        company_name = None
        text_lower = text.lower()
        for name, cid in companies.items():
            if name in text_lower:
                company_id = cid
                company_name = name.title()
                break

        event_type = "Funding Round"
        is_rumor = 0
        if "rumor" in text_lower or "rumoured" in text_lower:
            event_type = "Rumored Round"
            is_rumor = 1
        elif "partnership" in text_lower or "strategic" in text_lower:
            event_type = "Strategic Partnership"

        dedup = generate_dedup_key(text)

        cursor.execute(
            "SELECT 1 FROM intelligence_events WHERE source_url = ?", (dedup,)
        )
        if cursor.fetchone():
            skipped += 1
            continue

        try:
            cursor.execute(
                """
                INSERT INTO intelligence_events
                (company_id, event_type, amount_usd, is_rumor, confidence,
                 source, source_url, raw_signal_id, announced_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    event_type,
                    amount,
                    is_rumor,
                    0.65,
                    source or "full_backfill",
                    dedup,
                    sig_id,
                    datetime.now().strftime("%Y-%m-%d"),
                ),
            )
            created += 1
            if created % 20 == 0:
                logger.info("  %s events extracted so far...", created)
        except sqlite3.Error as e:
            logger.error("Insert error: %s", e)
            continue

    conn.commit()
    conn.close()

    logger.info("FULL BACKFILL COMPLETE")
    logger.info("   Created: %s new intelligence events", created)
    logger.info("   Skipped: %s (no amount or duplicate)", skipped)
    return created, skipped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    full_backfill()
