"""
High-Quality Multi-Source Signal Collector
Curated list of premium free sources for competitor intelligence.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Tuple

import feedparser

logger = logging.getLogger("multi_source_collector")

from collectors.sources_registry import catalog_summary, multi_source_tuples
from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from utils.http import close_http_client, fetch_text

SOURCES = multi_source_tuples()

FETCH_WORKERS = 6


def collect_source(url: str, name: str) -> Tuple[str, int]:
    added = 0
    body = fetch_text(url, timeout=25.0)
    if not body:
        return name, 0

    conn = get_conn()
    cursor = conn.cursor()
    try:
        feed = feedparser.parse(body)
        for entry in feed.entries[:12]:
            title = str(entry.get("title") or "")
            summary = str(entry.get("summary") or entry.get("description") or "")
            link = str(entry.get("link") or "")
            if not (title and link):
                continue
            payload = {
                "title": title,
                "summary": summary[:800],
                "url": link,
                "link": link,
                "kind": "multi_source_rss",
            }
            if insert_raw_signal_dedup(cursor, name, link, payload):
                added += 1
        conn.commit()
    finally:
        conn.close()
    return name, added


def run() -> int:
    summary = catalog_summary()
    logger.info(
        "Collecting from %s registry sources (%s enabled)...",
        len(SOURCES),
        summary["enabled"],
    )
    total = 0

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(collect_source, url, name): name for url, name in SOURCES}
        for future in as_completed(futures):
            name = futures[future]
            try:
                source_name, added = future.result()
                logger.info("  +%s from %s", added, source_name)
                total += added
            except Exception as exc:
                logger.error("Error collecting from %s: %s", name, exc)

    close_http_client()
    logger.info("Total new signals collected: %s from %s sources", total, len(SOURCES))
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
