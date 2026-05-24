#!/usr/bin/env python3
"""
Daily Intelligence Pipeline Runner
Runs the full competitor intelligence stack daily.
"""

import argparse
import logging
import os
import sys
import time

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

from automation.collector_registry import get_daily_sequential
from automation.pipeline_runner import run_pipeline
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("daily_intel")


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily competitor intelligence pipeline")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continue after any pipeline step failure (default: abort)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log pipeline steps without running subprocesses (sets CI_DAILY_DRY_RUN=1)",
    )
    args = parser.parse_args()
    if args.dry_run:
        os.environ["CI_DAILY_DRY_RUN"] = "1"

    logger.info("=== Daily Competitor Intelligence Pipeline ===")
    pipeline_start = time.perf_counter()
    timings: list[tuple[str, float]] = []

    grok_batch = MONOREPO_ROOT / "data" / "hermes_enrich" / "grok_x_results.json"
    os.environ.setdefault("GROK_X_RESULTS_PATH", str(grok_batch))
    skip_grok = os.environ.get("CI_SKIP_GROK_X", "").strip().lower() in ("1", "true", "yes")
    parallel_profile = "daily-no-x" if skip_grok else "full"
    if skip_grok:
        os.environ["CI_AUTO_GROK_X"] = "0"
        os.environ["CI_REQUIRE_GROK_X"] = "0"
        os.environ.setdefault("EDGAR_FORM_D_BULK", "0")
        os.environ.setdefault("CI_HN_SKIP_ALGOLIA", "1")
        logger.info("Grok X: skipped (CI_SKIP_GROK_X); use grok_refresh.py on its own cron")
        logger.info(
            "SEC Form D bulk: skipped on daily (EDGAR_FORM_D_BULK=0); use edgar_form_d_weekly.py"
        )
    else:
        os.environ.setdefault("CI_AUTO_GROK_X", "1")
        os.environ.setdefault("CI_REQUIRE_GROK_X", "1")
        logger.info(
            "Grok X: CI_AUTO_GROK_X=1 CI_REQUIRE_GROK_X=1 path=%s",
            grok_batch,
        )

    os.environ.setdefault("CI_INGEST_STAGING", "1")
    parallel_start = time.perf_counter()
    parallel_result = run_pipeline(
        [("automation/parallel_collect.py", ("--profile", parallel_profile))],
        abort_on_fail=True,
        force=args.force,
        dry_run=args.dry_run,
        logger=logger,
        run_script_fn=run_script,
    )
    timings.extend(parallel_result.timings)
    logger.info("Parallel batch wall time: %.1fs", time.perf_counter() - parallel_start)
    if parallel_result.aborted:
        return 1

    tail_result = run_pipeline(
        [("run_intel.py", ()), *get_daily_sequential()],
        abort_on_fail=True,
        force=args.force,
        dry_run=args.dry_run,
        logger=logger,
        run_script_fn=run_script,
    )
    timings.extend(tail_result.timings)
    if tail_result.aborted:
        return 1

    success = parallel_result.success + tail_result.success
    total_steps = parallel_result.total_steps + tail_result.total_steps
    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("Pipeline wall time: %.1fs", total_elapsed)
    log_timings(logger, timings)

    if success == total_steps:
        logger.info("Pipeline complete. All %s steps succeeded.", total_steps)
        if os.environ.get("CI_SQLITE_POST_CHECKPOINT", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        ):
            try:
                from db.sqlite_tuning import post_ingest_wal_maintenance

                ck_mode = os.environ.get("CI_SQLITE_POST_CHECKPOINT_MODE", "RESTART").strip()
                stats = post_ingest_wal_maintenance(ck_mode or "RESTART")
                logger.info("Post-ingest SQLite maintenance: %s", stats)
            except Exception as exc:
                logger.warning("Post-ingest SQLite maintenance failed: %s", exc)
        if os.environ.get("CI_SQLITE_POST_BACKUP", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        ):
            started_bk = time.perf_counter()
            try:
                from db.health import backup_db

                out = backup_db()
                logger.info("Post-daily sqlite backup: %s", out)
                ok_bk = True
            except Exception as exc:
                logger.warning("Post-daily sqlite backup failed: %s", exc)
                ok_bk = False
            elapsed_bk = time.perf_counter() - started_bk
            timings.append(("sqlite_backup", elapsed_bk))
            if not ok_bk:
                logger.warning("Post-daily sqlite backup failed (non-fatal)")
    else:
        logger.warning("Pipeline complete. %s/%s steps succeeded.", success, total_steps)
    return 0 if success == total_steps else 1


if __name__ == "__main__":
    configure_logging(logger)
    sys.exit(main())
