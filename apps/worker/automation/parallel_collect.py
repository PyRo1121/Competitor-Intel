#!/usr/bin/env python3
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from automation.collector_registry import BASE, PARALLEL_COLLECTORS
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("parallel_collect")

MAX_PARALLEL = 6


def run_parallel_collectors(
    scripts: list[str] | None = None,
) -> tuple[int, int, list[tuple[str, float]]]:
    targets = list(scripts or PARALLEL_COLLECTORS)
    timings: list[tuple[str, float]] = []
    success = 0
    batch_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        futures = {
            pool.submit(run_script, script, cwd=BASE, logger=logger): script
            for script in targets
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
    configure_logging(logger)
    ok, total, _ = run_parallel_collectors()
    sys.exit(0 if ok == total else 1)
