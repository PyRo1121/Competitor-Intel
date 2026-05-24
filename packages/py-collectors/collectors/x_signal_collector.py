"""
X / Twitter signal collector — persistence layer for Grok native X search.

Grok (Hermes agent) performs live X queries; this module normalizes results into
raw_signals with URL- or post-id-based dedup and rich data_json payloads.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from db.connection import get_conn
from db.ingest import get_company_id, insert_raw_signal_dedup, url_dedup_key

from collectors.rss_collector import extract_company_mentions, load_company_names
from collectors.sources_registry import get_x_monitor_queries

logger = logging.getLogger("x_signal_collector")

X_QUERIES = get_x_monitor_queries()


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\])\"']+", text or "")


def _extract_mentions(text: str) -> list[str]:
    return list({m.lower() for m in re.findall(r"@([A-Za-z0-9_]{1,15})", text or "")})


def _names_from_handles(cursor, handles: list[str]) -> list[str]:
    names: list[str] = []
    for handle in handles:
        cursor.execute(
            "SELECT name FROM companies WHERE LOWER(REPLACE(x_handle, '@', '')) = ? COLLATE NOCASE",
            (handle.lstrip("@"),),
        )
        row = cursor.fetchone()
        if row and row[0] not in names:
            names.append(row[0])
    return names


def extract_companies_from_x_post(
    text: str,
    author: str,
    grok_companies: list[str],
    company_names: list[str],
    cursor,
) -> list[str]:
    """Merge Grok hints, @handle lookups, and DB-backed substring matching."""
    detected: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        cleaned = (name or "").strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            detected.append(cleaned)

    for name in grok_companies:
        add(name)

    mentions = _extract_mentions(text)
    if author:
        mentions.append(author.lstrip("@").lower())
    for name in _names_from_handles(cursor, mentions):
        add(name)

    for name in extract_company_mentions(text, company_names):
        add(name)

    return detected


def resolve_company_id(
    cursor,
    companies: list[str],
    explicit_name: str | None = None,
) -> int | None:
    if explicit_name:
        cid = get_company_id(explicit_name)
        if cid:
            return cid
    for name in companies:
        cid = get_company_id(name)
        if cid:
            return cid
        cursor.execute(
            "SELECT id FROM companies WHERE LOWER(REPLACE(x_handle, '@', '')) = ?",
            (name.lstrip("@").lower(),),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
    return None


def classify_x_signal(text: str) -> str:
    lower = (text or "").lower()
    if any(
        w in lower for w in ("raised", "funding", "series a", "series b", "seed round", "pre-seed")
    ):
        return "funding"
    if any(w in lower for w in ("launch", "launched", "introducing", "announcing", "shipped")):
        return "product_launch"
    if any(w in lower for w in ("hiring", "we're hiring", "join our team", "open roles")):
        return "hiring"
    if any(w in lower for w in ("acquired", "acquisition", "acquires")):
        return "acquisition"
    return "social_momentum"


def _normalize_result(
    query: str,
    result: dict[str, Any],
    companies_detected: list[str] | None = None,
) -> dict[str, Any]:
    text = result.get("text") or result.get("content") or ""
    url = result.get("url") or result.get("post_url") or ""
    post_id = str(result.get("post_id") or result.get("id") or "")
    author = result.get("author") or result.get("username") or result.get("handle") or ""
    if author and not author.startswith("@"):
        author = f"@{author.lstrip('@')}"
    grok_companies = result.get("companies") or result.get("companies_detected") or []
    if isinstance(grok_companies, str):
        grok_companies = [grok_companies]
    companies = companies_detected if companies_detected is not None else list(grok_companies)
    category = result.get("category") or classify_x_signal(text)
    return {
        "query": query,
        "text": text,
        "author": author,
        "likes": result.get("likes", result.get("favorite_count", 0)),
        "retweets": result.get("retweets", result.get("retweet_count", 0)),
        "replies": result.get("replies", result.get("reply_count", 0)),
        "url": url,
        "link": url,
        "post_id": post_id,
        "posted_at": result.get("posted_at") or result.get("created_at"),
        "mentions": _extract_mentions(text),
        "urls": _extract_urls(text),
        "companies_detected": companies,
        "grok_companies": list(grok_companies),
        "sentiment": result.get("sentiment"),
        "is_founder_post": result.get("is_founder_post", False),
        "kind": "x_social",
        "category": category,
        "channel": "grok_x_search",
    }


def dedup_key_for_result(result: dict[str, Any]) -> str:
    post_id = result.get("post_id") or ""
    url = result.get("url") or ""
    if post_id:
        return f"x_post:{post_id}"
    if url:
        return url_dedup_key(url)
    text = (result.get("text") or "")[:120]
    return url_dedup_key(f"x:{result.get('author', '')}:{text}")


def store_x_signal(
    query: str,
    result: dict[str, Any],
    company_id: int | None = None,
    company_name: str | None = None,
    *,
    cursor=None,
    company_names: list[str] | None = None,
    commit: bool = True,
) -> bool:
    """Store one Grok/X result into raw_signals."""
    own_conn = cursor is None
    if own_conn:
        conn = get_conn()
        cursor = conn.cursor()
    else:
        conn = None

    try:
        text = result.get("text") or result.get("content") or ""
        author = result.get("author") or result.get("username") or result.get("handle") or ""
        grok_companies = result.get("companies") or result.get("companies_detected") or []
        if isinstance(grok_companies, str):
            grok_companies = [grok_companies]
        names = company_names if company_names is not None else load_company_names()
        companies = extract_companies_from_x_post(text, author, list(grok_companies), names, cursor)
        if company_name and company_name not in companies:
            companies.insert(0, company_name)
        resolved_id = company_id or resolve_company_id(
            cursor, companies, explicit_name=company_name
        )
        payload = _normalize_result(query, result, companies_detected=companies)
        stored = insert_raw_signal_dedup(
            cursor,
            "x",
            payload.get("url")
            or f"x://post/{payload.get('post_id') or dedup_key_for_result(payload)}",
            payload,
            company_id=resolved_id,
            detected_at=datetime.now(UTC).isoformat(),
            dedup_key=dedup_key_for_result(payload),
        )
        if stored and commit and own_conn and conn is not None:
            conn.commit()
        return stored
    finally:
        if own_conn and conn is not None:
            conn.close()


def store_grok_batch(
    query: str,
    results: list[dict[str, Any]],
    company_name: str | None = None,
) -> int:
    """Store multiple Grok results for one search query."""
    if not results:
        return 0
    conn = get_conn()
    cursor = conn.cursor()
    company_names = load_company_names()
    inserted = 0
    try:
        for row in results:
            if store_x_signal(
                query,
                row,
                company_name=company_name,
                cursor=cursor,
                company_names=company_names,
                commit=False,
            ):
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    logger.info("Stored %d X signals for query: %s", inserted, query[:80])
    return inserted


def load_grok_results_from_env() -> list[dict[str, Any]]:
    """
    Optional batch ingest: set GROK_X_RESULTS_PATH to a JSON file:
    [{"query": "...", "results": [{...}, ...]}, ...]
    """
    path = os.environ.get("GROK_X_RESULTS_PATH", "").strip()
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        logger.warning("GROK_X_RESULTS_PATH not found: %s", path)
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "batches" in data:
            return data["batches"]
    except json.JSONDecodeError as exc:
        logger.error("Invalid GROK_X_RESULTS_PATH JSON: %s", exc)
    return []


def _default_grok_results_path() -> Path:
    raw = os.environ.get("GROK_X_RESULTS_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[3] / "data" / "hermes_enrich" / "grok_x_results.json"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def _ensure_grok_batch_file() -> Path:
    """Fetch via xAI x_search when auto/require; never use local LLM."""
    path = _default_grok_results_path()
    auto = _env_flag("CI_AUTO_GROK_X")
    require = _env_flag("CI_REQUIRE_GROK_X")
    stale = not path.is_file() or path.stat().st_size < 50

    if require and not auto and stale:
        raise RuntimeError(
            f"CI_REQUIRE_GROK_X: missing {path}. Run: make grok-x-fetch "
            "(needs XAI_API_KEY). No Ollama fallback."
        )

    if (auto or require) and stale:
        from collectors.grok_x_fetcher import fetch_and_write

        max_q = int(os.environ.get("GROK_X_MAX_QUERIES", "10"))
        logger.info("Fetching Grok X batch (max_queries=%s) → %s", max_q, path)
        fetch_and_write(path, get_x_monitor_queries(), max_queries=max_q)

    os.environ["GROK_X_RESULTS_PATH"] = str(path)
    return path


def run_x_collection() -> int:
    """
    Entry point for parallel_collect / daily_intel.
    Ingests GROK_X_RESULTS_PATH; with CI_AUTO_GROK_X fetches via Grok x_search first.
    """
    try:
        if _env_flag("CI_AUTO_GROK_X") or _env_flag("CI_REQUIRE_GROK_X"):
            _ensure_grok_batch_file()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    total = 0
    path = os.environ.get("GROK_X_RESULTS_PATH", "").strip()
    batches = load_grok_results_from_env()
    if batches:
        for batch in batches:
            query = batch.get("query") or "grok_batch"
            results = batch.get("results") or batch.get("posts") or []
            company_name = batch.get("company") or batch.get("company_name")
            if isinstance(results, list):
                total += store_grok_batch(query, results, company_name=company_name)
        logger.info("Ingested %d X posts from %s", total, path)
    elif path:
        logger.error(
            "GROK_X_RESULTS_PATH is set but file missing or invalid: %s "
            "(copy data/hermes_enrich/grok_x_results.example.json, fill from Grok, rename)",
            path,
        )
    else:
        logger.info(
            "GROK_X_RESULTS_PATH not set — enable CI_AUTO_GROK_X=1 or run: make grok-x-fetch"
        )

    if _env_flag("CI_REQUIRE_GROK_X") and total == 0:
        logger.error(
            "CI_REQUIRE_GROK_X: 0 X posts ingested (path=%s). "
            "Fix XAI_API_KEY / x_search; no local-model fallback.",
            path or "(unset)",
        )
        return 1
    return 0


def run() -> int:
    return run_x_collection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(run())
