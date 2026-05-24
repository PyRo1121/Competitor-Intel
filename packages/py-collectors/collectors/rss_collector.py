#!/usr/bin/env python3
"""
RSS Feed Collector - High-Quality Sources Only
Monitors curated RSS feeds for company mentions and competitive intelligence.
"""

import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import feedparser

logger = logging.getLogger("rss_collector")

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup, url_dedup_key
from utils.http import close_http_client, fetch_text

from collectors.entity_extract import extract_entities_from_text, text_has_hype
from collectors.sources_registry import catalog_summary, rss_feed_dicts

VETTED_RSS_FEEDS = rss_feed_dicts()

RSS_FETCH_WORKERS = 8
RSS_ENTRIES_PER_FEED = 25
RSS_LOOKBACK_DAYS = 30
RSS_SUMMARY_MAX = 1200

FUNDING_SIGNAL_KEYWORDS = (
    "raised",
    "raises",
    "funding",
    "series a",
    "series b",
    "series c",
    "seed round",
    "pre-seed",
    "valuation",
    "led by",
    "million round",
    "billion",
    "closes",
    "secured",
    "investors",
    "acquired",
    "acquisition",
)


def load_company_names() -> list[str]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name, slug, x_handle FROM companies")
    names: list[str] = []
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


def extract_company_mentions(text: str, company_names: list[str]) -> list[str]:
    if not text:
        return []
    text_lower = text.lower()
    mentions: list[str] = []
    for company in company_names:
        company_lower = company.lower()
        if len(company_lower) < 3:
            continue
        idx = text_lower.find(company_lower)
        if idx >= 0:
            before = idx == 0 or not text_lower[idx - 1].isalnum()
            after = (
                idx + len(company_lower) >= len(text_lower)
                or not text_lower[idx + len(company_lower)].isalnum()
            )
            if before and after:
                mentions.append(company)
    return list(set(mentions))


def entry_is_high_signal(text: str, category: str) -> bool:
    """Funding/M&A language or VC-tier feed — store even before company match."""
    if category in ("vc", "general_startup"):
        t = (text or "").lower()
        if any(kw in t for kw in FUNDING_SIGNAL_KEYWORDS):
            return True
    return False


def _entry_body(entry: Any) -> str:
    parts = [
        entry.get("title") or "",
        entry.get("summary") or "",
        entry.get("description") or "",
    ]
    content = entry.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("value"):
                parts.append(str(block["value"]))
    elif isinstance(content, dict) and content.get("value"):
        parts.append(str(content["value"]))
    return " ".join(p for p in parts if p)


def parse_feed_body(
    body: str,
    feed_name: str,
    category: str,
    company_names: list[str],
) -> list[dict]:
    entries: list[dict] = []
    if not body:
        return entries
    try:
        feed = feedparser.parse(body)
        for entry in feed.entries[:RSS_ENTRIES_PER_FEED]:
            published_raw = entry.get("published_parsed") or entry.get("updated_parsed")
            if (
                published_raw
                and isinstance(published_raw, (tuple, list))
                and len(published_raw) >= 6
            ):
                published = tuple(published_raw)[:6]
                pub_date = datetime(*published)  # type: ignore[arg-type]
                if pub_date < datetime.now() - timedelta(days=RSS_LOOKBACK_DAYS):
                    continue
            else:
                pub_date = datetime.now()

            entry_text = _entry_body(entry)
            companies = extract_company_mentions(entry_text, company_names)
            high_signal = entry_is_high_signal(entry_text, category) or text_has_hype(entry_text)
            if high_signal:
                for name in extract_entities_from_text(entry_text):
                    if name not in companies:
                        companies.append(name)

            entries.append(
                {
                    "title": entry.get("title") or "",
                    "link": entry.get("link", ""),
                    "summary": entry_text[:RSS_SUMMARY_MAX],
                    "published": pub_date.isoformat(),
                    "source": feed_name,
                    "category": category,
                    "mentioned_companies": companies,
                    "high_signal": high_signal,
                }
            )
    except Exception as exc:
        logger.warning("RSS parse error for %s: %s", feed_name, exc)
    return entries


def fetch_and_parse_feed(
    feed: dict,
    company_names: list[str],
) -> tuple[str, list[dict]]:
    body = fetch_text(feed["url"], timeout=25.0)
    entries = parse_feed_body(body or "", feed["name"], feed["category"], company_names)
    return feed["name"], entries


def find_company_id(company_name: str, cursor: sqlite3.Cursor) -> int | None:
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


def store_signal(entry: dict, cursor: sqlite3.Cursor) -> int:
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
        "high_signal": entry.get("high_signal", False),
    }
    source_name = entry["source"]
    base_key = url_dedup_key(link)

    mentions = entry.get("mentioned_companies") or []
    if mentions:
        for company in mentions:
            company_id = find_company_id(company, cursor)
            scoped_key = f"{base_key}:{company_id or 0}:{company[:40]}"
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
    elif entry.get("high_signal") and insert_raw_signal_dedup(
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
