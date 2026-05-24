#!/usr/bin/env python3
"""Product Hunt collector - monitors product launches via RSS."""

import logging
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree as ET

from db.connection import get_conn
from db.ingest import get_company_id, insert_raw_signal_dedup
from utils.http import fetch_text

logger = logging.getLogger("producthunt")

FEED_URL = "https://www.producthunt.com/feed"


def fetch_feed() -> list[dict[str, Any]]:
    body = fetch_text(FEED_URL, timeout=20.0)
    if not body:
        return []
    try:
        root = ET.fromstring(body)
        items = []
        for item in root.findall(".//item"):
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")
            pub_date = item.find("pubDate")
            creator = item.find("{http://purl.org/dc/elements/1.1/}creator")
            if title is None or link is None:
                continue
            items.append(
                {
                    "title": title.text or "",
                    "url": link.text or "",
                    "description": (desc.text or "")[:500] if desc is not None else "",
                    "published": pub_date.text if pub_date is not None else None,
                    "maker": creator.text if creator is not None else None,
                }
            )
        logger.info("Fetched %d Product Hunt items", len(items))
        return items
    except ET.ParseError as exc:
        logger.error("Failed to parse Product Hunt feed: %s", exc)
        return []


def extract_company_names(title: str, description: str) -> list[str]:
    text = f"{title} {description}"
    keywords = [
        "Cursor",
        "Perplexity",
        "Cognition",
        "Harvey",
        "ElevenLabs",
        "Runway",
        "Linear",
        "Notion",
        "Arc",
        "Coda",
        "Height",
        "Mem",
        "Limitless",
        "Rewind",
        "Adept",
        "Anthropic",
        "OpenAI",
        "Midjourney",
        "Stability AI",
        "Cohere",
        "Replicate",
        "Hugging Face",
        "LangChain",
        "Pinecone",
        "Weaviate",
        "Chroma",
        "LlamaIndex",
        "Vercel",
        "Supabase",
        "Stripe",
        "Figma",
        "Airtable",
        "Zapier",
        "Make",
        "Webflow",
    ]
    return list({kw for kw in keywords if kw.lower() in text.lower()})


def classify_launch_type(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    if any(w in text for w in ["api", "sdk", "developer"]):
        return "api_launch"
    if any(w in text for w in ["mobile", "ios", "android", "app"]):
        return "mobile_launch"
    if any(w in text for w in ["integration", "plugin", "extension"]):
        return "integration"
    if any(w in text for w in ["beta", "early access", "waitlist"]):
        return "beta_launch"
    if any(w in text for w in ["v2", "version 2", "redesign", "relaunch"]):
        return "major_update"
    return "product_launch"


def store_signals(items: list[dict[str, Any]]) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    stored = 0
    detected_at = datetime.now(UTC).isoformat()

    for item in items:
        url = item.get("url") or ""
        if not url:
            continue
        companies = extract_company_names(item["title"], item["description"])
        company_id = get_company_id(companies[0]) if companies else None
        data = {
            "title": item["title"],
            "description": item["description"],
            "url": url,
            "link": url,
            "maker": item["maker"],
            "published": item["published"],
            "companies_detected": companies,
            "launch_type": classify_launch_type(item["title"], item["description"]),
            "kind": "product_launch",
            "category": classify_launch_type(item["title"], item["description"]),
        }
        if insert_raw_signal_dedup(
            cursor,
            "producthunt",
            url,
            data,
            company_id=company_id,
            detected_at=detected_at,
        ):
            stored += 1

    conn.commit()
    conn.close()
    logger.info("Stored %d new Product Hunt signals", stored)
    return stored


def run() -> int:
    items = fetch_feed()
    if not items:
        return 0
    return store_signals(items)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
