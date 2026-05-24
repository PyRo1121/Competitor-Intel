#!/usr/bin/env python3
"""
Promote outbound URLs from social/thread signals into article-shaped raw_signals.

X and Hacker News often surface a deal before the press article; this collector
creates one raw_signal per external URL so RSS-style processing and funding
extraction can run on the primary source.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any
from urllib.parse import urlparse

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup, url_dedup_key

logger = logging.getLogger("signal_url_fanout")

SKIP_HOST_SUFFIXES = (
    "x.com",
    "twitter.com",
    "mobile.twitter.com",
    "t.co",
    "pic.twitter.com",
)

FUNDING_HINTS = (
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
    "million",
    "billion",
    "acquired",
    "acquisition",
    "closes",
    "round",
)

URL_RE = re.compile(r"https?://[^\s\])\"'<>]+")


def _parse_data(data_json: str | None) -> dict[str, Any]:
    if not data_json:
        return {}
    try:
        parsed = json.loads(data_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def should_skip_url(url: str) -> bool:
    host = _host(url)
    if not host:
        return True
    return any(host == s or host.endswith("." + s) for s in SKIP_HOST_SUFFIXES)


def extract_outbound_urls(data: dict[str, Any]) -> list[str]:
    """Collect external URLs from a social/thread payload."""
    seen: set[str] = set()
    ordered: list[str] = []

    def add(raw: str) -> None:
        u = (raw or "").strip().rstrip(".,;)")
        if not u or should_skip_url(u):
            return
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    for key in ("urls", "outbound_urls", "linked_urls"):
        val = data.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    add(item)

    primary = data.get("url") or data.get("link") or ""
    if data.get("kind") not in ("x_social",):
        add(str(primary))

    blob = " ".join(
        str(data.get(k) or "") for k in ("text", "title", "summary", "content", "thread_comments")
    )
    for match in URL_RE.findall(blob):
        add(match)

    return ordered


def is_deal_relevant(data: dict[str, Any], url: str) -> bool:
    """Prefer URLs tied to funding/M&A language (still allow HN link posts)."""
    text = " ".join(
        str(data.get(k) or "")
        for k in ("text", "title", "summary", "content", "thread_comments", "story_type")
    ).lower()
    if any(h in text for h in FUNDING_HINTS):
        return True
    if data.get("category") == "funding" or data.get("story_type") == "funding":
        return True
    host = _host(url)
    return bool(host and "ycombinator.com" not in host)


def fanout_one_signal(
    cursor: sqlite3.Cursor,
    signal_id: int,
    source: str,
    company_id: int | None,
    data: dict[str, Any],
) -> int:
    if data.get("url_fanout_done"):
        return 0

    inserted = 0
    parent_title = (data.get("title") or data.get("text") or "")[:240]
    parent_summary = (data.get("text") or data.get("summary") or "")[:1500]

    for url in extract_outbound_urls(data):
        if not is_deal_relevant(data, url):
            continue
        child: dict[str, Any] = {
            "title": parent_title or url,
            "summary": parent_summary,
            "url": url,
            "link": url,
            "kind": "url_fanout",
            "category": data.get("category") or "funding",
            "discovered_via": source,
            "parent_raw_signal_id": signal_id,
            "channel": "url_fanout",
        }
        dedup = f"fanout:{signal_id}:{url_dedup_key(url)}"
        if insert_raw_signal_dedup(
            cursor,
            "article",
            url,
            child,
            company_id=company_id,
            dedup_key=dedup,
        ):
            inserted += 1

    data["url_fanout_done"] = True
    cursor.execute(
        "UPDATE raw_signals SET data_json = ? WHERE id = ?",
        (json.dumps(data), signal_id),
    )
    return inserted


def run(batch_size: int = 400) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, source, company_id, data_json
        FROM raw_signals
        WHERE source IN ('x', 'hackernews')
        ORDER BY detected_at DESC
        LIMIT ?
        """,
        (batch_size,),
    )
    rows = cur.fetchall()
    total = 0
    for signal_id, source, company_id, data_json in rows:
        data = _parse_data(data_json)
        total += fanout_one_signal(cur, signal_id, source, company_id, data)
    conn.commit()
    conn.close()
    logger.info("URL fanout: %d article signals from %d social/thread rows", total, len(rows))
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
