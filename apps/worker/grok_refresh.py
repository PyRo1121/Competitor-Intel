#!/usr/bin/env python3
"""
X refresh — fetch (xurl or Grok) + ingest + signal reprocessing.

CI_X_PROVIDER=xurl  → official xurl CLI (X API v2, no LLM)
CI_X_PROVIDER=grok   → Hermes x_search (default; unchanged for CI)

Run on a separate cron (~5×/day Eastern) so hourly RSS ingest does not burn X quota.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

from automation.collector_registry import GROK_COLLECTORS
from automation.run_utils import configure_logging, log_timings, run_script

logger = logging.getLogger("grok_refresh")


def main() -> int:
    if os.environ.get("CI_DISABLE_HERMES", "").strip().lower() in ("1", "true", "yes"):
        logger.info("Grok refresh skipped (CI_DISABLE_HERMES)")
        return 0
    if os.environ.get("CI_SKIP_GROK_X", "").strip().lower() in ("1", "true", "yes"):
        logger.info("Grok refresh skipped (CI_SKIP_GROK_X)")
        return 0

    grok_batch = MONOREPO_ROOT / "data" / "hermes_enrich" / "grok_x_results.json"
    os.environ.setdefault("GROK_X_RESULTS_PATH", str(grok_batch))
    os.environ["CI_AUTO_GROK_X"] = "1"
    os.environ["CI_REQUIRE_GROK_X"] = "1"

    provider = os.environ.get("CI_X_PROVIDER", "grok").strip().lower()
    if provider not in ("xurl", "grok"):
        logger.error("Invalid CI_X_PROVIDER=%r (use xurl or grok)", provider)
        return 1

    logger.info("=== X refresh (provider=%s) ===", provider)
    logger.info("Batch path: %s", grok_batch)

    pipeline_start = time.perf_counter()
    timings: list[tuple[str, float]] = []
    success = 0
    total_steps = 0

    ok, elapsed = run_script("apps/worker/x_refresh/fetch.py", logger=logger)
    timings.append((f"fetch_x_{provider}", elapsed))
    total_steps += 1
    if ok:
        success += 1

    for script in GROK_COLLECTORS:
        ok, elapsed = run_script(script, logger=logger)
        timings.append((script, elapsed))
        total_steps += 1
        if ok:
            success += 1

    ok, elapsed = run_script("collectors/signal_processor.py", logger=logger)
    timings.append(("signal_processor", elapsed))
    total_steps += 1
    if ok:
        success += 1

    ok, elapsed = run_script("collectors/signal_url_fanout.py", logger=logger)
    timings.append(("signal_url_fanout", elapsed))
    total_steps += 1
    if ok:
        success += 1

    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("X refresh wall time: %.1fs", total_elapsed)
    log_timings(logger, timings)

    if success == total_steps:
        logger.info("X refresh complete. All %s steps succeeded.", total_steps)
    else:
        logger.warning("X refresh: %s/%s steps succeeded.", success, total_steps)
    return 0 if success == total_steps else 1


if __name__ == "__main__":
    configure_logging(logger)
    sys.exit(main())
