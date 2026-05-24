"""Company claims from APIs + ingested RSS/signals (no website HTML scraping)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3

from utils.http import close_http_client

from .api_enrich import gather_api_profile
from .claims import upsert_profile_claim

logger = logging.getLogger("company_data.extract_website")

_PROFILE_FIELDS = {
    "founded_year": "founded_year",
    "headquarters": "headquarters",
    "team_size": "team_size",
    "team_size_source": "team_size_source",
    "business_model": "business_model",
    "tech_stack": "tech_stack",
    "description_long": "description_long",
    "legal_name": "legal_name",
    "industry": "industry",
    "entity_type": "entity_type",
    "website_url": "website_url",
    "public_repos": "public_repos",
}


def extract_company_website(
    conn: sqlite3.Connection,
    company_id: int,
    name: str,
    website: str | None,
    github_org: str | None,
) -> dict[str, int]:
    stats = {"profile_claims": 0, "team_claims": 0, "product_claims": 0}
    stats["profile_claims"] += _profile_from_apis(conn, company_id, name, website, github_org)
    return stats


def _profile_from_apis(
    conn: sqlite3.Connection,
    company_id: int,
    name: str,
    website: str | None,
    github_org: str | None,
) -> int:
    created = 0
    confidence = {
        "github_api": 0.78,
        "sec_edgar_api": 0.9,
    }

    for source, data, url_base in gather_api_profile(name, github_org):
        for key, field_key in _PROFILE_FIELDS.items():
            val = data.get(key)
            if val is None or val == "":
                continue
            val = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
            _, is_new = upsert_profile_claim(
                conn,
                company_id=company_id,
                field_key=field_key,
                field_value=val,
                source=source,
                source_url=f"{url_base}#{field_key}",
                company_website=website,
                extraction_confidence=confidence.get(source, 0.7),
            )
            if is_new:
                created += 1
    return created


def _website_batch_size(batch_size: int | None) -> int:
    if batch_size is None:
        batch_size = int(os.environ.get("COMPANY_DATA_WEBSITE_BATCH_SIZE", "10"))
    return max(1, batch_size)


def run_website_extraction(
    conn: sqlite3.Connection,
    batch_size: int | None = None,
) -> dict[str, int]:
    """API enrichment for all active companies in batches (default 10)."""
    size = _website_batch_size(batch_size)
    totals: dict[str, int] = {
        "profile_claims": 0,
        "team_claims": 0,
        "product_claims": 0,
        "companies": 0,
        "batches": 0,
    }
    rows: list[sqlite3.Row] = conn.execute(
        """
        SELECT id, name, website, github_org
        FROM companies
        WHERE status = 'active' OR status IS NULL
        ORDER BY score DESC NULLS LAST
        """
    ).fetchall()
    total = len(rows)
    if total == 0:
        close_http_client()
        return totals

    batch_count = (total + size - 1) // size
    logger.info(
        "API company enrichment: %s companies in %s batches of up to %s",
        total,
        batch_count,
        size,
    )

    for batch_idx, start in enumerate(range(0, total, size), start=1):
        chunk = rows[start : start + size]
        logger.info(
            "API batch %s/%s — companies %s–%s",
            batch_idx,
            batch_count,
            start + 1,
            start + len(chunk),
        )
        for row in chunk:
            stats = extract_company_website(
                conn,
                int(row["id"]),
                row["name"],
                row["website"],
                row["github_org"],
            )
            for k in ("profile_claims", "team_claims", "product_claims"):
                totals[k] += stats.get(k, 0)
            totals["companies"] += 1
        conn.commit()
        totals["batches"] = batch_idx

    close_http_client()
    return totals
