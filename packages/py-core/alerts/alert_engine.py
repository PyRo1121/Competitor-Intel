#!/usr/bin/env python3
import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any

import httpx
from db.connection import get_conn
from utils.http import get_http_client

logger = logging.getLogger("alerts")

# Default rules when alert_rules table is empty (see also API CRUD on alert_rules).
ALERT_RULES: dict[str, dict[str, Any]] = {
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
            "embeds": [
                {
                    "title": title,
                    "description": description[:2000],
                    "color": color,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "footer": {"text": "Competitor Intelligence Alert"},
                }
            ]
        }
        resp = get_http_client().post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Discord alert sent: %s", title)
        return True
    except httpx.HTTPError as e:
        logger.error("Failed to send Discord alert: %s", e)
        return False


def _parse_event_types(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            types = parsed.get("types") or parsed.get("event_types") or []
            return [str(t) for t in types]
        if isinstance(parsed, list):
            return [str(t) for t in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def load_db_alert_rules(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    """Enabled rows from alert_rules (API-managed)."""
    try:
        cursor.execute(
            """
            SELECT name, company_id, event_types, min_confidence, channel
            FROM alert_rules
            WHERE enabled = 1
            """
        )
    except sqlite3.OperationalError:
        return []
    rules: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        rules.append(
            {
                "name": row[0],
                "company_id": row[1],
                "event_types": _parse_event_types(row[2]),
                "min_confidence": float(row[3] or 0.5),
                "channel": row[4] or "discord",
            }
        )
    return rules


def classify_event_type(event_data: dict[str, Any]) -> str | None:
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
        keywords = rule["keywords"]
        matches = sum(1 for kw in keywords if kw in text)
        if matches >= 2:
            return rule_name
    return None


def match_db_rule(
    rule: dict[str, Any],
    *,
    company_id: int | None,
    event_type: str,
    confidence: float,
    amount_usd: int | None,
) -> bool:
    if rule.get("company_id") is not None and rule["company_id"] != company_id:
        return False
    if confidence < rule.get("min_confidence", 0.5):
        return False
    types = rule.get("event_types") or []
    if types:
        et = (event_type or "").lower()
        if not any(t.lower() in et or et in t.lower() for t in types):
            return False
    return not (
        "funding" in (rule.get("name") or "").lower()
        and amount_usd
        and amount_usd < int(ALERT_RULES["funding"]["min_amount"])
    )


def resolve_alert_label(
    event_data: dict[str, Any],
    db_rules: list[dict[str, Any]],
) -> str | None:
    company_id = event_data.get("company_id")
    event_type = event_data.get("event_type") or ""
    confidence = float(event_data.get("confidence") or 0.7)
    amount = event_data.get("amount_usd")

    for rule in db_rules:
        if match_db_rule(
            rule,
            company_id=company_id,
            event_type=event_type,
            confidence=confidence,
            amount_usd=amount,
        ):
            return rule["name"]

    return classify_event_type(event_data)


def check_amount_alert(event_data: dict[str, Any]) -> bool:
    amount = event_data.get("amount_usd") or 0
    return amount >= int(ALERT_RULES["funding"]["min_amount"])


def process_recent_events(hours: int = 1) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    db_rules = load_db_alert_rules(cursor)
    cursor.execute(
        """
        SELECT ie.id, ie.company_id, ie.event_type, ie.amount_usd, ie.source,
               ie.created_at, ie.confidence, c.name
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
        event_id, company_id, event_type, amount, source, created_at, confidence, company_name = (
            event
        )
        payload = {
            "event_type": event_type,
            "amount_usd": amount,
            "company_id": company_id,
            "confidence": confidence,
        }
        alert_type = resolve_alert_label(payload, db_rules)
        if not alert_type:
            continue
        if alert_type == "funding" and not check_amount_alert(payload):
            continue

        title = f"🚨 {alert_type.upper().replace('_', ' ')} Alert"
        description = f"**{company_name or 'Unknown'}**\n"
        description += f"Event: {event_type}\n"
        if amount:
            description += f"Amount: ${amount / 1_000_000:.1f}M\n"
        description += f"Source: {source}\n"

        colors = {
            "funding": 0x10B981,
            "acquisition": 0xF59E0B,
            "launch": 0x3B82F6,
            "hiring_spree": 0x8B5CF6,
        }
        reserved_at = datetime.now(UTC).isoformat()
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO alerts_sent (event_id, channel, sent_at)
                VALUES (?, 'discord', ?)
                """,
                (event_id, reserved_at),
            )
        except sqlite3.IntegrityError:
            continue
        if cursor.rowcount == 0:
            continue
        conn.commit()
        if send_discord_alert(webhook, title, description, colors.get(alert_type, 0xF59E0B)):
            sent += 1
        else:
            cursor.execute(
                (
                    "DELETE FROM alerts_sent WHERE event_id = ? "
                    "AND channel = 'discord' AND sent_at = ?"
                ),
                (event_id, reserved_at),
            )
            conn.commit()

    conn.commit()
    conn.close()
    logger.info("Sent %d alerts for %d recent events", sent, len(events))
    return sent


def run() -> int:
    return process_recent_events(hours=1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
