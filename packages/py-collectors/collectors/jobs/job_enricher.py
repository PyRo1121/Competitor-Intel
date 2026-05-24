"""Store per-source job claims and skill rows."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import Any

from db.connection import get_conn

from .job_parser import extract_tech_stack, parse_job_posting
from .job_source_trust import classify_job_source

logger = logging.getLogger("job_enricher")


def _company_website(company_id: int) -> str | None:
    conn = get_conn()
    row = conn.execute("SELECT website FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return row[0] if row else None


def store_job_claim(company_id: int, raw: dict[str, Any]) -> tuple[int | None, bool]:
    """Insert or update one job_posting_claim. Returns (claim_id, is_new)."""
    parsed = parse_job_posting(
        title=raw.get("title") or "",
        description=raw.get("description") or raw.get("description_text") or "",
        location=raw.get("location"),
        department=raw.get("department"),
        team=raw.get("team"),
        commitment=raw.get("commitment") or raw.get("employment_type"),
    )
    source_url = (raw.get("source_url") or "").strip()
    if not source_url:
        ext = raw.get("external_id") or ""
        ats = raw.get("ats_platform") or raw.get("source") or "unknown"
        source_url = f"job:{company_id}:{ats}:{ext}:{parsed['title'][:80]}"

    website = _company_website(company_id)
    tier, weight, official = classify_job_source(
        raw.get("source"),
        source_url,
        company_website=website,
        ats_platform=raw.get("ats_platform"),
    )

    payload_json = None
    if raw.get("raw_payload") is not None:
        try:
            payload_json = json.dumps(raw["raw_payload"], default=str)[:20000]
        except (TypeError, ValueError):
            payload_json = None

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM job_posting_claims WHERE source_url = ?",
            (source_url,),
        )
        existed = cur.fetchone() is not None

        cur.execute(
            """
            INSERT INTO job_posting_claims
            (company_id, external_id, title, department, team, location, location_type,
             remote_policy, seniority_band, employment_type, job_type,
             salary_min_usd, salary_max_usd, salary_range, salary_currency,
             description_snippet, description_text, tech_stack_json,
             source, source_url, source_tier, source_weight, is_official,
             ats_platform, posted_at, closes_at, is_active, extraction_confidence,
             intelligence_event_id, raw_signal_id, raw_payload_json, extracted_at)
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(source_url) DO UPDATE SET
                title = excluded.title,
                department = excluded.department,
                team = excluded.team,
                location = excluded.location,
                location_type = excluded.location_type,
                remote_policy = excluded.remote_policy,
                seniority_band = excluded.seniority_band,
                employment_type = excluded.employment_type,
                job_type = excluded.job_type,
                salary_min_usd = excluded.salary_min_usd,
                salary_max_usd = excluded.salary_max_usd,
                salary_range = excluded.salary_range,
                description_snippet = excluded.description_snippet,
                description_text = excluded.description_text,
                tech_stack_json = excluded.tech_stack_json,
                source_tier = excluded.source_tier,
                source_weight = excluded.source_weight,
                is_official = excluded.is_official,
                is_active = excluded.is_active,
                extraction_confidence = excluded.extraction_confidence,
                raw_payload_json = excluded.raw_payload_json,
                extracted_at = excluded.extracted_at
            """,
            (
                company_id,
                raw.get("external_id"),
                parsed["title"],
                parsed.get("department"),
                parsed.get("team"),
                parsed.get("location"),
                parsed.get("location_type"),
                parsed.get("remote_policy"),
                parsed.get("seniority_band"),
                parsed.get("employment_type"),
                parsed.get("job_type"),
                parsed.get("salary_min_usd"),
                parsed.get("salary_max_usd"),
                parsed.get("salary_range"),
                raw.get("salary_currency", "USD"),
                parsed.get("description_snippet"),
                parsed.get("description_text"),
                parsed.get("tech_stack_json"),
                raw.get("source") or raw.get("ats_platform"),
                source_url,
                tier,
                weight,
                1 if official else 0,
                raw.get("ats_platform"),
                raw.get("posted_at"),
                raw.get("closes_at"),
                1 if raw.get("is_active", True) else 0,
                float(raw.get("extraction_confidence", 0.85)),
                raw.get("intelligence_event_id"),
                raw.get("raw_signal_id"),
                payload_json,
                datetime.now().isoformat(),
            ),
        )
        cur.execute(
            "SELECT id FROM job_posting_claims WHERE source_url = ?",
            (source_url,),
        )
        row = cur.fetchone()
        claim_id = int(row[0]) if row else None
        if claim_id:
            sync_claim_skills(
                claim_id, parsed["title"], parsed.get("description_text") or "", conn=conn
            )
        conn.commit()
        return claim_id, not existed
    except sqlite3.Error as e:
        logger.error("store_job_claim failed: %s", e)
        return None, False
    finally:
        conn.close()


def sync_claim_skills(
    claim_id: int,
    title: str,
    description: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> int:
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM job_posting_skills WHERE job_posting_claim_id = ?", (claim_id,))
    written = 0
    for item in extract_tech_stack(title, description):
        cur.execute(
            """
            INSERT INTO job_posting_skills
            (job_posting_claim_id, skill, category, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (claim_id, item["skill"], item["category"], 0.9),
        )
        written += 1
    if own:
        conn.commit()
        conn.close()
    return written


def upsert_company_job_board(
    company_id: int,
    ats_platform: str,
    board_slug: str,
    board_url: str,
    job_count: int,
) -> None:
    conn = get_conn()
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO company_job_boards
        (
            company_id, ats_platform, board_slug, board_url, is_verified,
            last_fetched_at, last_job_count,
        )
        VALUES (?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(company_id, ats_platform) DO UPDATE SET
            board_slug = excluded.board_slug,
            board_url = excluded.board_url,
            is_verified = 1,
            last_fetched_at = excluded.last_fetched_at,
            last_job_count = excluded.last_job_count
        """,
        (company_id, ats_platform, board_slug, board_url, now, job_count),
    )
    conn.commit()
    conn.close()
