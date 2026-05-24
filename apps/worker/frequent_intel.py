#!/usr/bin/env python3
"""
Frequent ingest — RSS, HN, multi-source, GitHub, etc. without Hermes Grok X.

Run hourly (or every 2h) via cron/systemd. Keeps raw_signals and intelligence_events
fresh for the dashboard while X verification stays on grok_refresh.py schedule.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from ci_paths import ensure_app_paths

ensure_app_paths()

from automation.collector_registry import EXTRACTION_SCRIPTS, FREQUENT_SEQUENTIAL
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("frequent_intel")


def main() -> int:
    os.environ["CI_AUTO_GROK_X"] = "0"
    os.environ["CI_REQUIRE_GROK_X"] = "0"

    logger.info("=== Frequent Competitor Intelligence (no Grok X) ===")
    pipeline_start = time.perf_counter()
    timings: list[tuple[str, float]] = []
    success = 0
    total_steps = 0

    ok, elapsed = run_script(
        "automation/parallel_collect.py",
        "--profile",
        "frequent",
        logger=logger,
    )
    timings.append(("parallel_collectors_frequent", elapsed))
    total_steps += 1
    if ok:
        success += 1

    for script in EXTRACTION_SCRIPTS:
        ok, elapsed = run_script(script, logger=logger)
        timings.append((script, elapsed))
        total_steps += 1
        if ok:
            success += 1

    for script, args in FREQUENT_SEQUENTIAL:
        ok, elapsed = run_script(script, *args, logger=logger)
        timings.append((script, elapsed))
        total_steps += 1
        if ok:
            success += 1

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("Frequent pipeline wall time: %.1fs", total_elapsed)
    log_timings(logger, timings)

    if success == total_steps:
        logger.info("Frequent ingest complete. All %s steps succeeded.", total_steps)
    else:
        logger.warning("Frequent ingest: %s/%s steps succeeded.", success, total_steps)
    return 0 if success == total_steps else 1


if __name__ == "__main__":
    configure_logging(logger)
    sys.exit(main())
