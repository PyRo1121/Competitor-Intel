#!/usr/bin/env python3
"""ATS + hiring signals → job_posting_claims → job_postings."""

from __future__ import annotations

import logging
import os

from db.connection import get_conn

from collectors.jobs.job_pipeline import run_job_pipeline

logger = logging.getLogger("job_rollup")


def _counts() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    out = {}
    for table in (
        "job_posting_claims",
        "job_postings",
        "job_posting_skills",
        "company_job_boards",
        "job_velocity_snapshots",
    ):
        try:
            out[table] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            out[table] = 0
    out["active_postings"] = cur.execute(
        "SELECT COUNT(*) FROM job_postings WHERE is_active = 1"
    ).fetchone()[0]
    conn.close()
    return out


def run(*, company_limit: int | None = None) -> dict:
    return run_job_pipeline(company_limit=company_limit)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    before = _counts()
    limit_raw = os.environ.get("CI_JOB_COMPANY_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else None
    result = run(company_limit=limit)
    after = _counts()
    logger.info("Job rollup before=%s", before)
    logger.info("Job rollup result=%s", result)
    logger.info("Job rollup after=%s", after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
