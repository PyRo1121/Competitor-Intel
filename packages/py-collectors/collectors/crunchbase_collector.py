#!/usr/bin/env python3
"""Crunchbase News RSS collector."""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_conn
from db.ingest import get_company_id, insert_raw_signal_dedup
from utils.http import fetch_text

from collectors.sources_registry import feeds_by_category

logger = logging.getLogger("crunchbase")

COMPANY_KEYWORDS = [
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
    "Vercel",
    "Supabase",
    "Stripe",
    "Figma",
    "Airtable",
    "Zapier",
    "Webflow",
]


def feed_urls() -> list[str]:
    urls = [f.url for f in feeds_by_category("general_startup")]
    if not urls:
        urls = ["https://news.crunchbase.com/feed/"]
    return urls


def fetch_feed(url: str) -> list[dict[str, Any]]:
    body = fetch_text(url, timeout=20.0)
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
            if title is None:
                continue
            items.append(
                {
                    "title": title.text or "",
                    "url": link.text if link is not None else "",
                    "description": (desc.text or "")[:600] if desc is not None else "",
                    "published": pub_date.text if pub_date is not None else None,
                }
            )
        return items
    except ET.ParseError as exc:
        logger.error("Failed to parse %s: %s", url, exc)
        return []


def extract_companies(text: str) -> list[str]:
    return list({kw for kw in COMPANY_KEYWORDS if kw.lower() in text.lower()})


def classify(title: str, desc: str) -> str:
    text = f"{title} {desc}".lower()
    if any(
        w in text
        for w in ["raised", "funding", "series", "seed", "investment", "million", "billion"]
    ):
        return "funding"
    if any(w in text for w in ["acquired", "acquisition", "buys", "merger"]):
        return "acquisition"
    if any(w in text for w in ["launch", "announced", "released", "product", "feature"]):
        return "product_launch"
    return "news"


def store(items: list[dict[str, Any]]) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    stored = 0
    detected_at = datetime.now(UTC).isoformat()

    for item in items:
        companies = extract_companies(item["title"] + " " + item["description"])
        company_id = get_company_id(companies[0]) if companies else None
        url = item.get("url") or ""
        if not url:
            continue
        category = classify(item["title"], item["description"])
        data = {
            "title": item["title"],
            "description": item["description"],
            "url": url,
            "link": url,
            "published": item["published"],
            "companies_detected": companies,
            "kind": "crunchbase_news",
            "category": category,
        }
        if insert_raw_signal_dedup(
            cursor,
            "crunchbase",
            url,
            data,
            company_id=company_id,
            detected_at=detected_at,
        ):
            stored += 1

    conn.commit()
    conn.close()
    logger.info("Stored %d Crunchbase signals", stored)
    return stored


def run() -> int:
    items: list[dict[str, Any]] = []
    for url in feed_urls():
        items.extend(fetch_feed(url))
    if not items:
        return 0
    return store(items)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
