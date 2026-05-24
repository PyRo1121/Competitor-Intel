"""
Fetch X signals via the official xurl CLI (X API v2).

Subprocess-only — no Hermes agent imports, no LLM. Auth lives in ~/.xurl
(configured by the operator outside agent sessions).

Set CI_X_PROVIDER=xurl to use this path from fetch_x.py / grok_refresh.py.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("xurl_fetcher")

_URL_RE = re.compile(r"https?://[^\s\])\"']+")


def xurl_binary() -> str | None:
    return shutil.which("xurl")


def check_xurl_ready() -> tuple[bool, str]:
    """Return (ready, message). Never reads ~/.xurl — only xurl auth status."""
    binary = xurl_binary()
    if not binary:
        return (
            False,
            (
                "xurl not on PATH (install: curl -fsSL "
                "https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash)"
            ),
        )

    try:
        proc = subprocess.run(
            [binary, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError as exc:
        return False, f"xurl auth status failed: {exc}"

    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return False, f"xurl auth status exit {proc.returncode}: {out.strip()[:300]}"

    # Prefer the default app line (marked with ▸); ignore empty built-in "default" profile.
    active_block: list[str] = []
    for line in out.splitlines():
        if line.strip().startswith("▸"):
            active_block = [line]
            continue
        if active_block and line.startswith("      "):
            active_block.append(line)
            continue
        if active_block and not line.startswith("      "):
            break

    block_text = "\n".join(active_block).lower()
    if active_block and "oauth2:" in block_text:
        oauth_line = next((ln for ln in active_block if "oauth2:" in ln.lower()), "")
        if "(none)" not in oauth_line.lower():
            return True, "xurl ready"

    if "oauth2:" in out.lower() and "(none)" not in out.lower():
        # Fallback: any app with a bound oauth2 user
        for line in out.splitlines():
            if "oauth2:" in line.lower() and "(none)" not in line.lower():
                user = line.split("oauth2:", 1)[-1].strip()
                if user and user not in ("–", "-"):
                    return True, "xurl ready"

    return (
        False,
        (
            "xurl installed but no OAuth2 token — run one-time setup "
            "(see integrations/hermes/README.md#xurl)"
        ),
    )


def _extract_urls(text: str, entities: dict[str, Any] | None) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.findall(text or ""):
        if match not in seen:
            seen.add(match)
            urls.append(match)
    if entities:
        for item in entities.get("urls") or []:
            if not isinstance(item, dict):
                continue
            expanded = item.get("expanded_url") or item.get("url")
            if isinstance(expanded, str) and expanded.startswith("http") and expanded not in seen:
                seen.add(expanded)
                urls.append(expanded)
    return urls


def _users_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    includes_raw = payload.get("includes")
    includes: dict[str, Any] = includes_raw if isinstance(includes_raw, dict) else {}
    users_raw = includes.get("users")
    users: list[Any] = users_raw if isinstance(users_raw, list) else []
    out: dict[str, dict[str, Any]] = {}
    for user in users:
        if isinstance(user, dict) and user.get("id") is not None:
            out[str(user["id"])] = user
    return out


def map_xurl_tweet(tweet: dict[str, Any], users_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Map X API v2 tweet JSON to internal grok_x_results post shape."""
    tweet_id = str(tweet.get("id") or "")
    author_id = str(tweet.get("author_id") or "")
    user = users_by_id.get(author_id) or {}
    username = str(user.get("username") or "i")
    text = str(tweet.get("text") or "")
    metrics_raw = tweet.get("public_metrics")
    metrics: dict[str, Any] = metrics_raw if isinstance(metrics_raw, dict) else {}
    entities = tweet.get("entities") if isinstance(tweet.get("entities"), dict) else None

    return {
        "post_id": tweet_id,
        "text": text,
        "posted_at": tweet.get("created_at"),
        "likes": int(metrics.get("like_count") or 0),
        "retweets": int(metrics.get("retweet_count") or 0),
        "replies": int(metrics.get("reply_count") or 0),
        "url": f"https://x.com/{username}/status/{tweet_id}" if tweet_id else "",
        "urls": _extract_urls(text, entities),
        "companies_detected": [],
        "is_founder_post": False,
        "sentiment": None,
        "source_provider": "xurl",
        "author_username": username,
    }


def parse_xurl_search_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize xurl search JSON (v2 wrapper or shortcut) into internal posts."""
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if data is None and isinstance(payload.get("tweet"), dict):
        data = [payload["tweet"]]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []

    users_by_id = _users_by_id(payload)
    posts: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            posts.append(map_xurl_tweet(item, users_by_id))
    return posts


def xurl_search_posts(query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
    """Run `xurl search` for one query; return normalized post dicts."""
    binary = xurl_binary()
    if not binary:
        raise RuntimeError("xurl not found on PATH")

    n = max_results if max_results is not None else int(os.environ.get("XURL_SEARCH_N", "10"))
    n = max(1, min(n, 100))

    cmd = [binary, "search", query, "-n", str(n)]
    logger.info("xurl search query=%r n=%d", query[:120], n)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("XURL_SEARCH_TIMEOUT_SEC", "120")),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"xurl search timed out for query={query!r}") from exc

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if proc.returncode != 0:
        hint = stderr or stdout or f"exit {proc.returncode}"
        if "CreditsDepleted" in hint:
            raise RuntimeError("X API credits depleted — add billing at developer.x.com")
        if "401" in hint or "Unauthorized" in hint:
            raise RuntimeError("xurl auth failed — run: xurl auth oauth2 --app YOUR_APP")
        raise RuntimeError(f"xurl search failed: {hint[:500]}")

    if not stdout:
        logger.warning("xurl search returned empty stdout for query=%r", query[:80])
        return []

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"xurl search returned non-JSON: {stdout[:300]}") from exc

    if isinstance(payload, dict) and payload.get("errors"):
        errors = payload.get("errors")
        raise RuntimeError(f"xurl search API errors: {errors}")

    posts = parse_xurl_search_payload(payload if isinstance(payload, dict) else {})
    logger.info("xurl search query=%r posts=%d", query[:80], len(posts))
    return posts


def fetch_batches(
    queries: list[str],
    *,
    max_queries: int | None = None,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    selected = queries[:max_queries] if max_queries else queries
    batches: list[dict[str, Any]] = []
    for q in selected:
        q = (q or "").strip()
        if not q:
            continue
        posts = xurl_search_posts(q, max_results=max_results)
        batches.append({"query": q, "results": posts, "source_provider": "xurl"})
    return batches


def fetch_and_write(
    out_path: Path,
    queries: list[str],
    *,
    max_queries: int | None = None,
    max_results: int | None = None,
) -> Path:
    ready, msg = check_xurl_ready()
    if not ready:
        raise RuntimeError(msg)

    batches = fetch_batches(queries, max_queries=max_queries, max_results=max_results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(batches, indent=2), encoding="utf-8")
    total_posts = sum(len(b.get("results") or []) for b in batches)
    logger.info(
        "Wrote %s (%d batches, %d posts, provider=xurl)", out_path, len(batches), total_posts
    )
    return out_path
