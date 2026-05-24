"""Sector-agnostic company name hints from news headlines and signal text."""

from __future__ import annotations

import re

# Funding / launch / growth language (not industry-specific).
HYPE_KEYWORDS = (
    "raised",
    "raises",
    "funding",
    "series a",
    "series b",
    "series c",
    "seed",
    "pre-seed",
    "valuation",
    "led by",
    "million",
    "billion",
    "closes",
    "closed",
    "secured",
    "investors",
    "acquired",
    "acquisition",
    "launch",
    "launched",
    "introducing",
    "debuts",
    "startup",
    "hiring",
    "ipo",
    "round",
)

# Headline patterns: capture a plausible company name before the verb.
_HEADLINE_PATTERNS = (
    re.compile(
        r"\b([A-Z][A-Za-z0-9&.\-]{1,48}(?:\s+[A-Z][A-Za-z0-9&.\-]{1,32}){0,4})"
        r"\s+(?:raises|raised|lands|secured|closes|closed|bags|gets|snags|hits)\b",
        re.I,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9&.\-]{1,48}(?:\s+[A-Z][A-Za-z0-9&.\-]{1,32}){0,3})"
        r"\s+(?:launches|launched|debuts|introduces|unveils|announces)\b",
        re.I,
    ),
    re.compile(
        r"\b([A-Z][A-Za-z0-9&.\-]{1,48}(?:\s+[A-Z][A-Za-z0-9&.\-]{1,32}){0,3})"
        r"\s+(?:acquires|acquired|buys|bought)\b",
        re.I,
    ),
)

_REJECT_NAMES = frozenset(
    {
        "the",
        "a",
        "an",
        "show hn",
        "ask hn",
        "breaking",
        "exclusive",
        "update",
        "how",
        "why",
        "what",
        "sec",
        "fda",
        "eu",
        "us",
        "uk",
    }
)


def text_has_hype(text: str) -> bool:
    t = (text or "").lower()
    return any(kw in t for kw in HYPE_KEYWORDS)


def hype_keyword_hits(text: str) -> int:
    t = (text or "").lower()
    return sum(1 for kw in HYPE_KEYWORDS if kw in t)


def normalize_entity_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    cleaned = cleaned.strip(".,;:\"'()[]")
    return cleaned


def is_plausible_company_name(name: str) -> bool:
    n = normalize_entity_name(name)
    if len(n) < 2 or len(n) > 80:
        return False
    lower = n.lower()
    if lower in _REJECT_NAMES:
        return False
    if n.isupper() and len(n) > 12:
        return False
    return re.search(r"[A-Za-z]", n) is not None


def extract_entities_from_text(text: str) -> list[str]:
    """Heuristic company names from a headline or summary."""
    if not text or not text.strip():
        return []
    found: set[str] = set()
    for pattern in _HEADLINE_PATTERNS:
        for match in pattern.finditer(text):
            candidate = normalize_entity_name(match.group(1))
            if is_plausible_company_name(candidate):
                found.add(candidate)
    return sorted(found)
