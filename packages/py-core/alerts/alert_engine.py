#!/usr/bin/env python3
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from db.connection import get_conn
from utils.http import get_http_client

logger = logging.getLogger("alerts")

ALERT_RULES = {
    "funding": {
        "keywords": ["raised", "funding", "series", "seed", "investment"],
        "min_amount": 1_000_000,
        "channels": ["discord"],
    },
    "acquisition": {
        "keywords": ["acquired", "acquisition", "buys", "purchased", "merger"],
        "channels": ["discord"],
    },
    "launch": {
        "keywords": ["launch", "announced", "released", "introducing", "unveiled"],
        "channels": ["discord"],
    },
    "hiring_spree": {
        "keywords": ["hires", "hiring", "expanding team", "headcount"],
        "min_mentions": 3,
        "channels": ["discord"],
    },
}


def send_discord_alert(webhook_url: str, title: str, description: str, color: int = 0xF59E0B):
    try:
        payload = {
            "embeds": [{
                "title": title,
                "description": description[:2000],
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {"text": "Competitor Intelligence Alert"},
            }]
        }
        resp = get_http_client().post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Discord alert sent: %s", title)
        return True
    except httpx.HTTPError as e:
        logger.error("Failed to send Discord alert: %s", e)
        return False


def classify_event_type(event_data: Dict[str, Any]) -> Optional[str]:
    event_type = event_data.get("event_type", "").lower()
    text = json.dumps(event_data).lower()

    direct_map = {
        "funding": "funding",
        "funding_round": "funding",
        "acquisition": "acquisition",
        "product_launch": "launch",
        "partnership": "partnership",
        "hiring": "hiring_spree",
        "research": None,
    }
    if event_type in direct_map:
        return direct_map[event_type]

    for rule_name, rule in ALERT_RULES.items():
        matches = sum(1 for kw in rule["keywords"] if kw in text)
        if matches >= 2:
            return rule_name
    return None


def check_amount_alert(event_data: Dict[str, Any]) -> bool:
    amount = event_data.get("amount_usd") or 0
    return amount >= ALERT_RULES["funding"]["min_amount"]


def process_recent_events(hours: int = 1) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ie.id, ie.company_id, ie.event_type, ie.amount_usd, ie.source, ie.created_at, c.name
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        WHERE ie.created_at >= datetime('now', ?)
        AND ie.id NOT IN (SELECT event_id FROM alerts_sent WHERE channel = 'discord')
        """,
        (f"-{hours} hours",),
    )
    events = cursor.fetchall()
    sent = 0
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        logger.warning("No DISCORD_WEBHOOK_URL configured, skipping alerts")
        conn.close()
        return 0

    for event in events:
        event_id, company_id, event_type, amount, source, created_at, company_name = event
        alert_type = classify_event_type({"event_type": event_type, "amount_usd": amount})
        if not alert_type:
            continue

        title = f"🚨 {alert_type.upper().replace('_', ' ')} Alert"
        description = f"**{company_name or 'Unknown'}**\n"
        description += f"Event: {event_type}\n"
        if amount:
            description += f"Amount: ${amount / 1_000_000:.1f}M\n"
        description += f"Source: {source}\n"

        colors = {"funding": 0x10B981, "acquisition": 0xF59E0B, "launch": 0x3B82F6, "hiring_spree": 0x8B5CF6}
        if send_discord_alert(webhook, title, description, colors.get(alert_type, 0xF59E0B)):
            cursor.execute(
                "INSERT INTO alerts_sent (event_id, channel, sent_at) VALUES (?, 'discord', ?)",
                (event_id, datetime.now(timezone.utc).isoformat())
            )
            sent += 1

    conn.commit()
    conn.close()
    logger.info("Sent %d alerts for %d recent events", sent, len(events))
    return sent


def run() -> int:
    return process_recent_events(hours=1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
