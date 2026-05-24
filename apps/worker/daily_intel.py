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
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("daily_intel")


def _abort_unless_force(step: str, ok: bool, force: bool) -> bool:
    """Return True if the pipeline should stop immediately."""
    if ok:
        return False
    if force:
        logger.warning("%s failed (--force: continuing)", step)
        return False
    logger.error("%s failed; aborting pipeline (use --force to continue)", step)
    return True


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
    success = 0
    total_steps = 0

    grok_batch = MONOREPO_ROOT / "data" / "hermes_enrich" / "grok_x_results.json"
    os.environ.setdefault("GROK_X_RESULTS_PATH", str(grok_batch))
    skip_grok = os.environ.get("CI_SKIP_GROK_X", "").strip().lower() in ("1", "true", "yes")
    parallel_profile = "daily-no-x" if skip_grok else "full"
    if skip_grok:
        os.environ["CI_AUTO_GROK_X"] = "0"
        os.environ["CI_REQUIRE_GROK_X"] = "0"
        logger.info("Grok X: skipped (CI_SKIP_GROK_X); use grok_refresh.py on its own cron")
    else:
        os.environ.setdefault("CI_AUTO_GROK_X", "1")
        os.environ.setdefault("CI_REQUIRE_GROK_X", "1")
        logger.info(
            "Grok X: CI_AUTO_GROK_X=1 CI_REQUIRE_GROK_X=1 path=%s",
            grok_batch,
        )

    parallel_start = time.perf_counter()
    ok, elapsed = run_script(
        "automation/parallel_collect.py",
        "--profile",
        parallel_profile,
        logger=logger,
        step_id="parallel_collect",
    )
    timings.append(("parallel_collectors", elapsed))
    total_steps += 1
    if ok:
        success += 1
    logger.info("Parallel batch wall time: %.1fs", time.perf_counter() - parallel_start)
    if _abort_unless_force("parallel_collect", ok, args.force):
        log_timings(logger, timings)
        return 1

    ok, elapsed = run_script("run_intel.py", logger=logger, step_id="run_intel")
    timings.append(("run_intel.py", elapsed))
    total_steps += 1
    if ok:
        success += 1
    if _abort_unless_force("run_intel", ok, args.force):
        log_timings(logger, timings)
        return 1

    for script, script_args in get_daily_sequential():
        step_id = script.rsplit("/", 1)[-1].replace(".py", "")
        ok, elapsed = run_script(script, *script_args, logger=logger, step_id=step_id)
        timings.append((script, elapsed))
        total_steps += 1
        if ok:
            success += 1
        elif _abort_unless_force(script, ok, args.force):
            log_timings(logger, timings)
            return 1

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
            ok_bk, elapsed_bk = run_script(
                "scripts/sqlite_health.py",
                "--backup",
                logger=logger,
                step_id="sqlite_backup",
            )
            timings.append(("sqlite_backup", elapsed_bk))
            if not ok_bk:
                logger.warning("Post-daily sqlite backup failed (non-fatal)")
    else:
        logger.warning("Pipeline complete. %s/%s steps succeeded.", success, total_steps)
    return 0 if success == total_steps else 1


if __name__ == "__main__":
    configure_logging(logger)
    sys.exit(main())
