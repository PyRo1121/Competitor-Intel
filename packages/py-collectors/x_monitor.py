"""
X Monitoring — Grok 4.3 native search interface + DB persistence.

Grok runs X queries; call process_grok_x_results() or store_grok_batch() to persist.
"""

from typing import Any, Dict, List, Optional, Optional

from collectors.sources_registry import get_x_monitor_queries
from collectors.x_signal_collector import store_grok_batch, store_x_signal
from db.ingest import get_company_id, insert_x_post

import logging

logger = logging.getLogger("x_monitor")


def fetch_recent_x_activity(company_x_handle: str, days: int = 3) -> str:
    """Return prompt text for Grok — no direct X API calls from this host."""
    return get_x_query_prompt(company_x_handle, days)


def process_grok_x_results(company_name: str, grok_results: List[Dict[str, Any]]) -> int:
    """
    Process Grok JSON array: writes x_posts (when company matches) and raw_signals.
    """
    inserted_posts = 0
    inserted_signals = 0
    handle = company_name.lstrip("@")
    query = f"@{handle}"
    company_id = get_company_id(company_name) or get_company_id(handle)

    for post in grok_results:
        if insert_x_post(company_name, post):
            inserted_posts += 1
        if store_x_signal(
            query,
            post,
            company_id=company_id,
            company_name=company_name,
        ):
            inserted_signals += 1

    logger.info(
        "Grok X ingest for %s: %d x_posts, %d raw_signals",
        company_name,
        inserted_posts,
        inserted_signals,
    )
    return inserted_signals


def process_grok_query_results(
    query: str,
    grok_results: List[Dict[str, Any]],
    company_name: Optional[str] = None,
) -> int:
    """Store ad-hoc Grok search results (global queries, not tied to one company)."""
    return store_grok_batch(query, grok_results, company_name=company_name)


def get_x_query_prompt(company_x_handle: str, days: int = 2) -> str:
    handle = company_x_handle.lstrip("@")
    return f"""Search X for the last {days} days of posts from @{handle}.
Return ONLY a JSON array with this exact structure for each post:
[
  {{
    "post_id": "string",
    "text": "full post text",
    "posted_at": "ISO datetime",
    "likes": number,
    "retweets": number,
    "replies": number,
    "url": "https://x.com/...",
    "is_founder_post": true/false,
    "sentiment": number between -1 and 1
  }}
]
Only include posts with meaningful product, funding, or hiring signals. Ignore pure engagement posts."""


def list_default_queries() -> List[str]:
    return get_x_monitor_queries()
