#!/usr/bin/env python3
"""
GitHub Signals Collector
Tracks trending AI repos using the GitHub API.
Requires GITHUB_TOKEN environment variable for higher rate limits.
"""

import logging
import os

logger = logging.getLogger("github_signals")

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from utils.http import close_http_client, get_http_client

GITHUB_API = "https://api.github.com"


def github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def add_signal(title: str, summary: str, source: str, url: str) -> bool:
    if not url:
        return False
    conn = get_conn()
    cursor = conn.cursor()
    try:
        payload = {
            "title": title,
            "summary": summary,
            "url": url,
            "link": url,
            "kind": "github_trending",
        }
        inserted = insert_raw_signal_dedup(cursor, source, url, payload)
        if inserted:
            conn.commit()
        return inserted
    finally:
        conn.close()


def fetch_github_repos(query: str = "topic:ai language:python", limit: int = 10) -> list[dict]:
    url = f"{GITHUB_API}/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": limit}
    client = get_http_client()
    try:
        resp = client.get(url, params=params, headers=github_headers(), timeout=20.0)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as exc:
        logger.error("GitHub API error: %s", exc)
        return []


def run() -> int:
    repos = fetch_github_repos()
    added = 0
    for repo in repos:
        name = repo.get("full_name", "")
        url = repo.get("html_url", "")
        desc = repo.get("description") or ""
        stars = repo.get("stargazers_count", 0)
        summary = f"{desc} ({stars} stars)" if desc else f"{stars} stars"
        if add_signal(name, summary, "github", url):
            added += 1
    close_http_client()
    logger.info("GitHub signals: %s new", added)
    return added


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
