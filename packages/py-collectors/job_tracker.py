#!/usr/bin/env python3
import logging
import sqlite3
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from db.connection import get_conn
from collectors.enrichment.utils import safe_request

logger = logging.getLogger("job_tracker")

JOB_BOARDS = {
    "lever": "{company}.jobs.lever.co",
    "greenhouse": "boards.greenhouse.io/{company}",
    "workable": "apply.workable.com/{company}",
    "breezy": "{company}.breezy.hr",
    "recruitee": "{company}.recruitee.com",
    "ashby": "jobs.ashbyhq.com/{company}",
}

TECH_KEYWORDS = [
    "python", "javascript", "typescript", "rust", "go", "java",
    "react", "vue", "svelte", "next.js", "node", "django",
    "postgresql", "mongodb", "redis", "elasticsearch",
    "aws", "gcp", "azure", "kubernetes", "docker", "terraform",
    "machine learning", "tensorflow", "pytorch", "llm", "openai",
    "langchain", "huggingface", "vector database", "embedding",
    "react native", "flutter", "swift", "kotlin",
]


def guess_job_board_url(company_name: str, website: str) -> List[str]:
    urls = []
    slug = company_name.lower().replace(" ", "-").replace(".", "")
    for board, template in JOB_BOARDS.items():
        url = "https://" + template.format(company=slug)
        urls.append(url)
    if website:
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]
        urls.append(f"https://{domain}/careers")
        urls.append(f"https://{domain}/jobs")
        urls.append(f"https://{domain}/about#jobs")
    return urls


def detect_tech_from_job(title: str, description: str) -> List[str]:
    text = f"{title} {description}".lower()
    found = []
    for tech in TECH_KEYWORDS:
        if tech in text:
            found.append(tech)
    return found


def classify_job_type(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["senior", "staff", "principal", "lead", "director", "vp", "head of"]):
        return "senior"
    if any(w in t for w in ["manager", "director", "vp", "head of", "chief"]):
        return "management"
    if any(w in t for w in ["intern", "co-op", "student"]):
        return "intern"
    if any(w in t for w in ["contract", "consultant", "freelance"]):
        return "contract"
    return "mid"


def run() -> int:
    logger.info("Job tracker: checking company career pages")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, website FROM companies WHERE website IS NOT NULL")
    companies = cursor.fetchall()
    conn.close()
    total_jobs = 0
    for company_id, name, website in companies:
        urls = guess_job_board_url(name, website)
        jobs_found = 0
        for url in urls:
            try:
                resp = safe_request(url, timeout=10, allow_redirects=True)
                if not resp:
                    continue
                text = resp.text.lower()
                if any(indicator in text for indicator in ["job", "opening", "position", "role", "career", "apply"]):
                    jobs_found += 1
            except Exception:
                continue
        if jobs_found > 0:
            total_jobs += 1
            logger.info("%s: found job listings (%d boards)", name, jobs_found)
    logger.info("Job tracker: %d companies with active listings", total_jobs)
    return total_jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
