#!/usr/bin/env python3
"""
GitHub Signal Collector v2
Pulls stars, forks, recent activity + tracks star velocity over time.
Distinct from github_signals.py (trending repos → raw_signals).
"""

import logging
import os
from datetime import datetime

from db.connection import get_conn
from utils.http import close_http_client, get_http_client

logger = logging.getLogger("github_collector")

GITHUB_API = "https://api.github.com"


def github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def create_github_history_table():
    """Ensure github_history table exists."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS github_history (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            stars INTEGER,
            forks INTEGER,
            repos INTEGER,
            recorded_at TEXT,
            UNIQUE(company_id, recorded_at)
        )
    """)
    conn.commit()
    conn.close()


def extract_github_org(website: str, _x_handle: str | None = None) -> str | None:
    """Extract GitHub organization name from URL."""
    if not website:
        return None

    if "github.com/" in website:
        parts = website.split("github.com/")[1].split("/")
        return parts[0] if parts else None

    known = {
        "cursor.com": "cursor",
        "crewai.com": "crewAIInc",
        "langchain.com": "langchain-ai",
        "llamaindex.ai": "run-llama",
        "e2b.dev": "e2b-dev",
        "browserbase.com": "browserbase",
        "multion.ai": "MultiOn-AI",
        "dust.tt": "dust-tt",
    }
    for domain, org in known.items():
        if domain in website.lower():
            return org
    return None


def get_github_data(org: str) -> dict:
    """Fetch GitHub data for an organization or user."""
    client = get_http_client()
    headers = github_headers()
    params = {"per_page": 100}

    for path in (f"orgs/{org}/repos", f"users/{org}/repos"):
        try:
            resp = client.get(
                f"{GITHUB_API}/{path}",
                headers=headers,
                params=params,
                timeout=15.0,
            )
            if resp.status_code != 200:
                continue
            repos = resp.json()
            if not isinstance(repos, list):
                continue
            total_stars = sum(r.get("stargazers_count", 0) for r in repos)
            total_forks = sum(r.get("forks_count", 0) for r in repos)
            return {
                "stars": total_stars,
                "forks": total_forks,
                "repos": len(repos),
            }
        except Exception as exc:
            logger.warning("GitHub API error for %s (%s): %s", org, path, exc)

    return {"error": f"No repos found for {org}"}


def record_github_snapshot(company_id: int, data: dict):
    """Record a GitHub snapshot for a company."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO github_history
        (company_id, stars, forks, repos, recorded_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            company_id,
            data.get("stars", 0),
            data.get("forks", 0),
            data.get("repos", 0),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def calculate_star_velocity(company_id: int) -> dict:
    """Calculate star growth over last 7 and 30 days."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT stars, recorded_at FROM github_history
        WHERE company_id = ?
        ORDER BY recorded_at DESC
    """,
        (company_id,),
    )

    records = cursor.fetchall()
    conn.close()

    if len(records) < 2:
        return {"velocity_7d": 0, "velocity_30d": 0, "trend": "insufficient_data"}

    latest_stars = records[0][0]
    latest_date = datetime.fromisoformat(records[0][1])

    velocity_7d = 0
    for stars, date_str in records[1:]:
        date = datetime.fromisoformat(date_str)
        if (latest_date - date).days <= 7:
            velocity_7d = latest_stars - stars
            break

    velocity_30d = 0
    for stars, date_str in records[1:]:
        date = datetime.fromisoformat(date_str)
        if (latest_date - date).days <= 30:
            velocity_30d = latest_stars - stars
            break

    trend = "growing" if velocity_7d > 0 else "flat"

    return {
        "velocity_7d": velocity_7d,
        "velocity_30d": velocity_30d,
        "trend": trend,
    }


def run_github_collection(limit: int = 40) -> int:
    """Run GitHub collection for tracked companies (companies + github_history)."""
    create_github_history_table()
    logger.info("Starting GitHub collection for up to %d companies", limit)

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, website, github_org FROM companies
        WHERE (github_org IS NOT NULL AND github_org != '')
           OR website IS NOT NULL
        LIMIT ?
    """,
        (limit,),
    )

    companies = cursor.fetchall()
    conn.close()

    updated = 0
    try:
        for company_id, name, website, github_org in companies:
            org = (github_org or "").strip() or extract_github_org(website or "")
            if not org:
                continue

            data = get_github_data(org)
            if "error" in data:
                logger.debug("Skip %s (%s): %s", name, org, data["error"])
                continue

            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE companies
                SET github_stars = ?, github_forks = ?, github_repos = ?, last_github_update = ?
                WHERE id = ?
            """,
                (
                    data["stars"],
                    data["forks"],
                    data["repos"],
                    datetime.now().isoformat(),
                    company_id,
                ),
            )
            conn.commit()
            conn.close()

            record_github_snapshot(company_id, data)
            updated += 1
            logger.info("Updated %s: %d stars", name, data["stars"])
    finally:
        close_http_client()

    logger.info("GitHub collection complete. Updated %d companies.", updated)
    return updated


def run() -> int:
    return run_github_collection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
