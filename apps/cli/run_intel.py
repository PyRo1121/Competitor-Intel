#!/usr/bin/env python3
"""
Thin post-ingest gate for daily_intel: verify SQLite schema.

Intelligence extraction runs in daily sequential (`signal_processor`, rollups).
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

from automation.collector_registry import EXTRACTION_SCRIPTS

(MONOREPO_ROOT / "logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(MONOREPO_ROOT / "logs" / "run_intel.log", mode="a"),
    ],
)
logger = logging.getLogger("run_intel")

from db.connection import get_conn


def ensure_schema() -> bool:
    """Verify core tables exist."""
    logger.info("Verifying database schema...")
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='intelligence_events'"
        )
        if not cursor.fetchone():
            logger.error("intelligence_events table missing — run db/schema init first")
            conn.close()
            return False
        conn.close()
        logger.info("Schema verification complete")
        return True
    except sqlite3.Error as e:
        logger.error("Schema verification failed: %s", e)
        return False


def _run_extraction_script(script: str, dry_run: bool = False) -> tuple[bool, float, str | None]:
    import subprocess

    started = time.perf_counter()
    if dry_run:
        logger.info("[DRY RUN] Would run %s", script)
        return True, 0.0, None

    cmd = [sys.executable, str(MONOREPO_ROOT / script)]
    result = subprocess.run(cmd, cwd=MONOREPO_ROOT)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        return False, elapsed, f"exit {result.returncode}"
    return True, elapsed, None


def backfill_intelligence_events(dry_run: bool = False) -> dict:
    """Run EXTRACTION_SCRIPTS if any (empty by default)."""
    if not EXTRACTION_SCRIPTS:
        logger.info("No EXTRACTION_SCRIPTS configured — skipping")
        return {"stage": "extraction", "success_count": 0, "total": 0}

    success_count = 0
    for script in EXTRACTION_SCRIPTS:
        ok, _elapsed, _err = _run_extraction_script(script, dry_run)
        if ok:
            success_count += 1
    return {
        "stage": "extraction",
        "success_count": success_count,
        "total": len(EXTRACTION_SCRIPTS),
    }


def run_full_sweep(dry_run: bool = False) -> int:
    if not ensure_schema():
        return 1
    extraction = backfill_intelligence_events(dry_run)
    if extraction["total"] and extraction["success_count"] < extraction["total"]:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Schema gate for daily pipeline")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(run_full_sweep(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
