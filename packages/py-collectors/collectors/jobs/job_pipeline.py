"""Orchestrate ATS fetch → claims → canonical postings → velocity snapshots."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from db.connection import get_conn
from db.migrations import apply_runtime_migrations

from .ats_clients import probe_company_boards
from .job_aggregator import aggregate_job_postings, record_velocity_snapshots
from .job_enricher import store_job_claim, upsert_company_job_board

logger = logging.getLogger("job_pipeline")


def _load_companies(limit: int | None = None) -> list[tuple]:
    conn = get_conn()
    sql = """
        SELECT id, name, website, github_org
        FROM companies
        WHERE website IS NOT NULL OR github_org IS NOT NULL
        ORDER BY github_stars DESC, name
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def _claims_from_hiring_events() -> int:
    """Promote intelligence_events labeled Hiring with job-like descriptions."""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ie.id, ie.company_id, ie.description, ie.source, ie.source_url,
               ie.raw_signal_id, ie.announced_date
        FROM intelligence_events ie
        WHERE ie.company_id IS NOT NULL
          AND ie.event_type = 'Hiring'
          AND ie.description IS NOT NULL
          AND (
            LOWER(ie.description) LIKE '%engineer%'
            OR LOWER(ie.description) LIKE '%developer%'
            OR LOWER(ie.description) LIKE '%hiring%'
            OR LOWER(ie.description) LIKE '%open role%'
            OR LOWER(ie.description) LIKE '%job%'
          )
        LIMIT 200
        """
    )
    rows = cur.fetchall()
    conn.close()
    created = 0
    for row in rows:
        title = row["description"][:200]
        claim_id, is_new = store_job_claim(
            int(row["company_id"]),
            {
                "title": title,
                "description": row["description"],
                "source": row["source"] or "intelligence_event",
                "source_url": row["source_url"] or f"intel-event:{row['id']}",
                "posted_at": row["announced_date"],
                "intelligence_event_id": row["id"],
                "raw_signal_id": row["raw_signal_id"],
                "ats_platform": "press_mention",
                "extraction_confidence": 0.55,
            },
        )
        if claim_id and is_new:
            created += 1
    return created


def run_job_pipeline(*, company_limit: int | None = None) -> dict[str, Any]:
    conn = get_conn()
    apply_runtime_migrations(conn)
    conn.commit()
    conn.close()

    companies = _load_companies(company_limit)
    claims_new = 0
    claims_updated = 0
    boards_found = 0
    jobs_fetched = 0

    for company_id, name, _website, github_org in companies:
        for board in probe_company_boards(name, github_org):
            boards_found += 1
            upsert_company_job_board(
                company_id,
                board["ats_platform"],
                board["board_slug"],
                board["board_url"],
                len(board["jobs"]),
            )
            for job in board["jobs"]:
                jobs_fetched += 1
                claim_id, is_new = store_job_claim(company_id, job)
                if claim_id:
                    if is_new:
                        claims_new += 1
                    else:
                        claims_updated += 1

    event_claims = _claims_from_hiring_events()
    agg = aggregate_job_postings()
    snapshots = record_velocity_snapshots()

    summary = {
        "companies_scanned": len(companies),
        "boards_found": boards_found,
        "jobs_fetched": jobs_fetched,
        "claims_new": claims_new,
        "claims_updated": claims_updated,
        "event_claims_new": event_claims,
        **agg,
        "velocity_snapshots": snapshots,
    }
    logger.info("Job pipeline complete: %s", summary)
    return summary
