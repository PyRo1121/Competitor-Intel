#!/usr/bin/env python3
"""
Deep GitHub Analyzer
Uses GitHub API (with token if available) to extract detailed repository metrics:
commit velocity, contributor patterns, language breakdown, release cadence.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("github_deep")

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.connection import get_conn
from utils.http import get_http_client

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

BASE_URL = "https://api.github.com"


def github_api(path: str) -> dict | None:
    """Make authenticated GitHub API request."""
    url = f"{BASE_URL}/{path.lstrip('/')}"
    client = get_http_client()
    try:
        resp = client.get(url, headers=HEADERS, timeout=15.0)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            logger.debug("GitHub 404 for %s", path)
        elif resp.status_code == 403:
            logger.warning("GitHub rate limited. Set GITHUB_TOKEN for 5000/hr.")
        else:
            logger.warning("GitHub API %d for %s", resp.status_code, path)
    except Exception as e:
        logger.warning("GitHub request failed: %s", e)
    return None


def get_repo_commits(owner: str, repo: str, since_days: int = 30) -> int:
    """Count commits in last N days."""
    since = (datetime.now() - timedelta(days=since_days)).isoformat()
    data = github_api(f"repos/{owner}/{repo}/commits?since={since}&per_page=1")
    if data is None:
        return 0
    # Check Link header for total count if paginated
    return len(data) if isinstance(data, list) else 0


def get_repo_contributors(owner: str, repo: str) -> dict:
    """Get contributor statistics."""
    data = github_api(f"repos/{owner}/{repo}/contributors?per_page=100")
    if not data or not isinstance(data, list):
        return {}

    active = sum(1 for c in data if c.get("contributions", 0) > 0)
    return {
        "total": len(data),
        "active": active,
        "top_contributor": data[0].get("login") if data else None,
    }


def get_repo_languages(owner: str, repo: str) -> dict:
    """Get language breakdown."""
    data = github_api(f"repos/{owner}/{repo}/languages")
    if not data:
        return {}
    total = sum(data.values())
    return {lang: round(bytes_count / total * 100, 1) for lang, bytes_count in data.items()}


def get_repo_releases(owner: str, repo: str) -> list[dict]:
    """Get recent releases."""
    data = github_api(f"repos/{owner}/{repo}/releases?per_page=10")
    if not data or not isinstance(data, list):
        return []
    return [
        {
            "tag": r.get("tag_name"),
            "published": r.get("published_at", "")[:10],
            "name": r.get("name", "")[:60],
        }
        for r in data[:5]
    ]


def get_org_repos(github_org: str) -> list[dict]:
    """Get top repos for an organization."""
    data = github_api(f"orgs/{github_org}/repos?sort=stars&per_page=20")
    if not data or not isinstance(data, list):
        # Try user endpoint
        data = github_api(f"users/{github_org}/repos?sort=stars&per_page=20")

    if not data or not isinstance(data, list):
        return []

    repos = []
    for repo in data:
        if repo.get("fork"):
            continue
        repos.append(
            {
                "name": repo["name"],
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language"),
                "updated": repo.get("updated_at", "")[:10],
            }
        )

    return repos


def analyze_company_github(company_id: int, github_org: str) -> bool:
    """Perform deep GitHub analysis for a company."""
    if not github_org:
        return False

    logger.info("Analyzing GitHub for %s...", github_org)

    repos = get_org_repos(github_org)
    if not repos:
        logger.warning("No repos found for %s", github_org)
        return False

    # Focus on top repo
    top_repo = repos[0]
    owner = github_org
    repo_name = top_repo["name"]

    # Gather metrics
    commits_30d = get_repo_commits(owner, repo_name, 30)
    contributors = get_repo_contributors(owner, repo_name)
    languages = get_repo_languages(owner, repo_name)
    releases = get_repo_releases(owner, repo_name)

    # Calculate metrics
    primary_lang = (
        max(languages, key=lambda k: languages[k]) if languages else top_repo.get("language")
    )
    sum(r["stars"] for r in repos)

    # Store in database
    conn = get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO github_metrics
            (company_id, repo_name, total_commits, commits_last_30d, contributor_count,
             active_contributors_30d, primary_language, languages_json, release_count,
             last_release_date, star_growth_30d, fork_growth_30d, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET
                total_commits = EXCLUDED.total_commits,
                commits_last_30d = EXCLUDED.commits_last_30d,
                contributor_count = EXCLUDED.contributor_count,
                active_contributors_30d = EXCLUDED.active_contributors_30d,
                primary_language = EXCLUDED.primary_language,
                languages_json = EXCLUDED.languages_json,
                release_count = EXCLUDED.release_count,
                last_release_date = EXCLUDED.last_release_date,
                extracted_at = EXCLUDED.extracted_at
        """,
            (
                company_id,
                repo_name,
                0,  # total_commits not easily available
                commits_30d,
                contributors.get("total", 0),
                contributors.get("active", 0),
                primary_lang,
                json.dumps(languages) if languages else None,
                len(releases),
                releases[0]["published"] if releases else None,
                0,  # star_growth_30d requires historical data
                0,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()
        logger.info(
            "GitHub metrics stored for %s: %d commits/30d, %d contributors, %s",
            github_org,
            commits_30d,
            contributors.get("total", 0),
            primary_lang,
        )
        return True
    except sqlite3.Error as e:
        logger.error("DB error storing GitHub metrics: %s", e)
        return False
    finally:
        conn.close()


def run_github_deep_analysis(limit: int = 30) -> dict:
    """Run deep GitHub analysis for all companies with GitHub orgs."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, github_org
        FROM companies
        WHERE github_org IS NOT NULL AND github_org != ''
        ORDER BY github_stars DESC NULLS LAST
        LIMIT ?
    """,
        (limit,),
    )

    companies = cursor.fetchall()
    conn.close()

    analyzed = 0
    failed = 0

    for row in companies:
        if analyze_company_github(row["id"], row["github_org"]):
            analyzed += 1
        else:
            failed += 1

    logger.info("GitHub analysis complete: %d analyzed, %d failed", analyzed, failed)
    return {"analyzed": analyzed, "failed": failed}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    run_github_deep_analysis()
