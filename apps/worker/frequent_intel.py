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

from automation.collector_registry import EXTRACTION_SCRIPTS, get_frequent_sequential
from automation.pipeline_runner import run_pipeline
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("frequent_intel")


def main() -> int:
    os.environ["CI_AUTO_GROK_X"] = "0"
    os.environ["CI_REQUIRE_GROK_X"] = "0"

    logger.info("=== Frequent Competitor Intelligence (no Grok X) ===")
    pipeline_start = time.perf_counter()

    steps: list[str | tuple[str, tuple[str, ...]]] = [
        ("automation/parallel_collect.py", ("--profile", "frequent")),
        *EXTRACTION_SCRIPTS,
        *get_frequent_sequential(),
    ]
    result = run_pipeline(steps, logger=logger, run_script_fn=run_script)

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("Frequent pipeline wall time: %.1fs", total_elapsed)
    log_timings(logger, result.timings)

    if result.success == result.total_steps:
        logger.info("Frequent ingest complete. All %s steps succeeded.", result.total_steps)
    else:
        logger.warning(
            "Frequent ingest: %s/%s steps succeeded.",
            result.success,
            result.total_steps,
        )
    return 0 if result.success == result.total_steps else 1


if __name__ == "__main__":
    configure_logging(logger)
    sys.exit(main())
