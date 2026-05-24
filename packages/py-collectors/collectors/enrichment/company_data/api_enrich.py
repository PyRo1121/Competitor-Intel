"""Company profile facts via official APIs (no HTML scraping)."""

from __future__ import annotations

import json
import logging
from typing import Any

from collectors.enrichment.github_deep import github_api
from utils.http import safe_request

logger = logging.getLogger("company_data.api_enrich")

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_SEC_TICKERS: dict[str, int] | None = None


def github_org_profile(github_org: str) -> dict[str, Any]:
    """GitHub REST API org metadata + language mix from top repos."""
    if not github_org:
        return {}

    org = github_api(f"orgs/{github_org}")
    if not org:
        return {}

    out: dict[str, Any] = {
        "source_url": f"https://api.github.com/orgs/{github_org}",
    }
    if org.get("description"):
        out["description_long"] = org["description"]
    if org.get("location"):
        out["headquarters"] = org["location"]
    if org.get("public_repos") is not None:
        out["public_repos"] = org["public_repos"]

    langs: dict[str, int] = {}
    repos = github_api(f"orgs/{github_org}/repos?sort=updated&per_page=8")
    if isinstance(repos, list):
        for repo in repos[:8]:
            name = repo.get("name")
            if not name:
                continue
            lang_data = github_api(f"repos/{github_org}/{name}/languages")
            if isinstance(lang_data, dict):
                for lang, count in lang_data.items():
                    langs[lang] = langs.get(lang, 0) + int(count)
    if langs:
        top = sorted(langs.items(), key=lambda x: -x[1])[:8]
        out["tech_stack"] = json.dumps([lang for lang, _ in top])

    return out


def _load_sec_tickers() -> dict[str, int]:
    global _SEC_TICKERS
    if _SEC_TICKERS is not None:
        return _SEC_TICKERS

    from collectors.sources_registry import SEC_USER_AGENT

    resp = safe_request(
        SEC_TICKERS_URL,
        timeout=20.0,
        headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"},
    )
    mapping: dict[str, int] = {}
    if resp is not None:
        try:
            raw = resp.json()
            for entry in raw.values():
                title = (entry.get("title") or "").strip().lower()
                cik = int(entry.get("cik_str") or 0)
                if title and cik:
                    mapping[title] = cik
        except (ValueError, TypeError, AttributeError) as exc:
            logger.warning("SEC tickers parse failed: %s", exc)

    _SEC_TICKERS = mapping
    return mapping


def lookup_sec_company(name: str) -> dict[str, Any]:
    """SEC EDGAR submissions JSON for US public registrants (free API)."""
    tickers = _load_sec_tickers()
    key = name.strip().lower()
    cik = tickers.get(key)
    if not cik:
        for title, cid in tickers.items():
            if title.startswith(key) or key.startswith(title.split(",")[0].strip()):
                cik = cid
                break
    if not cik:
        return {}

    from collectors.sources_registry import SEC_USER_AGENT

    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    resp = safe_request(
        url,
        timeout=20.0,
        headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"},
    )
    if resp is None:
        return {}

    try:
        data = resp.json()
    except ValueError:
        return {}

    out: dict[str, Any] = {
        "cik": cik,
        "source_url": url,
    }
    if data.get("name"):
        out["legal_name"] = data["name"]
    if data.get("sicDescription"):
        out["industry"] = data["sicDescription"]
    if data.get("stateOfIncorporation"):
        out["headquarters"] = data["stateOfIncorporation"]
    if data.get("entityType"):
        out["entity_type"] = data["entityType"]

    return out


def gather_api_profile(
    company_name: str,
    github_org: str | None,
) -> list[tuple[str, dict[str, Any], str]]:
    """Returns list of (source_key, fields, source_url)."""
    rows: list[tuple[str, dict[str, Any], str]] = []

    if github_org:
        gh = github_org_profile(github_org)
        if gh:
            url = gh.pop("source_url", f"https://api.github.com/orgs/{github_org}")
            rows.append(("github_api", gh, url))

    sec = lookup_sec_company(company_name)
    if sec:
        url = sec.pop("source_url", SEC_TICKERS_URL)
        rows.append(("sec_edgar_api", sec, url))

    return rows
