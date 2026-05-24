"""
Funding Rumor Detector
Extracts potential funding signals from raw text using regex patterns.
Creates structured funding_events when confidence threshold is met.
"""

import json
import logging
import re
import sqlite3

from db.connection import get_conn
from db.ingest import get_company_id

from collectors.pipeline_guard import (
    strict_pipeline_blocks_funding_events,
    strict_pipeline_blocks_legacy_events,
)

logger = logging.getLogger(__name__)


def parse_valuation(text: str) -> tuple[int, str] | None:
    """Extract USD valuation from text (e.g. $3B+, $40M). Returns (amount_usd, label)."""
    patterns = [
        (r"\$?([\d.]+)\s*(B|billion)", 1_000_000_000),
        (r"\$([\d.]+)(B|b)\b", 1_000_000_000),
        (r"\$?([\d.]+)\s*(M|million)", 1_000_000),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = float(match.group(1))
        unit = match.group(2).lower()
        usd = int(value * multiplier)
        if "b" in unit:
            return usd, f"${value:g}B"
        return usd, f"${value:g}M"
    return None


def detect_round_type(text: str) -> str | None:
    """Detect funding round type."""
    text_lower = text.lower()
    if "series a" in text_lower:
        return "Series A"
    if "series b" in text_lower:
        return "Series B"
    if "series c" in text_lower:
        return "Series C"
    if "series d" in text_lower:
        return "Series D"
    if "series e" in text_lower:
        return "Series E"
    if "extension" in text_lower:
        return "Extension"
    if "secondary" in text_lower:
        return "Secondary"
    if "raising" in text_lower or "round" in text_lower:
        return "Unknown Round"
    return None


def process_funding_signal(signal: dict) -> bool:
    """Process a raw funding signal and create structured event if possible."""
    if strict_pipeline_blocks_funding_events("funding_rumor_detector"):
        return False
    company_name = signal.get("company") or ""
    company_id = get_company_id(company_name)
    if not company_id:
        return False

    text = signal.get("text", "")
    valuation = parse_valuation(text)
    round_type = detect_round_type(text)

    if valuation or round_type:
        conn = get_conn()
        cursor = conn.cursor()

        valuation_usd = valuation[0] if valuation else None
        cursor.execute(
            """
            INSERT INTO funding_events
            (
                company_id, round_type, amount_usd, valuation_usd, announced_date,
                source, source_url, confidence,
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                round_type or "Unknown",
                None,
                valuation_usd,
                (signal.get("posted_at") or "")[:10] if signal.get("posted_at") else None,
                "X / Grok",
                signal.get("url"),
                signal.get("confidence", 0.7),
            ),
        )

        conn.commit()
        conn.close()
        logger.info("Created funding event for company_id=%s round=%s", company_id, round_type)
        return True

    return False


def run_funding_detector():
    """Scan all unprocessed funding signals and create events."""
    if strict_pipeline_blocks_legacy_events("funding_rumor_detector"):
        return 0
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, company_id, data_json
        FROM raw_signals
        WHERE source = 'x_funding' AND processed = 0
        """
    )
    signals = cursor.fetchall()

    processed = 0
    for sig_id, _company_id, data_json in signals:
        try:
            data = json.loads(data_json)
            if process_funding_signal(data):
                cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
                processed += 1
        except (json.JSONDecodeError, sqlite3.Error) as e:
            logger.error("Error processing signal %s: %s", sig_id, e)

    conn.commit()
    conn.close()
    logger.info("Funding Detector: Processed %d signals into structured events.", processed)
    return processed


if __name__ == "__main__":
    run_funding_detector()
