#!/usr/bin/env python3
"""
Discord Intelligence Reporter
Posts rich daily competitor intelligence briefs to Discord with retry logic.
"""

import logging
import os
import sys
import time
from pathlib import Path

import httpx

# Ensure parent directory is importable
sys.path.insert(0, str(Path(__file__).parent))
from utils.http import get_http_client

from daily_brief import format_for_discord
from daily_brief import generate_daily_brief as gen_brief

logger = logging.getLogger("discord_report")

# Discord rate limits: implement jitter
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds with exponential backoff


def post_to_discord(embed: dict, webhook_url: str | None = None) -> bool:
    """Post embed to Discord webhook with retry logic.

    Args:
        embed: Discord embed dict
        webhook_url: Optional explicit URL. Falls back to DISCORD_WEBHOOK_URL env var.

    Returns:
        True on success, False otherwise
    """
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

    if not url:
        logger.warning("DISCORD_WEBHOOK_URL not set — printing to console only")
        logger.info("Embed ready for Discord")
        return False

    client = get_http_client()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.post(
                url,
                json={"embeds": [embed]},
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            # Handle rate limits
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", RETRY_DELAY * attempt)
                logger.warning("Rate limited. Retry after %ss", retry_after)
                time.sleep(float(retry_after))
                continue

            resp.raise_for_status()
            logger.info("Posted to Discord successfully")
            return True

        except httpx.TimeoutException:
            logger.warning("Request timeout (attempt %s/%s)", attempt, MAX_RETRIES)
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 429:
                continue  # handled above
            logger.error("HTTP error: %s", e)
            break  # Don't retry on 4xx client errors
        except httpx.HTTPError as e:
            logger.warning("Request failed (attempt %s/%s): %s", attempt, MAX_RETRIES, e)

        if attempt < MAX_RETRIES:
            delay = RETRY_DELAY * attempt
            logger.info("Retrying in %ss...", delay)
            time.sleep(delay)

    logger.error("Failed to post to Discord after all retries")
    return False


def main():
    """CLI entry point for Discord reporting."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    brief = gen_brief()
    embed = format_for_discord(brief)
    success = post_to_discord(embed)

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
