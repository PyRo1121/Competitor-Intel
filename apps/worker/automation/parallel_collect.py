#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from automation.collector_registry import (
    BASE,
    DAILY_NO_X_PARALLEL_COLLECTORS,
    FREQUENT_PARALLEL_COLLECTORS,
    PARALLEL_COLLECTORS,
)
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("parallel_collect")


def _max_parallel() -> int:
    raw = os.environ.get("CI_PARALLEL_COLLECTORS", "4").strip()
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 4


_PROFILE_SCRIPTS = {
    "full": PARALLEL_COLLECTORS,
    "frequent": FREQUENT_PARALLEL_COLLECTORS,
    "daily-no-x": DAILY_NO_X_PARALLEL_COLLECTORS,
}


def run_parallel_collectors(
    scripts: list[str] | None = None,
    *,
    profile: str = "full",
) -> tuple[int, int, list[tuple[str, float]]]:
    if scripts is None:
        targets = list(_PROFILE_SCRIPTS.get(profile, PARALLEL_COLLECTORS))
    else:
        targets = list(scripts)
    timings: list[tuple[str, float]] = []
    success = 0
    batch_start = time.perf_counter()

    workers = _max_parallel()
    logger.info("Parallel collectors: max_workers=%s profile=%s", workers, profile)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_script, script, cwd=BASE, logger=logger): script for script in targets
        }
        for future in as_completed(futures):
            ok, elapsed = future.result()
            script = futures[future]
            timings.append((script, elapsed))
            if ok:
                success += 1

    log_timings(logger, timings, top_n=5)
    logger.info(
        "Parallel collection: %s/%s succeeded in %.1fs",
        success,
        len(targets),
        time.perf_counter() - batch_start,
    )
    return success, len(targets), timings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run parallel raw-signal collectors")
    parser.add_argument(
        "--profile",
        choices=sorted(_PROFILE_SCRIPTS),
        default="full",
        help="full = daily batch (incl. X ingest file); frequent = RSS/open web only",
    )
    args = parser.parse_args()
    configure_logging(logger)
    ok, total, _ = run_parallel_collectors(profile=args.profile)
    sys.exit(0 if ok == total else 1)
