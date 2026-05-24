#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from automation.collector_registry import (
    BASE,
    DAILY_NO_X_PARALLEL_COLLECTORS,
    FREQUENT_PARALLEL_COLLECTORS,
    PARALLEL_COLLECTORS,
)
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("parallel_collect")

# Lazy import — parallel_collect must not require db at module load for dry-run tests.
def _staging_files_for_run(run_id: str):
    from db.staging import list_staging_files

    return list_staging_files(run_id)


def _staging_enabled() -> bool:
    return os.environ.get("CI_INGEST_STAGING", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _max_parallel() -> int:
    """Collector subprocesses; default 4 when staging (no DB writes in collectors)."""
    default = "4" if _staging_enabled() else "3"
    raw = os.environ.get("CI_PARALLEL_COLLECTORS", default).strip()
    try:
        return max(1, min(6, int(raw)))
    except ValueError:
        return 3


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
    staging = _staging_enabled()
    run_id = os.environ.get("CI_STAGING_RUN_ID", "").strip()
    if staging and not run_id:
        run_id = uuid.uuid4().hex[:12]
        os.environ["CI_STAGING_RUN_ID"] = run_id
    logger.info(
        "Parallel collectors: max_workers=%s profile=%s staging=%s run_id=%s",
        workers,
        profile,
        staging,
        run_id or "-",
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for script in targets:
            extra: dict[str, str] = {}
            if staging:
                extra = {
                    "CI_INGEST_STAGING": "1",
                    "CI_STAGING_RUN_ID": run_id,
                    "CI_STAGING_SLOT": Path(script).stem,
                }
            futures[pool.submit(run_script, script, cwd=BASE, logger=logger, extra_env=extra)] = (
                script
            )
        for future in as_completed(futures):
            ok, elapsed = future.result()
            script = futures[future]
            timings.append((script, elapsed))
            if ok:
                success += 1

    if staging and run_id and _staging_files_for_run(run_id):
        merge_ok, merge_elapsed = run_script(
            "apps/worker/ingest_staging.py",
            "--run-id",
            run_id,
            cwd=BASE,
            logger=logger,
            step_id="ingest_staging",
        )
        timings.append(("ingest_staging", merge_elapsed))
        if not merge_ok:
            success = max(0, success - 1)
        elif success == len(targets):
            os.environ.pop("CI_STAGING_RUN_ID", None)

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
