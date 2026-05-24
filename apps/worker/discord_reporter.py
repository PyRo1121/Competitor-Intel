"""
Discord Reporter - Generates rich, professional embeds + sends them
Ready for webhook or direct bot use
"""

import logging
from datetime import UTC, datetime

import httpx
from db.connection import get_conn
from utils.http import get_http_client

logger = logging.getLogger("discord_reporter")


def get_top_signals(limit: int = 8) -> list[dict]:
    """Get the most important recent signals for Discord."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            c.name,
            'X Post' as type,
            x.text,
            x.likes,
            x.url,
            x.posted_at
        FROM x_posts x
        JOIN companies c ON x.company_id = c.id
        ORDER BY x.likes DESC
        LIMIT ?
    """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    signals = []
    for row in rows:
        signals.append(
            {
                "company": row[0],
                "type": row[1],
                "content": row[2][:280] + "..." if len(row[2]) > 280 else row[2],
                "engagement": f"{row[3]:,} likes",
                "url": row[4],
                "timestamp": row[5],
            }
        )
    return signals


def generate_discord_embeds() -> list[dict]:
    """Create rich Discord embed objects."""
    signals = get_top_signals(6)

    if not signals:
        return []

    embeds = []

    # Main summary embed
    main_embed = {
        "title": "🚀 Competitor Intelligence Brief",
        "description": "Top signals from the last 24 hours across 16 AI companies",
        "color": 0x00FFAA,
        "timestamp": datetime.now(UTC).isoformat(),
        "footer": {"text": "Hermes Competitor Intel • Powered by Grok 4.3"},
        "fields": [],
    }

    for sig in signals[:4]:
        main_embed["fields"].append(
            {
                "name": f"{sig['company']} — {sig['type']}",
                "value": f"{sig['content']}\n{sig['engagement']} • [View]({sig['url']})",
                "inline": False,
            }
        )

    embeds.append(main_embed)

    # Individual high-engagement post embeds
    for sig in signals[:2]:
        embed = {
            "title": f"🔥 {sig['company']} High-Signal Update",
            "description": sig["content"],
            "color": 0x5865F2,
            "url": sig["url"],
            "fields": [
                {"name": "Engagement", "value": sig["engagement"], "inline": True},
                {"name": "Source", "value": "X / Twitter", "inline": True},
            ],
            "footer": {"text": "Hermes Competitor Intel"},
        }
        embeds.append(embed)

    return embeds


def send_to_discord(webhook_url: str, content: str | None = None) -> bool:
    """
    Send the latest intelligence as rich embeds to a Discord webhook.
    Usage: send_to_discord("https://discord.com/api/webhooks/...")
    """
    if not webhook_url:
        logger.warning("No webhook URL provided.")
        return False

    embeds = generate_discord_embeds()
    if not embeds:
        logger.info("No signals to send.")
        return False

    payload = {"content": content or "📡 **Competitor Intelligence Update**", "embeds": embeds}

    try:
        response = get_http_client().post(webhook_url, json=payload, timeout=15)
        response.raise_for_status()
        logger.info("Sent %s embeds to Discord", len(embeds))
        return True
    except httpx.HTTPError as e:
        logger.error("Failed to send to Discord: %s", e)
        return False


def get_discord_payload():
    """Final payload ready to send via Discord webhook or bot."""
    embeds = generate_discord_embeds()
    return {"content": "📡 **Competitor Intelligence Update**", "embeds": embeds}


if __name__ == "__main__":
    payload = get_discord_payload()
    logger.info("Discord payload ready:")
    logger.info("  - %s embeds generated", len(payload["embeds"]))
    logger.info(
        "  - Top companies: %s", [e["title"].split("—")[0].strip() for e in payload["embeds"][:3]]
    )
