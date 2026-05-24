"""Source tier weights for job posting claims."""

from __future__ import annotations

from collectors.enrichment.funding_source_trust import (
    classify_source as _classify_funding_source,
)
from collectors.enrichment.funding_source_trust import (
    domain_matches_company,
    normalize_domain,
)

ATS_OFFICIAL_PLATFORMS = frozenset(
    {"greenhouse", "lever", "ashby", "workable", "recruitee", "breezy", "company_careers"}
)


def classify_job_source(
    source: str | None,
    source_url: str | None,
    *,
    company_website: str | None = None,
    ats_platform: str | None = None,
) -> tuple[str, float, bool]:
    """Return (source_tier, source_weight, is_official)."""
    if ats_platform in ATS_OFFICIAL_PLATFORMS:
        host = normalize_domain(source_url)
        if domain_matches_company(host, company_website):
            return "company_official", 1.0, True
        return "company_official", 0.92, False

    tier, weight, official = _classify_funding_source(
        source, source_url, company_website=company_website
    )
    return tier, weight, official
