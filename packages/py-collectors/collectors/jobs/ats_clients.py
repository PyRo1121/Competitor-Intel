"""Fetch normalized job dicts from public ATS APIs (Greenhouse, Lever, Ashby)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from typing import Any

from utils.http import fetch_text, safe_request

logger = logging.getLogger("ats_clients")

# Verified public board slugs (probe these first to avoid noisy 404 scans)
KNOWN_BOARD_SLUGS: dict[str, dict[str, str]] = {
    "anthropic": {"greenhouse": "anthropic"},
    "cursor": {"ashby": "cursor"},
    "perplexity": {"greenhouse": "perplexityai"},
    "notion": {"lever": "notion"},
    "linear": {"lever": "linear"},
    "scale ai": {"greenhouse": "scaleai"},
    "scaleai": {"greenhouse": "scaleai"},
    "harvey": {"greenhouse": "harvey"},
    "runway": {"greenhouse": "runway"},
    "elevenlabs": {"greenhouse": "elevenlabs"},
    "cognition": {"greenhouse": "cognition"},
    "adept": {"greenhouse": "adept"},
}


def slug_variants(name: str, github_org: str | None = None) -> list[str]:
    """Candidate board slugs for ATS probing."""
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip().lower()
        if not s or s in seen:
            return
        seen.add(s)
        out.append(s)

    if github_org:
        add(github_org)
    base = (name or "").strip().lower()
    add(base.replace(" ", "-"))
    add(base.replace(" ", ""))
    add(re.sub(r"[^a-z0-9]+", "-", base).strip("-"))
    add(re.sub(r"[^a-z0-9]+", "", base))
    return out[:8]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")


def fetch_greenhouse(slug: str) -> list[dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    resp = safe_request(url, timeout=15)
    if not resp or resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return []
    jobs: list[dict[str, Any]] = []
    for job in data.get("jobs") or []:
        depts = job.get("departments") or []
        dept = depts[0].get("name") if depts else None
        loc = job.get("location") or {}
        location = loc.get("name") if isinstance(loc, dict) else str(loc or "")
        content = _strip_html(job.get("content") or "")
        jobs.append(
            {
                "external_id": str(job.get("id", "")),
                "title": job.get("title") or "",
                "department": dept,
                "location": location,
                "source_url": job.get("absolute_url") or url,
                "posted_at": (job.get("updated_at") or job.get("created_at") or "")[:10] or None,
                "description": content,
                "ats_platform": "greenhouse",
                "source": "greenhouse",
                "raw_payload": job,
            }
        )
    return jobs


def fetch_lever(slug: str) -> list[dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    resp = safe_request(url, timeout=15)
    if not resp or resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    jobs: list[dict[str, Any]] = []
    for job in data:
        cats = job.get("categories") or {}
        jobs.append(
            {
                "external_id": str(job.get("id", "")),
                "title": job.get("text") or job.get("title") or "",
                "department": cats.get("department"),
                "team": cats.get("team"),
                "location": cats.get("location"),
                "source_url": job.get("hostedUrl") or job.get("applyUrl") or url,
                "posted_at": (job.get("createdAt") or "")[:10] or None,
                "description": _strip_html(
                    job.get("descriptionPlain") or job.get("description") or ""
                ),
                "ats_platform": "lever",
                "source": "lever",
                "commitment": cats.get("commitment"),
                "raw_payload": job,
            }
        )
    return jobs


def fetch_ashby(slug: str) -> list[dict[str, Any]]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    text = fetch_text(url, timeout=15)
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    jobs: list[dict[str, Any]] = []
    for job in data.get("jobs") or []:
        jobs.append(
            {
                "external_id": str(job.get("id", "")),
                "title": job.get("title") or "",
                "department": job.get("department"),
                "team": job.get("team"),
                "location": job.get("location"),
                "source_url": job.get("jobUrl") or job.get("applyUrl") or url,
                "posted_at": (job.get("publishedAt") or job.get("updatedAt") or "")[:10] or None,
                "description": _strip_html(
                    job.get("descriptionPlain") or job.get("description") or ""
                ),
                "ats_platform": "ashby",
                "source": "ashby",
                "employment_type": job.get("employmentType"),
                "raw_payload": job,
            }
        )
    return jobs


def probe_company_boards(
    name: str,
    github_org: str | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Yield {ats_platform, board_slug, jobs: [...]} for each ATS that responds with openings.
    """
    name_key = (name or "").strip().lower()
    known = KNOWN_BOARD_SLUGS.get(name_key, {})
    if github_org and github_org.lower() in KNOWN_BOARD_SLUGS:
        known = {**KNOWN_BOARD_SLUGS[github_org.lower()], **known}

    platforms = (
        ("greenhouse", fetch_greenhouse),
        ("lever", fetch_lever),
        ("ashby", fetch_ashby),
    )

    for platform, fetcher in platforms:
        if platform in known:
            slug = known[platform]
            try:
                jobs = fetcher(slug)
            except Exception as e:
                logger.debug("%s/%s known slug failed: %s", platform, slug, e)
                jobs = []
            if jobs:
                yield {
                    "ats_platform": platform,
                    "board_slug": slug,
                    "board_url": _board_url(platform, slug),
                    "jobs": jobs,
                }
                continue

    for slug in slug_variants(name, github_org):
        for platform, fetcher in platforms:
            if platform in known:
                continue
            try:
                jobs = fetcher(slug)
            except Exception as e:
                logger.debug("%s/%s failed: %s", platform, slug, e)
                continue
            if jobs:
                yield {
                    "ats_platform": platform,
                    "board_slug": slug,
                    "board_url": _board_url(platform, slug),
                    "jobs": jobs,
                }
                break


def _board_url(platform: str, slug: str) -> str:
    if platform == "greenhouse":
        return f"https://boards.greenhouse.io/{slug}"
    if platform == "lever":
        return f"https://jobs.lever.co/{slug}"
    if platform == "ashby":
        return f"https://jobs.ashbyhq.com/{slug}"
    return ""
