#!/usr/bin/env python3
"""
YouTube Channel Monitor
Monitors specified YouTube channels for product announcements, funding news,
and competitive intelligence signals.

Uses RSS feeds as primary source with yt-dlp as fallback.
Install yt-dlp for best results: pip install yt-dlp

Setup:
1. Add channel IDs to YOUTUBE_CHANNELS below
2. Install yt-dlp: pip install yt-dlp
3. Run: python3 youtube_collector.py
4. Or integrate into cron: runs automatically with other collectors
"""

import hashlib
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import feedparser

logger = logging.getLogger("youtube_collector")

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_conn
from db.ingest import get_company_id, insert_raw_signal_dedup, url_dedup_key

# YouTube channels to monitor (channel_id: display_name)
YOUTUBE_CHANNELS = {
    "UC_x5XG1OV2P6uZZ5FSM9Ttw": "Google for Developers",
    "UCFT8CB4NBEE0i3JoFNbu_gw": "Microsoft",
    "UCm9K6r3N--bCayJxOQI5h-w": "OpenAI",
    "UCrDwWp7EBBv4NwvScIpBDOA": "Anthropic",
    "UCcefcZRL2oaA_uBNeo5UOWg": "Y Combinator",
    "UCrMmyBpVBC-1TWLKWxXxN1w": "TechCrunch",
    "UCri5S-88ib_2Ugu08kES3Yg": "The Verge",
    "UC0v-ta8aD4_Ge7Z8j-WPTLQ": "Lex Fridman",
    "UCe0TLA0EsQbECEjuFLq0uXA": "a16z",
    "UCWxklhEba5C2h6HJqGKx1uw": "Sequoia Capital",
}

CHANNEL_COMPANY_MAP = {
    "UCm9K6r3N--bCayJxOQI5h-w": "OpenAI",
    "UCrDwWp7EBBv4NwvScIpBDOA": "Anthropic",
    "UC_x5XG1OV2P6uZZ5FSM9Ttw": "Google",
    "UCFT8CB4NBEE0i3JoFNbu_gw": "Microsoft",
}

HIGH_SIGNAL_KEYWORDS = [
    "funding", "raised", "series a", "series b", "series c", "seed round",
    "valuation", "million", "billion", "invest", "acquire", "acquisition",
    "launch", "new product", "announcement", "partnership", "collaboration",
    "ipo", "public offering", "merger", "startup", "unicorn",
    "ai model", "llm", "agent", "autonomous",
]


def extract_video_id(entry: dict) -> str:
    """Resolve a YouTube video ID from RSS/yt-dlp entry fields."""
    for key in ("yt_videoid", "video_id"):
        value = entry.get(key)
        if value:
            return str(value)

    entry_id = str(entry.get("id", ""))
    if entry_id.startswith("yt:video:"):
        return entry_id.rsplit(":", 1)[-1]

    link = str(entry.get("link", ""))
    if link:
        parsed = urlparse(link)
        if parsed.hostname and "youtu" in parsed.hostname:
            if parsed.path.startswith("/watch"):
                query = parse_qs(parsed.query)
                if query.get("v"):
                    return query["v"][0]
            if parsed.path.startswith("/shorts/"):
                return parsed.path.split("/")[2]
            if parsed.path.startswith("/embed/"):
                return parsed.path.split("/")[2]

    return ""


def normalize_entry(entry: dict, channel_id: str) -> Dict:
    """Build a consistent video entry dict for downstream storage."""
    video_id = extract_video_id(entry)
    link = entry.get("link") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else "")
    return {
        "video_id": video_id,
        "title": entry.get("title", ""),
        "description": entry.get("description") or entry.get("summary", ""),
        "link": link,
        "published": entry.get("published", ""),
        "channel_id": channel_id,
    }


def fetch_channel_feed(channel_id: str) -> List[Dict]:
    """Fetch recent videos from a YouTube channel via RSS or fallback methods."""
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    try:
        feed = feedparser.parse(rss_url)
        if getattr(feed, "bozo", 0) and not feed.entries:
            logger.warning("RSS parse issue for channel %s: %s", channel_id, getattr(feed, "bozo_exception", ""))

        entries = []
        for entry in feed.entries[:10]:
            normalized = normalize_entry(entry, channel_id)
            if normalized["video_id"] or normalized["link"]:
                entries.append(normalized)

        if entries:
            return entries

        return fetch_with_ytdlp(channel_id)

    except Exception as e:
        logger.error("Error fetching feed for channel %s: %s", channel_id, e)
        return []


