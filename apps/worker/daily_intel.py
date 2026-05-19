#!/usr/bin/env python3
"""
Daily Intelligence Pipeline Runner
Runs the full competitor intelligence stack daily.
"""

import logging
import sys
import time

from ci_paths import ensure_app_paths

ensure_app_paths()

from automation.collector_registry import DAILY_SEQUENTIAL
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("daily_intel")


def main() -> int:
    logger.info("=== Daily Competitor Intelligence Pipeline ===")
    pipeline_start = time.perf_counter()
    timings: list[tuple[str, float]] = []
    success = 0
    total_steps = 0

    parallel_start = time.perf_counter()
    ok, elapsed = run_script("automation/parallel_collect.py", logger=logger)
    timings.append(("parallel_collectors", elapsed))
    total_steps += 1
    if ok:
        success += 1
    logger.info("Parallel batch wall time: %.1fs", time.perf_counter() - parallel_start)

    ok, elapsed = run_script("run_intel.py", logger=logger)
    timings.append(("run_intel.py", elapsed))
    total_steps += 1
    if ok:
        success += 1

    for script, args in DAILY_SEQUENTIAL:
        ok, elapsed = run_script(script, *args, logger=logger)
        timings.append((script, elapsed))
        total_steps += 1
        if ok:
            success += 1

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("Pipeline wall time: %.1fs", total_elapsed)
    log_timings(logger, timings)

    if success == total_steps:
        logger.info("Pipeline complete. All %s steps succeeded.", total_steps)
    else:
        logger.warning("Pipeline complete. %s/%s steps succeeded.", success, total_steps)
    return 0 if success == total_steps else 1


if __name__ == "__main__":
    configure_logging(logger)
    sys.exit(main())
