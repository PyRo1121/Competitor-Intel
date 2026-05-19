#!/usr/bin/env python3
"""Hacker News collector - monitors Show HN and high-signal discussions."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from utils.http import safe_request

logger = logging.getLogger("hackernews")

HN_API = "https://hacker-news.firebaseio.com/v0"
SHOW_HN = f"{HN_API}/showstories.json"
TOP_STORIES = f"{HN_API}/topstories.json"


def fetch_story_ids(endpoint: str, limit: int = 50) -> List[int]:
    resp = safe_request(endpoint, timeout=15.0)
    if resp is None:
        return []
    try:
        ids = resp.json()
        return ids[:limit] if ids else []
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to parse HN story IDs: %s", exc)
        return []


def fetch_story(story_id: int) -> Dict[str, Any]:
    resp = safe_request(f"{HN_API}/item/{story_id}.json", timeout=10.0)
    if resp is None:
        return {}
    try:
        return resp.json()
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to fetch HN story %d: %s", story_id, exc)
        return {}


def is_startup_relevant(story: Dict[str, Any]) -> bool:
    if not story:
        return False
    title = (story.get("title") or "").lower()
    text = (story.get("text") or "").lower()
    combined = f"{title} {text}"
    keywords = [
        "launch", "show hn", "startup", "funding", "raised",
        "series a", "series b", "seed", "acquired", "open source",
        "github", "api", "saas", "developer tools", "ai",
        "machine learning", "llm", "productivity", "cursor",
        "perplexity", "anthropic", "openai", "notion", "linear",
        "elevenlabs", "runway", "midjourney", "stability",
    ]
    return any(kw in combined for kw in keywords)


def extract_company_names(title: str, text: str) -> List[str]:
    combined = f"{title} {text}"
    companies = []
    candidates = [
        "Cursor", "Perplexity", "Cognition", "Harvey", "ElevenLabs",
        "Runway", "Linear", "Notion", "Arc", "Coda", "Height",
        "Mem", "Limitless", "Rewind", "Adept", "Anthropic",
        "OpenAI", "Midjourney", "Stability AI", "Cohere", "Replicate",
        "Hugging Face", "LangChain", "Pinecone", "Vercel", "Supabase",
        "Stripe", "Figma", "Airtable", "Zapier", "Webflow",
    ]
    for c in candidates:
        if c.lower() in combined.lower():
            companies.append(c)
    return list(set(companies))


def classify_story_type(story: Dict[str, Any]) -> str:
    title = (story.get("title") or "").lower()
    if title.startswith("show hn"):
        return "show_hn"
    if title.startswith("ask hn"):
        return "ask_hn"
    if any(w in title for w in ["launch", "launched", "introducing"]):
        return "launch"
    if any(w in title for w in ["funding", "raised", "series", "seed"]):
        return "funding"
    if any(w in title for w in ["acquired", "acquisition", "bought"]):
        return "acquisition"
    if "open source" in title:
        return "open_source"
    return "discussion"


def resolve_company_id(cursor, companies: List[str]) -> Optional[int]:
    if not companies:
        return None
    cursor.execute(
        "SELECT id FROM companies WHERE name = ? COLLATE NOCASE",
        (companies[0],),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def store_signals(stories: List[Dict[str, Any]]) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    stored = 0
    detected_at = datetime.now(timezone.utc).isoformat()

    for story in stories:
        title = story.get("title", "")
        text = story.get("text", "")
        companies = extract_company_names(title, text)
        company_id = resolve_company_id(cursor, companies)
        url = story.get("url") or f"https://news.ycombinator.com/item?id={story['id']}"
        data = {
            "title": title,
            "text": (text or "")[:1000],
            "url": url,
            "link": url,
            "score": story.get("score"),
            "descendants": story.get("descendants"),
            "by": story.get("by"),
            "time": story.get("time"),
            "companies_detected": companies,
            "story_type": classify_story_type(story),
            "kind": "hackernews",
            "category": classify_story_type(story),
        }
        if insert_raw_signal_dedup(
            cursor,
            "hackernews",
            url,
            data,
            company_id=company_id,
            detected_at=detected_at,
        ):
            stored += 1

    conn.commit()
    conn.close()
    logger.info("Stored %d new Hacker News signals", stored)
    return stored


def run() -> int:
    story_ids = fetch_story_ids(SHOW_HN, limit=30)
    story_ids += fetch_story_ids(TOP_STORIES, limit=30)
    story_ids = list(set(story_ids))
    logger.info("Fetching %d HN stories", len(story_ids))
    stories = []
    for sid in story_ids:
        story = fetch_story(sid)
        if story and is_startup_relevant(story):
            stories.append(story)
    logger.info("Found %d startup-relevant stories", len(stories))
    if not stories:
        return 0
    return store_signals(stories)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
