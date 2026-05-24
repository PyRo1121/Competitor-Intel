"""
Browser-impersonating HTTP for HTML pages (Cloudflare / bot checks).

Uses curl_cffi (libcurl-impersonate) — free, MIT — to match Chrome TLS + HTTP/2
fingerprints. RSS, JSON APIs, and SEC feeds should keep using utils.http (httpx).

Env:
  CI_BROWSER_FETCH=1          Enable browser fetch (default on)
  CI_BROWSER_IMPERSONATE=chrome120   curl_cffi impersonate profile
  CI_SCRAPE_DELAY_SEC=0.75    Min seconds between browser fetches (polite)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, cast

logger = logging.getLogger("intel_browser_fetch")

DEFAULT_IMPERSONATE = os.environ.get("CI_BROWSER_IMPERSONATE", "chrome120")
MAX_RETRIES = int(os.environ.get("CI_BROWSER_FETCH_RETRIES", "3"))
BACKOFF = float(os.environ.get("CI_BROWSER_FETCH_BACKOFF", "2"))
POLITE_DELAY_SEC = float(os.environ.get("CI_SCRAPE_DELAY_SEC", "0.75"))

# Fallback profiles if the default is rejected
_IMPERSONATE_FALLBACKS = ("chrome120", "chrome119", "chrome116", "safari17_0")

_last_fetch_at: float = 0.0

BROWSER_DEFAULT_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def browser_fetch_enabled() -> bool:
    return os.environ.get("CI_BROWSER_FETCH", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _polite_wait() -> None:
    global _last_fetch_at
    if POLITE_DELAY_SEC <= 0:
        return
    now = time.monotonic()
    if _last_fetch_at > 0:
        gap = POLITE_DELAY_SEC - (now - _last_fetch_at)
        if gap > 0:
            time.sleep(gap)
    _last_fetch_at = time.monotonic()


def _looks_like_challenge_page(html: str) -> bool:
    if not html or len(html) < 150:
        return True
    sample = html[:12_000].lower()
    markers = (
        "cf-browser-verification",
        "challenge-platform",
        "cdn-cgi/challenge-platform",
        "just a moment",
        "attention required",
        "enable javascript and cookies",
        "checking your browser",
        "ray id",
    )
    hits = sum(1 for m in markers if m in sample)
    if hits >= 2:
        return True
    return bool(len(html) < 4000 and hits >= 1)


def _impersonate_profiles(preferred: str | None) -> tuple[str, ...]:
    primary = (preferred or DEFAULT_IMPERSONATE).strip()
    seen: set[str] = set()
    ordered: list[str] = []
    for p in (primary, *_IMPERSONATE_FALLBACKS):
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)
    return tuple(ordered)


def fetch_browser_text(
    url: str,
    timeout: float = 20.0,
    headers: dict[str, str] | None = None,
    *,
    impersonate: str | None = None,
) -> str | None:
    """
    Fetch page HTML with browser TLS impersonation.
    Returns None when disabled, curl_cffi missing, challenge page, or all retries fail.
    """
    if not browser_fetch_enabled():
        return None

    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        logger.warning(
            "curl_cffi not installed — browser fetch skipped for %s. Run: uv sync",
            url,
        )
        return None

    _polite_wait()
    merged = {**BROWSER_DEFAULT_HEADERS, **(headers or {})}
    profiles = _impersonate_profiles(impersonate)

    last_status: int | None = None
    for attempt in range(MAX_RETRIES):
        profile = profiles[min(attempt, len(profiles) - 1)]
        try:
            resp = curl_requests.get(
                url,
                headers=merged,
                timeout=timeout,
                impersonate=cast(Any, profile),
                allow_redirects=True,
            )
            last_status = resp.status_code
            if resp.status_code >= 400:
                logger.warning(
                    "Browser fetch HTTP %s (%s/%s) %s profile=%s",
                    resp.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                    profile,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF**attempt)
                continue

            text = resp.text or ""
            if _looks_like_challenge_page(text):
                logger.warning(
                    "Challenge interstitial (%s/%s) %s profile=%s",
                    attempt + 1,
                    MAX_RETRIES,
                    url,
                    profile,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF**attempt)
                continue

            return text
        except Exception as exc:
            logger.warning(
                "Browser fetch error (%s/%s) %s profile=%s: %s",
                attempt + 1,
                MAX_RETRIES,
                url,
                profile,
                exc,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF**attempt)

    logger.error(
        "Browser fetch exhausted retries for %s (last_status=%s)",
        url,
        last_status,
    )
    return None
