#!/usr/bin/env python3
"""
Legacy company enrichment (website/GitHub HTML).
Company-data rollup uses company_data/api_enrich.py instead.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger("company_enricher")

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import contextlib

from db.connection import get_conn
from utils.browser_fetch import fetch_browser_text
from utils.http import close_http_client, safe_request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page(url: str, timeout: int = 15) -> str | None:
    """Fetch HTML; browser impersonation first (curl_cffi), then httpx fallback."""
    html = fetch_browser_text(url, timeout=float(timeout), headers=HEADERS)
    if html:
        return html
    resp = safe_request(url, timeout=float(timeout), headers=HEADERS)
    if resp is not None:
        return resp.text
    return None


def scrape_website(_company_name: str, website: str) -> dict:
    """Scrape company website for about page and job board data."""
    if not website:
        return {}

    data = {}

    # Try about page
    about_urls = [
        f"{website}/about",
        f"{website}/company",
        f"{website}/team",
        f"{website}/careers",
    ]

    for url in about_urls:
        html = fetch_page(url, timeout=10)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Look for team size mentions
        text = soup.get_text()

        # "Join our team of 50+" or "50+ employees"
        m = re.search(r"(\d+)\+?\s*(employees?|team members?|people)", text, re.IGNORECASE)
        if m and not data.get("team_size"):
            data["team_size"] = int(m.group(1))
            data["team_size_source"] = "website"

        # "Founded in 2020"
        m = re.search(r"founded\s+(?:in\s+)?(\d{4})", text, re.IGNORECASE)
        if m and not data.get("founded_year"):
            data["founded_year"] = int(m.group(1))

        # Job board - count open roles
        if "careers" in url or "jobs" in url:
            jobs = soup.find_all("a", href=re.compile(r"job|career|position", re.I))
            if jobs:
                data["hiring_count"] = len(jobs)

    # Try pricing page for business model
    pricing_html = fetch_page(f"{website}/pricing", timeout=8)
    if pricing_html:
        soup = BeautifulSoup(pricing_html, "html.parser")
        text = soup.get_text().lower()

        if "api" in text:
            data["business_model"] = "API"
        elif "enterprise" in text or "contact sales" in text:
            data["business_model"] = "Enterprise SaaS"
        elif any(w in text for w in ["/mo", "monthly", "per month", "plan"]):
            data["business_model"] = "SaaS"
        elif "open source" in text or "github" in text:
            data["business_model"] = "Open Source"

    return data


def scrape_github_org(github_org: str) -> dict:
    """Scrape GitHub organization page for tech stack and repo count."""
    if not github_org:
        return {}

    url = f"https://github.com/{github_org}"
    html = fetch_page(url, timeout=10)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    data = {}

    # Look for language stats
    lang_section = soup.find(string=re.compile(r"Top languages", re.I))
    if lang_section:
        parent = lang_section.find_parent("div")
        if parent:
            langs = parent.find_all(string=re.compile(r"[A-Za-z#\+]+"))
            data["tech_stack"] = json.dumps(
                [lang.strip() for lang in langs if len(lang.strip()) > 1][:8]
            )

    # Repo count
    repo_link = soup.find("a", href=f"/{github_org}?tab=repositories")
    if repo_link:
        count_text = repo_link.find("span", class_=re.compile(r"Counter"))
        if count_text:
            with contextlib.suppress(ValueError):
                data["repo_count"] = int(count_text.get_text(strip=True).replace(",", ""))

    return data


def enrich_company(company_id: int, name: str, website: str, github_org: str) -> bool:
    """Enrich a single company with deep data from all sources."""
    logger.info("Enriching %s...", name)

    # Collect from all sources
    website_data = scrape_website(name, website) if website else {}
    github_data = scrape_github_org(github_org) if github_org else {}

    merged = {}
    merged.update(github_data)
    merged.update(website_data)

    if not merged:
        logger.warning("No enrichment data found for %s", name)
        return False

    # Store in database
    conn = get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO company_details
            (company_id, founded_year, headquarters, team_size, team_size_source,
             business_model, tech_stack, description_long, last_enriched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id) DO UPDATE SET
                founded_year = COALESCE(EXCLUDED.founded_year, founded_year),
                headquarters = COALESCE(EXCLUDED.headquarters, headquarters),
                team_size = COALESCE(EXCLUDED.team_size, team_size),
                team_size_source = COALESCE(EXCLUDED.team_size_source, team_size_source),
                business_model = COALESCE(EXCLUDED.business_model, business_model),
                tech_stack = COALESCE(EXCLUDED.tech_stack, tech_stack),
                description_long = COALESCE(EXCLUDED.description_long, description_long),
                last_enriched_at = EXCLUDED.last_enriched_at
        """,
            (
                company_id,
                merged.get("founded_year"),
                merged.get("headquarters"),
                merged.get("team_size"),
                merged.get("team_size_source"),
                merged.get("business_model"),
                merged.get("tech_stack"),
                merged.get("description_long"),
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        logger.info(
            "Enriched %s: %s", name, ", ".join(f"{k}={v}" for k, v in merged.items() if v)[:100]
        )
        return True
    except sqlite3.Error as e:
        logger.error("DB error enriching %s: %s", name, e)
        return False
    finally:
        conn.close()


def run_company_enrichment(limit: int = 50) -> dict:
    """Run enrichment for all companies."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, website, github_org
        FROM companies
        WHERE status = 'active'
        ORDER BY score DESC NULLS LAST, github_stars DESC
        LIMIT ?
    """,
        (limit,),
    )

    companies = cursor.fetchall()
    conn.close()

    enriched = 0
    failed = 0

    for row in companies:
        if enrich_company(row["id"], row["name"], row["website"], row["github_org"]):
            enriched += 1
        else:
            failed += 1

    close_http_client()
    logger.info("Company enrichment complete: %d enriched, %d failed", enriched, failed)
    return {"enriched": enriched, "failed": failed, "total": len(companies)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    run_company_enrichment()