def fetch_with_ytdlp(channel_id: str) -> List[Dict]:
    """Fetch videos using yt-dlp as fallback (no API key needed)."""
    try:
        import subprocess

        channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
        result = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-json", "--playlist-end", "10", channel_url],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.debug("yt-dlp failed for %s: %s", channel_id, result.stderr.strip()[:200])
            return []

        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(
                    normalize_entry(
                        {
                            "id": data.get("id", ""),
                            "title": data.get("title", ""),
                            "description": data.get("description", ""),
                            "link": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                            "published": data.get("upload_date", ""),
                        },
                        channel_id,
                    )
                )
            except json.JSONDecodeError:
                continue

        return entries
    except FileNotFoundError:
        logger.debug("yt-dlp not installed, skipping fallback")
        return []
    except Exception as e:
        logger.error("yt-dlp fallback error: %s", e)
        return []


def extract_signal_score(text: str) -> float:
    """Score a video title/description for signal relevance (0.0-1.0)."""
    text_lower = text.lower()

    matches = sum(1 for kw in HIGH_SIGNAL_KEYWORDS if kw in text_lower)
    funding_terms = ["raised", "funding", "series", "million", "billion", "valuation"]
    funding_matches = sum(1 for term in funding_terms if term in text_lower)

    score = (matches * 0.1) + (funding_matches * 0.15)
    return min(score, 1.0)


def generate_video_hash(video_id: str, title: str) -> str:
    """Generate deduplication hash for a video."""
    key = video_id or title
    return hashlib.md5(key.encode()).hexdigest()[:16]


def store_youtube_signal(
    entry: Dict,
    channel_name: str,
    channel_id: str,
    score: float,
) -> bool:
    if score < 0.2:
        return False

    if not entry.get("video_id") and not entry.get("link"):
        logger.debug("Skipping video without id or link: %s", entry.get("title", "")[:80])
        return False

    link = entry.get("link") or ""
    if not link:
        return False

    company_id = None
    mapped_name = CHANNEL_COMPANY_MAP.get(channel_id)
    if mapped_name:
        company_id = get_company_id(mapped_name)

    conn = get_conn()
    cursor = conn.cursor()
    try:
        dedup_key = url_dedup_key(link)
        payload = {
            "video_id": entry["video_id"],
            "title": entry["title"],
            "description": (entry.get("description") or "")[:500],
            "link": link,
            "url": link,
            "published": entry["published"],
            "channel": channel_name,
            "channel_id": channel_id,
            "relevance_score": score,
            "kind": "youtube_video",
        }
        if mapped_name:
            payload["channel_company"] = mapped_name
        inserted = insert_raw_signal_dedup(
            cursor,
            "youtube",
            link,
            payload,
            company_id=company_id,
            dedup_key=dedup_key,
        )
        if inserted:
            conn.commit()
        return inserted
    except sqlite3.Error as exc:
        logger.error("Database error storing YouTube signal: %s", exc)
        return False
    finally:
        conn.close()


def run_youtube_collection() -> Dict[str, int]:
    """Run YouTube collection for all configured channels."""
    logger.info("Starting YouTube channel monitor for %d channels", len(YOUTUBE_CHANNELS))

    stats = {"processed": 0, "stored": 0, "channels": 0}

    for channel_id, channel_name in YOUTUBE_CHANNELS.items():
        logger.info("Checking channel: %s", channel_name)

        entries = fetch_channel_feed(channel_id)
        if not entries:
            logger.warning("No videos returned for %s (%s)", channel_name, channel_id)
            continue

        stats["channels"] += 1
        channel_stored = 0

        for entry in entries:
            stats["processed"] += 1

            text = f"{entry['title']} {entry.get('description', '')}"
            score = extract_signal_score(text)

            if score >= 0.2 and store_youtube_signal(entry, channel_name, channel_id, score):
                stats["stored"] += 1
                channel_stored += 1
                logger.info("  Stored: %s (score=%.2f)", entry["title"][:60], score)

        if channel_stored > 0:
            logger.info("  Channel %s: %d new signals", channel_name, channel_stored)

    logger.info(
        "YouTube collection complete: %d/%d videos stored from %d channels",
        stats["stored"],
        stats["processed"],
        stats["channels"],
    )
    return stats


def run() -> int:
    """Pipeline entry point used by daily_intel and other orchestrators."""
    return run_youtube_collection()["stored"]


def list_configured_channels() -> None:
    """Print configured YouTube channels."""
    logger.info("Configured YouTube channels:")
    for channel_id, name in YOUTUBE_CHANNELS.items():
        logger.info("  %s: %s", name, f"https://youtube.com/channel/{channel_id}")


def add_channel(channel_id: str, name: str) -> bool:
    """Add a new YouTube channel to monitor (runtime only; edit file to persist)."""
    if not re.match(r"^UC[a-zA-Z0-9_-]{22}$", channel_id):
        logger.error("Invalid channel ID format: %s", channel_id)
        return False

    YOUTUBE_CHANNELS[channel_id] = name
    logger.info("Added channel: %s (%s)", name, channel_id)
    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_configured_channels()
    elif len(sys.argv) > 1 and sys.argv[1] == "--add" and len(sys.argv) >= 4:
        add_channel(sys.argv[2], sys.argv[3])
    else:
        run_youtube_collection()
