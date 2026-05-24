"""Source tier and trust weights for funding claims."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# tier -> (weight, is_official_capable)
TIER_WEIGHTS = {
    "company_official": (1.0, True),
    "regulatory": (0.95, True),
    "press_wire": (0.88, False),
    "tier1_media": (0.78, False),
    "industry_db": (0.72, False),
    "rss": (0.62, False),
    "social": (0.48, False),
    "unknown": (0.50, False),
}

PRESS_WIRE_DOMAINS = frozenset(
    {
        "prnewswire.com",
        "businesswire.com",
        "globenewswire.com",
    }
)

TIER1_MEDIA_DOMAINS = frozenset(
    {
        "techcrunch.com",
        "bloomberg.com",
        "reuters.com",
        "wsj.com",
        "ft.com",
        "theinformation.com",
        "venturebeat.com",
        "forbes.com",
        "cnbc.com",
        "axios.com",
        # Startup / venture press (common in RSS collectors)
        "tech.eu",
        "eu-startups.com",
        "geekwire.com",
        "betakit.com",
        "arcticstartup.com",
        "techfundingnews.com",
        "businessinsider.com",
        "fastcompany.com",
        "sifted.eu",
    }
)

# Credible but narrower or roundup-heavy — tier below tier1, above generic RSS
STARTUP_PRESS_DOMAINS = frozenset(
    {
        "finovate.com",
        "pehub.com",
        "privateequitywire.co.uk",
        "finsmes.com",
        "siliconangle.com",
        "inc.com",
        "entrepreneur.com",
        "pulse2.com",
        "startupdaily.net",
        "angellist.com",
        "producthunt.com",
    }
)

INDUSTRY_DB_DOMAINS = frozenset(
    {
        "crunchbase.com",
        "pitchbook.com",
        "dealroom.co",
        "cbinsights.com",
    }
)

API_SOURCE_TIERS = {
    "github_api": ("company_official", 0.8, False),
    "sec_edgar_api": ("regulatory", 0.95, True),
    "sec_edgar": ("regulatory", 0.95, True),
    "esma_mica": ("regulatory", 0.95, True),
    "ycombinator": ("industry_db", 0.75, False),
    "producthunt": ("rss", 0.7, False),
}

SOCIAL_SOURCES = frozenset({"x", "twitter"})


def normalize_domain(url_or_host: str | None) -> str | None:
    if not url_or_host:
        return None
    raw = url_or_host.strip().lower()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        host = urlparse(raw).netloc or urlparse(raw).path
    except ValueError:
        return None
    host = host.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or None


def domain_matches_company(host: str | None, company_website: str | None) -> bool:
    company_host = normalize_domain(company_website)
    if not host or not company_host:
        return False
    return host == company_host or host.endswith(f".{company_host}")


def classify_source(
    source: str | None,
    source_url: str | None,
    *,
    company_website: str | None = None,
    is_rumor: bool = False,
) -> tuple[str, float, bool]:
    """
    Returns (source_tier, source_weight, is_official).
    Official = announcement on the company's own domain (or regulatory filing).
    """
    if is_rumor:
        tier = "social" if (source or "").lower() in SOCIAL_SOURCES else "unknown"
        weight, _ = TIER_WEIGHTS[tier]
        return tier, min(weight, 0.45), False

    host = normalize_domain(source_url)
    src = (source or "").strip().lower()

    if src in API_SOURCE_TIERS:
        tier, weight, official = API_SOURCE_TIERS[src]
        return tier, weight, official

    if host and domain_matches_company(host, company_website):
        return "company_official", TIER_WEIGHTS["company_official"][0], True

    if src in {"sec", "edgar", "sec_edgar", "esma_mica"} or (
        host and ("sec.gov" in host or "esma.europa.eu" in host)
    ):
        return "regulatory", TIER_WEIGHTS["regulatory"][0], True

    if host and any(host == d or host.endswith(f".{d}") for d in PRESS_WIRE_DOMAINS):
        return "press_wire", TIER_WEIGHTS["press_wire"][0], False

    if host and any(host == d or host.endswith(f".{d}") for d in TIER1_MEDIA_DOMAINS):
        return "tier1_media", TIER_WEIGHTS["tier1_media"][0], False

    if host and any(host == d or host.endswith(f".{d}") for d in STARTUP_PRESS_DOMAINS):
        return "tier1_media", 0.72, False

    if host and any(host == d or host.endswith(f".{d}") for d in INDUSTRY_DB_DOMAINS):
        return "industry_db", TIER_WEIGHTS["industry_db"][0], False

    if src in SOCIAL_SOURCES:
        return "social", TIER_WEIGHTS["social"][0], False

    if src in {"rss", "article", "website", "company_site", "blog", "hackernews"}:
        return "rss", TIER_WEIGHTS["rss"][0], False

    if src == "website" and host:
        return "rss", TIER_WEIGHTS["rss"][0], False

    return "unknown", TIER_WEIGHTS["unknown"][0], False


def reclassify_claim_source_tiers(conn) -> int:
    """Refresh source_tier/weight on all claims from current domain lists."""
    rows = conn.execute(
        "SELECT id, company_id, source, source_url, is_rumor FROM funding_round_claims"
    ).fetchall()
    updated = 0
    for row in rows:
        company_row = conn.execute(
            "SELECT website FROM companies WHERE id = ?", (row["company_id"],)
        ).fetchone()
        website = company_row[0] if company_row else None
        tier, weight, official = classify_source(
            row["source"],
            row["source_url"],
            company_website=website,
            is_rumor=bool(row["is_rumor"]),
        )
        conn.execute(
            """
            UPDATE funding_round_claims
            SET source_tier = ?, source_weight = ?, is_official = ?
            WHERE id = ?
            """,
            (tier, weight, 1 if official else 0, row["id"]),
        )
        updated += 1
    return updated


def headline_snippet(text: str, max_len: int = 280) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"
