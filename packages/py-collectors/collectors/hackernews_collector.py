#!/usr/bin/env python3
"""Hacker News collector - Show HN, top stories, and thread context."""

import html
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from utils.http import close_http_client, safe_request

from collectors.company_match import resolve_company_id as match_company_id
from collectors.entity_extract import extract_entities_from_text, text_has_hype
from collectors.rss_collector import extract_company_mentions, load_company_names
from collectors.signal_company_resolver import build_domain_index, resolve_from_url

logger = logging.getLogger("hackernews")

HN_API = "https://hacker-news.firebaseio.com/v0"
HN_ALGOLIA = "https://hn.algolia.com/api/v1/search"
SHOW_HN = f"{HN_API}/showstories.json"
TOP_STORIES = f"{HN_API}/topstories.json"
NEW_STORIES = f"{HN_API}/newstories.json"
COMMENT_FETCH_LIMIT = 6
THREAD_COMMENT_MAX = 500


def fetch_story_ids(endpoint: str, limit: int = 50) -> list[int]:
    resp = safe_request(endpoint, timeout=15.0)
    if resp is None:
        return []
    try:
        ids = resp.json()
        return ids[:limit] if ids else []
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to parse HN story IDs: %s", exc)
        return []


def fetch_story(story_id: int) -> dict[str, Any]:
    resp = safe_request(f"{HN_API}/item/{story_id}.json", timeout=10.0)
    if resp is None:
        return {}
    try:
        return resp.json()
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to fetch HN story %d: %s", story_id, exc)
        return {}


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(cleaned).strip()


def fetch_thread_comments(story: dict[str, Any], limit: int = COMMENT_FETCH_LIMIT) -> list[str]:
    """Top-level HN comments — often name investors, terms, or link to press."""
    kids = story.get("kids") or []
    comments: list[str] = []
    for kid in kids[:limit]:
        item = fetch_story(int(kid))
        if not item or item.get("type") != "comment":
            continue
        body = _strip_html(str(item.get("text") or ""))
        if len(body) > 40:
            comments.append(body[:THREAD_COMMENT_MAX])
    return comments


def is_startup_relevant(story: dict[str, Any]) -> bool:
    if not story:
        return False
    title = (story.get("title") or "").lower()
    text = _strip_html(str(story.get("text") or "")).lower()
    combined = f"{title} {text}"
    keywords = [
        "launch",
        "show hn",
        "startup",
        "funding",
        "raised",
        "series a",
        "series b",
        "seed",
        "acquired",
        "open source",
        "github",
        "api",
        "saas",
        "developer tools",
        "led by",
        "million",
        "valuation",
        "round",
        "hiring",
        "platform",
        "marketplace",
        "fintech",
        "health",
    ]
    if any(kw in combined for kw in keywords):
        return True
    return text_has_hype(combined)


def classify_story_type(story: dict[str, Any]) -> str:
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


def _resolve_first_company_id(
    cursor: sqlite3.Cursor,
    names: list[str],
    *,
    domain_index: dict | None = None,
) -> int | None:
    for name in names:
        cid = match_company_id(cursor, name, domain_index=domain_index)
        if cid is not None:
            return cid
    return None


