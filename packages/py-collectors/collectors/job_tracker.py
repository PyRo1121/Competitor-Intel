#!/usr/bin/env python3
"""Job tracker — granular ATS ingest (Greenhouse, Lever, Ashby) → claims → postings."""

from __future__ import annotations

import logging
import os

from ci_paths import ensure_app_paths

ensure_app_paths()

from collectors.jobs.job_pipeline import run_job_pipeline

logger = logging.getLogger("job_tracker")


def run() -> int:
    limit_raw = os.environ.get("CI_JOB_COMPANY_LIMIT", "").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else None
    result = run_job_pipeline(company_limit=limit)
    return int(result.get("claims_new", 0) + result.get("jobs_fetched", 0))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
