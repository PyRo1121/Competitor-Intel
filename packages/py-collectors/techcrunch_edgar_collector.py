"""
TechCrunch funding signal collector — HTML scrape for funding headlines.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup, url_dedup_key
from utils.http import fetch_text

logger = logging.getLogger("techcrunch_edgar")

FUNDING_KEYWORDS = [
    "raised", "funding", "seed round", "series a", "series b",
    "valuation", "acquires", "acquisition", "invests", "investors",
    "million", "billion", "startup funding",
]

SCRAPE_URLS = [
    "https://techcrunch.com/tag/artificial-intelligence/",
    "https://techcrunch.com/tag/startups/",
    "https://techcrunch.com/latest/",
]


def fetch_techcrunch_funding_news() -> List[Dict[str, Any]]:
    logger.info("Fetching TechCrunch funding headlines...")
    signals: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()

    for page_url in SCRAPE_URLS:
        html = fetch_text(page_url, timeout=20.0)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href*='/20']")[:25]:
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or len(title) < 15 or title in seen_titles:
                continue
            title_lower = title.lower()
            if not any(kw in title_lower for kw in FUNDING_KEYWORDS):
                continue
            if isinstance(href, str) and href.startswith("http"):
                url = href
            else:
                url = f"https://techcrunch.com{href or ''}"
            seen_titles.add(title)
            signals.append(
                {
                    "title": title,
                    "url": url,
                    "link": url,
                    "kind": "funding_news",
                    "category": "funding",
                    "source_page": page_url,
                }
            )

    logger.info("Found %s funding-related TechCrunch articles", len(signals))
    return signals


def store_signals(signals: List[Dict[str, Any]]) -> int:
    if not signals:
        return 0

    conn = get_conn()
    cursor = conn.cursor()
    inserted = 0
    detected_at = datetime.now().isoformat()

    for sig in signals:
        url = sig.get("url") or ""
        dedup_key = url_dedup_key(url) if url else url_dedup_key(sig.get("title", ""))
        payload = {**sig, "detected_at": detected_at}
        if insert_raw_signal_dedup(
            cursor,
            "techcrunch",
            url or f"title:{sig.get('title', '')}",
            payload,
            detected_at=detected_at,
            dedup_key=dedup_key,
        ):
            inserted += 1

    conn.commit()
    conn.close()
    logger.info("TechCrunch collector stored %s signals", inserted)
    return inserted


def run_techcrunch_edgar_collector() -> int:
    return store_signals(fetch_techcrunch_funding_news())


def run() -> int:
    return run_techcrunch_edgar_collector()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
