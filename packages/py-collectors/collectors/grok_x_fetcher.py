"""
Fetch X signals via Hermes x_search (xAI Grok + X.com OAuth).

Uses the same tool and credential resolver as the Hermes agent
(tools.x_search_tool + tools.xai_http.resolve_xai_http_credentials).
No Ollama fallback. API errors propagate — nothing degrades to local models.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("grok_x_fetcher")

_DEFAULT_HERMES_ROOT = Path.home() / ".hermes" / "hermes-agent"
HERMES_AGENT_ROOT = Path(
    os.environ.get("HERMES_AGENT_ROOT", str(_DEFAULT_HERMES_ROOT)).strip()
    or str(_DEFAULT_HERMES_ROOT)
)

JSON_INSTRUCTION = """
Return ONLY valid JSON (no markdown fences): an array of post objects with fields:
post_id, text, posted_at (ISO-8601), likes, retweets, replies, url,
urls (array of outbound https links), companies_detected (array), is_founder_post, sentiment.
Include every funding/product/hiring signal you find. Empty array [] if none.
"""


def _ensure_hermes_on_path() -> None:
    root = str(HERMES_AGENT_ROOT)
    if not HERMES_AGENT_ROOT.is_dir():
        raise RuntimeError(
            f"Hermes agent not found at {HERMES_AGENT_ROOT}. "
            "Install Hermes and run: hermes auth add xai-oauth"
        )
    if root not in sys.path:
        sys.path.insert(0, root)


def resolve_xai_credentials() -> tuple[str, str, str]:
    """Hermes OAuth first (SuperGrok / X.com), then XAI_API_KEY only if OAuth missing."""
    _ensure_hermes_on_path()
    from tools.xai_http import resolve_xai_http_credentials

    creds = resolve_xai_http_credentials()
    key = str(creds.get("api_key") or "").strip()
    if not key:
        raise RuntimeError(
            "No xAI credentials from Hermes. Run: hermes auth add xai-oauth "
            "(SuperGrok / X.com). No local-model fallback."
        )
    base = str(creds.get("base_url") or "https://api.x.ai/v1").rstrip("/")
    provider = str(creds.get("provider") or "xai")
    logger.info("xAI via Hermes credential resolver (%s)", provider)
    return key, base, provider


def _parse_posts_from_answer(answer: str) -> list[dict[str, Any]]:
    text = (answer or "").strip()
    if not text:
        return []
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            logger.warning("Grok answer was not JSON; no posts parsed")
            return []
        data = json.loads(match.group(0))
    if isinstance(data, dict) and "results" in data:
        inner = data["results"]
        return inner if isinstance(inner, list) else []
    if isinstance(data, list):
        return [p for p in data if isinstance(p, dict)]
    return []


def x_search_posts(query: str) -> list[dict[str, Any]]:
    """Run Hermes x_search_tool for one query (same path as interactive agent)."""
    _ensure_hermes_on_path()
    from tools.x_search_tool import x_search_tool

    prompt = f"Search X for: {query}\n\n{JSON_INSTRUCTION}"
    raw = x_search_tool(query=prompt)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Hermes x_search returned non-JSON: {raw[:300]}") from exc

    if not data.get("success"):
        err = data.get("error") or data.get("message") or raw
        raise RuntimeError(f"Hermes x_search failed: {err}")

    answer = str(data.get("answer") or "")
    posts = _parse_posts_from_answer(answer)
    provider = data.get("credential_source") or data.get("provider") or "hermes"
    logger.info(
        "x_search query=%r posts=%d provider=%s model=%s",
        query[:80],
        len(posts),
        provider,
        data.get("model"),
    )
    return posts


def fetch_batches(
    queries: list[str],
    *,
    max_queries: int | None = None,
) -> list[dict[str, Any]]:
    selected = queries[:max_queries] if max_queries else queries
    batches: list[dict[str, Any]] = []
    for q in selected:
        q = (q or "").strip()
        if not q:
            continue
        posts = x_search_posts(q)
        batches.append({"query": q, "results": posts})
    return batches


def fetch_and_write(
    out_path: Path,
    queries: list[str],
    *,
    max_queries: int | None = None,
) -> Path:
    batches = fetch_batches(queries, max_queries=max_queries)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(batches, indent=2), encoding="utf-8")
    total_posts = sum(len(b.get("results") or []) for b in batches)
    logger.info("Wrote %s (%d batches, %d posts)", out_path, len(batches), total_posts)
    return out_path