def store_signals(stories: list[dict[str, Any]], company_names: list[str]) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    stored = 0
    detected_at = datetime.now(UTC).isoformat()

    for story in stories:
        title = story.get("title", "")
        text = _strip_html(str(story.get("text") or ""))
        comments = story.get("thread_comments") or []
        combined = f"{title} {text} " + " ".join(comments)
        entities = extract_entities_from_text(f"{title} {text}")
        companies = extract_company_mentions(combined, company_names)
        companies = list(dict.fromkeys(companies + entities))
        company_id = _resolve_first_company_id(cursor, companies)
        external = story.get("url")
        discussion = f"https://news.ycombinator.com/item?id={story['id']}"
        url = external or discussion
        outbound: list[str] = []
        if external:
            outbound.append(external)
        outbound.append(discussion)

        data = {
            "title": title,
            "text": text[:1500],
            "summary": combined[:1500],
            "url": url,
            "link": url,
            "discussion_url": discussion,
            "external_url": external,
            "urls": outbound,
            "thread_comments": comments,
            "score": story.get("score"),
            "descendants": story.get("descendants"),
            "by": story.get("by"),
            "time": story.get("time"),
            "companies_detected": companies,
            "provisional_entities": entities,
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


def enrich_stories_with_threads(stories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for story in stories:
        if (story.get("descendants") or 0) >= 3:
            story["thread_comments"] = fetch_thread_comments(story)
    return stories


def _story_domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        return (urlparse(url).netloc or "").lower().replace("www.", "")
    except ValueError:
        return ""


def store_algolia_show_hn(cursor, company_names: list[str], pages: int = 12) -> int:
    """Historical Show HN via Algolia (no API key)."""
    domain_index = build_domain_index(cursor)
    detected_at = datetime.now(UTC).isoformat()
    stored = 0
    timestamp: int | None = None

    for _ in range(pages):
        params: dict[str, Any] = {"tags": "show_hn", "hitsPerPage": 100}
        if timestamp is not None:
            params["numericFilters"] = f"created_at_i<{timestamp}"
        resp = safe_request(HN_ALGOLIA, timeout=25.0, params=params)
        if resp is None:
            break
        try:
            hits = resp.json().get("hits") or []
        except (json.JSONDecodeError, TypeError, AttributeError):
            break
        if not hits:
            break

        for hit in hits:
            title = (hit.get("title") or "").strip()
            story_url = hit.get("url") or (
                f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            )
            host = _story_domain(story_url)
            companies = extract_company_mentions(f"{title} {host}", company_names)
            companies.extend(extract_entities_from_text(title))
            companies = list(dict.fromkeys(companies))
            company_id = None
            if host:
                match = resolve_from_url(f"https://{host}", domain_index)
                if match:
                    company_id = int(match[0])
            if company_id is None and companies:
                company_id = match_company_id(cursor, companies[0], domain_index=domain_index)
            object_id = str(hit.get("objectID") or "")
            data = {
                "title": title,
                "url": story_url,
                "link": story_url,
                "points": hit.get("points"),
                "num_comments": hit.get("num_comments"),
                "author": hit.get("author"),
                "created_at": hit.get("created_at"),
                "companies_detected": companies,
                "provisional_entities": extract_entities_from_text(title),
                "kind": "hn_algolia_show",
                "story_type": "show_hn",
                "category": "show_hn",
            }
            if insert_raw_signal_dedup(
                cursor,
                "hackernews",
                story_url,
                data,
                company_id=company_id,
                detected_at=detected_at,
                dedup_key=f"hn_algolia_{object_id}",
            ):
                stored += 1

        last_ts = hits[-1].get("created_at_i")
        if last_ts is None:
            break
        timestamp = int(last_ts)

    return stored


def run() -> int:
    try:
        story_ids = fetch_story_ids(SHOW_HN, limit=40)
        story_ids += fetch_story_ids(TOP_STORIES, limit=40)
        story_ids += fetch_story_ids(NEW_STORIES, limit=25)
        story_ids = list(dict.fromkeys(story_ids))
        logger.info("Fetching %d HN stories", len(story_ids))
        stories = []
        for sid in story_ids:
            story = fetch_story(sid)
            if story and is_startup_relevant(story):
                stories.append(story)
        logger.info("Found %d startup-relevant stories", len(stories))
        company_names = load_company_names()
        stored = 0
        if stories:
            stories = enrich_stories_with_threads(stories)
            stored = store_signals(stories, company_names)
        conn = get_conn()
        cursor = conn.cursor()
        try:
            stored += store_algolia_show_hn(cursor, company_names)
            conn.commit()
        finally:
            conn.close()
        return stored
    finally:
        close_http_client()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
