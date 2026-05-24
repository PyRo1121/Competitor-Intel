import logging
import time
from typing import Any

import httpx

logger = logging.getLogger("intel_http")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Hermes-Intel/2.0; +https://hermes.dev)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
}

MAX_RETRIES = 3
BACKOFF = 2

_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
        )
    return _client


def close_http_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def safe_request(
    url: str,
    timeout: float = 20.0,
    headers: dict | None = None,
    params: dict | None = None,
) -> httpx.Response | None:
    client = get_http_client()
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.get(url, headers=merged, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            logger.warning(
                "Request failed (%s/%s): %s - %s",
                attempt + 1,
                MAX_RETRIES,
                url,
                exc,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF**attempt)
    logger.error("All retries failed for %s", url)
    return None


def fetch_text(url: str, timeout: float = 20.0) -> str | None:
    resp = safe_request(url, timeout=timeout)
    if resp is None:
        return None
    return resp.text


def post_json(
    url: str,
    payload: dict[str, Any],
    timeout: float = 60.0,
    headers: dict | None = None,
) -> dict[str, Any] | None:
    """POST JSON body; return parsed response dict or None on failure."""
    client = get_http_client()
    merged = {**DEFAULT_HEADERS, "Accept": "application/json", **(headers or {})}
    try:
        resp = client.post(url, json=payload, headers=merged, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        logger.warning("Connection failed: %s", url)
        return None
    except httpx.TimeoutException:
        logger.warning("Request timed out: %s", url)
        return None
    except httpx.HTTPError as exc:
        logger.warning("POST failed: %s - %s", url, exc)
        return None
    except ValueError as exc:
        logger.warning("Invalid JSON from %s: %s", url, exc)
        return None
