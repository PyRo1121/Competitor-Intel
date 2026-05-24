"""Wikipedia REST summary — free descriptions and infobox hints."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from utils.http import safe_request

logger = logging.getLogger("intel_wikipedia")

WIKI_UA = "CompetitorIntel/1.0 (research; mailto:contact@example.com)"


def _title_from_name(name: str) -> str:
    cleaned = re.sub(r"\s+(inc\.?|llc|ltd\.?|corp\.?|plc)$", "", name.strip(), flags=re.I)
    return cleaned.replace(" ", "_")


def fetch_summary(company_name: str) -> dict[str, Any]:
    """Page summary; empty dict if no article."""
    title = _title_from_name(company_name)
    if not title:
        return {}

    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
    resp = safe_request(
        url,
        timeout=12.0,
        headers={"User-Agent": WIKI_UA, "Accept": "application/json"},
    )
    if resp is None:
        return {}

    try:
        data = resp.json()
    except ValueError as exc:
        logger.warning("Wikipedia JSON error for %s: %s", title, exc)
        return {}

    if data.get("type") == "disambiguation":
        return {}

    out: dict[str, Any] = {
        "source_url": data.get("content_urls", {}).get("desktop", {}).get("page")
        or f"https://en.wikipedia.org/wiki/{quote(title)}",
    }
    extract = (data.get("extract") or "").strip()
    if extract:
        out["description_long"] = extract[:4000]

    desc = data.get("description")
    if desc and not out.get("description_long"):
        out["description_long"] = str(desc)

    return out
