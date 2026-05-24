"""Parse job titles, compensation, seniority, location, and tech stack from text."""

from __future__ import annotations

import json
import re
from typing import Any

TECH_KEYWORDS: dict[str, str] = {
    "python": "language",
    "javascript": "language",
    "typescript": "language",
    "rust": "language",
    "go": "language",
    "golang": "language",
    "java": "language",
    "c++": "language",
    "ruby": "language",
    "react": "framework",
    "vue": "framework",
    "svelte": "framework",
    "next.js": "framework",
    "node": "runtime",
    "django": "framework",
    "fastapi": "framework",
    "postgresql": "database",
    "postgres": "database",
    "mongodb": "database",
    "redis": "database",
    "elasticsearch": "database",
    "aws": "cloud",
    "gcp": "cloud",
    "azure": "cloud",
    "kubernetes": "infra",
    "docker": "infra",
    "terraform": "infra",
    "machine learning": "ml",
    "pytorch": "ml",
    "tensorflow": "ml",
    "llm": "ml",
    "langchain": "ml",
    "openai": "ml",
    "huggingface": "ml",
    "kafka": "data",
    "spark": "data",
    "dbt": "data",
}


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip())


def parse_seniority_band(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["intern", "co-op", "coop", "student", "new grad", "newgrad"]):
        return "intern"
    if any(w in t for w in ["junior", "jr.", "jr ", "entry level", "entry-level"]):
        return "junior"
    if any(w in t for w in ["staff", "principal", "distinguished", "fellow"]):
        return "staff"
    if any(
        w in t
        for w in [
            "director",
            "vp ",
            "vice president",
            "head of",
            "chief ",
            " cto",
            " ceo",
            " cfo",
            " cpo",
        ]
    ):
        return "executive"
    if any(w in t for w in ["senior", "sr.", "sr ", "lead ", "team lead"]):
        return "senior"
    if any(w in t for w in ["manager", "management"]):
        return "management"
    if any(w in t for w in ["contract", "consultant", "freelance"]):
        return "contract"
    return "mid"


def parse_employment_type(title: str, commitment: str | None = None) -> str:
    blob = f"{title} {(commitment or '')}".lower()
    if any(w in blob for w in ["intern", "internship", "co-op"]):
        return "internship"
    if any(w in blob for w in ["contract", "consultant", "freelance"]):
        return "contract"
    if "part-time" in blob or "part time" in blob:
        return "part_time"
    return "full_time"


def parse_remote_policy(location: str | None, description: str = "") -> str:
    blob = f"{location or ''} {description}".lower()
    if "remote" in blob and ("hybrid" in blob or "onsite" in blob or "on-site" in blob):
        return "hybrid"
    if "remote" in blob:
        return "remote"
    if any(w in blob for w in ["hybrid", "flexible"]):
        return "hybrid"
    if any(w in blob for w in ["onsite", "on-site", "in-office", "in office"]):
        return "onsite"
    return "unknown"


def parse_salary_usd(text: str) -> tuple[int | None, int | None, str | None]:
    """Return (min_usd, max_usd, raw_string)."""
    if not text:
        return None, None, None
    patterns = [
        r"\$([\d,]+)k?\s*[-–—to]+\s*\$([\d,]+)k?\b",
        r"\$([\d,]+)\s*[-–—]\s*\$([\d,]+)\b",
        r"\$([\d,]+)k?\s*\+\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if not m:
            continue
        raw = m.group(0)
        try:
            lo = int(m.group(1).replace(",", ""))
            hi = int(m.group(2).replace(",", "")) if m.lastindex and m.lastindex >= 2 else lo
            if lo < 1000:
                lo *= 1000
            if hi < 1000:
                hi *= 1000
            return lo, hi, raw
        except (ValueError, IndexError):
            continue
    m = re.search(r"\$([\d,]+)k?\b", text, re.I)
    if m:
        val = int(m.group(1).replace(",", ""))
        if val < 1000:
            val *= 1000
        return val, val, m.group(0)
    return None, None, None


def extract_tech_stack(title: str, description: str = "") -> list[dict[str, str]]:
    text = f"{title} {description}".lower()
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for skill, category in TECH_KEYWORDS.items():
        if skill in text and skill not in seen:
            seen.add(skill)
            found.append({"skill": skill, "category": category})
    return found[:25]


def parse_job_posting(
    *,
    title: str,
    description: str = "",
    location: str | None = None,
    department: str | None = None,
    team: str | None = None,
    commitment: str | None = None,
) -> dict[str, Any]:
    title = normalize_title(title)
    desc = (description or "")[:8000]
    seniority = parse_seniority_band(title)
    employment = parse_employment_type(title, commitment)
    remote = parse_remote_policy(location, desc)
    sal_min, sal_max, sal_raw = parse_salary_usd(f"{title} {desc}")
    tech = extract_tech_stack(title, desc)
    return {
        "title": title,
        "department": department or team,
        "team": team or department,
        "location": location,
        "location_type": remote,
        "remote_policy": remote,
        "seniority_band": seniority,
        "employment_type": employment,
        "job_type": employment,
        "salary_min_usd": sal_min,
        "salary_max_usd": sal_max,
        "salary_range": sal_raw,
        "description_snippet": desc[:500] if desc else None,
        "description_text": desc or None,
        "tech_stack_json": json.dumps(tech) if tech else None,
    }
