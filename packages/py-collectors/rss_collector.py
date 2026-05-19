#!/usr/bin/env python3
"""
RSS Feed Collector - High-Quality Sources Only
Monitors curated RSS feeds for company mentions and competitive intelligence.
"""

import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import feedparser

logger = logging.getLogger("rss_collector")

from collectors.sources_registry import catalog_summary, rss_feed_dicts
from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup, url_dedup_key
from utils.http import close_http_client, fetch_text

VETTED_RSS_FEEDS = rss_feed_dicts()

RSS_FETCH_WORKERS = 8


def load_company_names() -> List[str]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name, slug, x_handle FROM companies")
    names: List[str] = []
    for row in cursor.fetchall():
        name, slug, handle = row
        if name:
            names.append(name)
        if slug:
            names.append(slug.replace("-", " "))
        if handle:
            names.append(handle.lstrip("@"))
    conn.close()
    return names


def extract_company_mentions(text: str, company_names: List[str]) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    mentions: List[str] = []
    for company in company_names:
        company_lower = company.lower()
        if len(company_lower) < 3:
            continue
        idx = text_lower.find(company_lower)
        if idx >= 0:
            before = idx == 0 or not text_lower[idx - 1].isalnum()
            after = idx + len(company_lower) >= len(text_lower) or not text_lower[
                idx + len(company_lower)
            ].isalnum()
            if before and after:
                mentions.append(company)
    return list(set(mentions))


def parse_feed_body(
    body: str,
    feed_name: str,
    category: str,
    company_names: List[str],
) -> List[Dict]:
    entries: List[Dict] = []
    if not body:
        return entries
    try:
        feed = feedparser.parse(body)
        for entry in feed.entries[:12]:
            published_raw = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_raw and isinstance(published_raw, (tuple, list)) and len(published_raw) >= 6:
                published = tuple(published_raw)[:6]
                pub_date = datetime(*published)  # type: ignore[arg-type]
                if pub_date < datetime.now() - timedelta(days=21):
                    continue
            else:
                pub_date = datetime.now()

            text = f"{entry.get('title') or ''} {entry.get('summary') or ''}"
            companies = extract_company_mentions(text, company_names)

            entries.append(
                {
                    "title": entry.get("title") or "",
                    "link": entry.get("link", ""),
                    "summary": (entry.get("summary") or "")[:600],
                    "published": pub_date.isoformat(),
                    "source": feed_name,
                    "category": category,
                    "mentioned_companies": companies,
                }
            )
    except Exception as exc:
        logger.warning("RSS parse error for %s: %s", feed_name, exc)
    return entries


def fetch_and_parse_feed(
    feed: Dict,
    company_names: List[str],
) -> tuple[str, List[Dict]]:
    body = fetch_text(feed["url"], timeout=25.0)
    entries = parse_feed_body(body or "", feed["name"], feed["category"], company_names)
    return feed["name"], entries


def find_company_id(company_name: str, cursor: sqlite3.Cursor) -> Optional[int]:
    cursor.execute("SELECT id FROM companies WHERE name = ?", (company_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute("SELECT id FROM companies WHERE LOWER(name) = LOWER(?)", (company_name,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        "SELECT id FROM companies WHERE slug = ?",
        (company_name.lower().replace(" ", "-"),),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    known_variations = {
        "huggingface": "Hugging Face",
        "hf": "Hugging Face",
        "llamaindex": "LlamaIndex",
        "elevenlabs": "ElevenLabs",
        "runwayml": "Runway",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "cursor": "Cursor",
        "perplexity": "Perplexity",
    }

    canonical = known_variations.get(company_name.lower())
    if canonical:
        cursor.execute("SELECT id FROM companies WHERE name = ?", (canonical,))
        row = cursor.fetchone()
        if row:
            return row[0]

    return None


def store_signal(entry: Dict, cursor: sqlite3.Cursor) -> int:
    link = entry.get("link", "")
    if not link:
        return 0
    stored = 0
    data = {
        "title": entry["title"],
        "link": link,
        "url": link,
        "summary": entry["summary"],
        "source": entry["source"],
        "category": entry["category"],
        "kind": "rss_blog",
        "mentioned_companies": entry.get("mentioned_companies", []),
    }
    source_name = entry["source"]
    base_key = url_dedup_key(link)

    if entry.get("mentioned_companies"):
        for company in entry["mentioned_companies"]:
            company_id = find_company_id(company, cursor)
            scoped_key = f"{base_key}:{company_id or 0}"
            if insert_raw_signal_dedup(
                cursor,
                source_name,
                link,
                data,
                company_id=company_id,
                detected_at=entry["published"],
                dedup_key=scoped_key,
            ):
                stored += 1
    elif insert_raw_signal_dedup(
        cursor,
        source_name,
        link,
        data,
        detected_at=entry["published"],
        dedup_key=base_key,
    ):
        stored += 1
    return stored


def run_rss_collection() -> int:
    summary = catalog_summary()
    logger.info(
        "Collecting from %s enabled RSS sources (registry: %s enabled / %s total)...",
        len(VETTED_RSS_FEEDS),
        summary["enabled"],
        summary["total"],
    )

    company_names = load_company_names()
    logger.info("Loaded %s company name variations from database", len(company_names))

    total_entries = 0
    linked_signals = 0
    stored_count = 0

    conn = get_conn()
    cursor = conn.cursor()

    with ThreadPoolExecutor(max_workers=RSS_FETCH_WORKERS) as pool:
        futures = {
            pool.submit(fetch_and_parse_feed, feed, company_names): feed
            for feed in VETTED_RSS_FEEDS
        }
        for future in as_completed(futures):
            feed_name, entries = future.result()
            for entry in entries:
                total_entries += 1
                if entry.get("mentioned_companies"):
                    linked_signals += 1
                stored_count += store_signal(entry, cursor)
            if entries:
                logger.info("[OK] %s: %s entries", feed_name, len(entries))

    conn.commit()
    conn.close()
    close_http_client()

    logger.info("RSS collection complete.")
    logger.info("Total entries parsed: %s", total_entries)
    logger.info("New signals stored: %s", stored_count)
    logger.info("Linked to companies: %s", linked_signals)
    logger.info("Unlinked (review needed): %s", total_entries - linked_signals)
    return stored_count


def run() -> int:
    return run_rss_collection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
