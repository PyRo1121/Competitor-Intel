#!/usr/bin/env python3
"""
Report Generator
Creates structured text reports from intelligence events.

These are plain text drafts; no posting to any platform occurs.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("report_generator")

from db.connection import get_conn, DB_PATH


def generate_reports(limit: int = 6) -> list[dict]:
    """Generate text reports from recent intelligence events."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            ie.event_type,
            c.name as company,
            ie.amount_usd,
            ie.valuation_usd,
            ie.lead_investor,
            ie.counterparty,
            ie.is_rumor,
            ie.confidence,
            ie.source
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        ORDER BY ie.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    events = cursor.fetchall()
    conn.close()

    reports = []
    for event in events:
        company = event["company"] or "Unknown"
        amount = event["amount_usd"]
        is_rumor = event["is_rumor"]
        confidence = event["confidence"] or 0

        # Summary paragraph
        if amount and amount > 1_000_000_000:
            hook = f"{company} raised ${amount / 1_000_000_000:.1f}B"
        elif amount:
            hook = f"{company} raised ${amount / 1_000_000:.0f}M"
        else:
            hook = f"{company} -- {event['event_type']}"

        summary = f"""{hook}

Event: {event['event_type']}
Confidence: {confidence:.0%}
Source: {event['source'] or 'Unknown'}
Status: {'Rumor (unconfirmed)' if is_rumor else 'Confirmed'}
"""

        reports.append(
            {
                "company": company,
                "summary": summary,
                "confidence": confidence,
            }
        )

    return reports


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    reports = generate_reports(4)
    for r in reports:
        logger.info("\n=== %s ===", r['company'])
        logger.info(r["summary"])
