#!/usr/bin/env python3
"""High-frequency ingest wrapper — RSS, X batch, website monitor."""

import logging
import sys
import time

from automation.collector_registry import CONTINUOUS_COLLECTORS
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("continuous_ingest")


def run_continuous_ingest() -> tuple[int, int]:
    logger.info("=== Continuous ingest cycle ===")
    cycle_start = time.perf_counter()
    timings: list[tuple[str, float]] = []
    success = 0

    for script in CONTINUOUS_COLLECTORS:
        ok, elapsed = run_script(script, logger=logger)
        timings.append((script, elapsed))
        if ok:
            success += 1

    log_timings(logger, timings, top_n=len(CONTINUOUS_COLLECTORS))
    logger.info(
        "Continuous ingest: %s/%s succeeded in %.1fs",
        success,
        len(CONTINUOUS_COLLECTORS),
        time.perf_counter() - cycle_start,
    )
    return success, len(CONTINUOUS_COLLECTORS)


if __name__ == "__main__":
    configure_logging(logger)
    ok, total = run_continuous_ingest()
    sys.exit(0 if ok == total else 1)
