#!/usr/bin/env python3
"""Merge staged raw_signals JSONL into SQLite (single writer). See docs/SQLITE.md."""

from __future__ import annotations

import argparse
import logging
import os

from ci_paths import ensure_app_paths

ensure_app_paths()

from db.staging import clear_staging_run, merge_staging_run

logger = logging.getLogger("ingest_staging")


def main() -> int:
    os.environ.setdefault("CI_SQLITE_WRITER_LOCK_TIMEOUT_SEC", "900")
    parser = argparse.ArgumentParser(description="Merge staged collector JSONL into SQLite")
    parser.add_argument(
        "--run-id",
        default=os.environ.get("CI_STAGING_RUN_ID", "").strip(),
        help="Staging run id (default: CI_STAGING_RUN_ID)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep JSONL after merge (or set CI_STAGING_KEEP=1)",
    )
    args = parser.parse_args()
    if not args.run_id:
        logger.error("--run-id or CI_STAGING_RUN_ID required")
        return 1

    summary = merge_staging_run(args.run_id)
    logger.info("Staging merge complete: %s", summary)
    keep = args.keep or os.environ.get("CI_STAGING_KEEP", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not keep:
        clear_staging_run(args.run_id)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
