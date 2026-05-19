#!/usr/bin/env python3
import logging
import sqlite3
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

from db.connection import get_conn
from collectors.enrichment.utils import safe_request

logger = logging.getLogger("tech_stack")

TECH_PATTERNS = {
    "frontend": [
        ("react", r"react|reactjs|facebook/react"),
        ("vue", r"vue\.js|vuejs| Evan You"),
        ("svelte", r"svelte|sveltekit"),
        ("angular", r"angular|angularjs"),
        ("next.js", r"next\.js|nextjs|vercel/next"),
        ("tailwind", r"tailwind|tailwindcss"),
    ],
    "backend": [
        ("node.js", r"node\.js|nodejs|express\.js|nest\.js"),
        ("python", r"python|django|flask|fastapi"),
        ("go", r"\bgo\b|golang|gin-gonic"),
        ("rust", r"rust|actix|tokio|rocket\.rs"),
        ("java", r"java|spring|springboot"),
        ("ruby", r"ruby|ruby on rails|rails"),
    ],
    "database": [
        ("postgresql", r"postgres|postgresql"),
        ("mysql", r"mysql|mariadb"),
        ("mongodb", r"mongodb|mongo"),
        ("redis", r"redis"),
        ("elasticsearch", r"elasticsearch|elastic"),
        ("sqlite", r"sqlite"),
        ("clickhouse", r"clickhouse"),
        ("supabase", r"supabase"),
    ],
    "infra": [
        ("aws", r"aws|amazon web services|ec2|s3|lambda"),
        ("gcp", r"gcp|google cloud|gke|cloud run"),
        ("azure", r"azure|microsoft cloud"),
        ("kubernetes", r"kubernetes|k8s|kubectl|helm"),
        ("docker", r"docker|containerization"),
        ("terraform", r"terraform|iac"),
        ("vercel", r"vercel"),
        ("cloudflare", r"cloudflare|workers|pages"),
    ],
    "ml_ai": [
        ("pytorch", r"pytorch|torch"),
        ("tensorflow", r"tensorflow|tf\.keras"),
        ("openai", r"openai|gpt-4|gpt-3|chatgpt"),
        ("langchain", r"langchain"),
        ("huggingface", r"huggingface|transformers"),
        ("pinecone", r"pinecone"),
        ("weaviate", r"weaviate"),
        ("chroma", r"chroma db|chromadb"),
    ],
    "security": [
        ("auth0", r"auth0"),
        ("okta", r"okta"),
        ("stripe", r"stripe"),
    ],
}


def detect_from_website(website: str) -> List[Dict[str, Any]]:
    if not website:
        return []
    try:
        if not website.startswith("http"):
            website = "https://" + website
        resp = safe_request(website, timeout=15, allow_redirects=True)
        if not resp:
            return []
        text = resp.text.lower()
        detected = []
        for category, patterns in TECH_PATTERNS.items():
            for tech, pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    detected.append({
                        "category": category,
                        "technology": tech,
                        "source": "website",
                        "confidence": 0.6,
                    })
        return detected
    except Exception as e:
        logger.error("Failed to detect from %s: %s", website, e)
        return []


def detect_from_github(github_org: str) -> List[Dict[str, Any]]:
    if not github_org:
        return []
    try:
        url = f"https://api.github.com/users/{github_org}/repos?per_page=100"
        resp = safe_request(url, timeout=15)
        if not resp:
            return []
        repos = resp.json()
        if not isinstance(repos, list):
            return []
        detected = []
        lang_counts = {}
        for repo in repos:
            lang = repo.get("language")
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1
        total = sum(lang_counts.values())
        for lang, count in lang_counts.items():
            if total > 0 and count / total > 0.1:
                detected.append({
                    "category": "backend",
                    "technology": lang.lower(),
                    "source": "github",
                    "confidence": min(0.5 + (count / total) * 0.5, 0.95),
                })
        return detected
    except Exception as e:
        logger.error("Failed to detect from GitHub %s: %s", github_org, e)
        return []


def store_tech_stack(company_id: int, detections: List[Dict[str, Any]]):
    if not detections:
        return
    conn = get_conn()
    cursor = conn.cursor()
    for det in detections:
        cursor.execute(
            """
            INSERT INTO technology_stack (company_id, category, technology, detection_source, confidence)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                company_id,
                det["category"],
                det["technology"],
                det["source"],
                det["confidence"],
            ),
        )
    conn.commit()
    conn.close()


def run() -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, website, github_org FROM companies")
    companies = cursor.fetchall()
    conn.close()
    total_detections = 0
    for company_id, website, github_org in companies:
        detections = []
        if website:
            detections.extend(detect_from_website(website))
        if github_org:
            detections.extend(detect_from_github(github_org))
        if detections:
            total_detections += len(detections)
            store_tech_stack(company_id, detections)
            logger.info("Detected %d tech items for company %d", len(detections), company_id)
    logger.info("Tech stack detection complete: %d total detections", total_detections)
    return total_detections


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
