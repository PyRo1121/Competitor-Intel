#!/usr/bin/env python3
"""
Competitor Intelligence Orchestrator v14
Runs the complete pipeline with proper logging, transactions, and error recovery.

Pipeline stages (post-collection; raw ingest is automation/parallel_collect.py):
  1. Schema verification
  2. Intelligence extraction (legacy scripts; canonical path is signal_processor in daily)
  3. Embedding generation (companies + events via Ollama)
  4. Report generation (daily brief + Discord)

Usage:
    python run_intel.py           # Full sweep
    python run_intel.py --dry-run # Validate without storing
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

from automation.collector_registry import EXTRACTION_SCRIPTS

# Ensure log directory exists before configuring logging
(MONOREPO_ROOT / "logs").mkdir(exist_ok=True)

# Configure logging
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

STATE_FILE = MONOREPO_ROOT / ".pipeline_state.json"


class PipelineState:
    """Persistent pipeline state for resumable execution."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except json.JSONDecodeError:
                logger.warning("Corrupt state file, starting fresh")
        return {"last_completed_stage": None, "last_run": None, "runs": []}

    def save(self):
        self.state_file.write_text(json.dumps(self.data, indent=2))

    def mark_stage_complete(self, stage: str):
        self.data["last_completed_stage"] = stage
        self.data["last_run"] = datetime.now().isoformat()

    def is_stage_complete(self, stage: str) -> bool:
        return self.data.get("last_completed_stage") == stage

    def log_run(self, result: dict[str, Any]):
        runs = self.data.setdefault("runs", [])
        runs.append(
            {
                "timestamp": datetime.now().isoformat(),
                **result,
            }
        )
        # Keep last 30 runs
        self.data["runs"] = runs[-30:]


def ensure_schema() -> bool:
    """Verify schema is current. Returns True if OK."""
    logger.info("Verifying database schema...")
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Check if intelligence_events table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='intelligence_events'"
        )
        if not cursor.fetchone():
            logger.error("intelligence_events table missing — run db/schema.py first")
            conn.close()
            return False

        # Check for required columns
        cursor.execute("PRAGMA table_info(intelligence_events)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"event_type", "amount_usd", "confidence", "source_url"}
        missing = required - columns
        if missing:
            logger.warning("Missing columns in intelligence_events: %s", missing)

        conn.close()
        logger.info("Schema verification complete")
        return True

    except sqlite3.Error as e:
        logger.error("Schema verification failed: %s", e)
        return False


def _run_extraction_script(script: str, dry_run: bool = False) -> tuple[bool, float, str | None]:
    """Run an extraction script via subprocess (consistent with daily_intel timing)."""
    import subprocess

    started = time.perf_counter()
    if dry_run:
        logger.info("[DRY RUN] Would run %s", script)
        return True, 0.0, None

    cmd = [sys.executable, str(MONOREPO_ROOT / script)]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=MONOREPO_ROOT)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        msg = f"exit {result.returncode}"
        logger.error("Script failed: %s (%s, %.1fs)", script, msg, elapsed)
        return False, elapsed, msg
    logger.info("Finished %s in %.1fs", script, elapsed)
    return True, elapsed, None


def backfill_intelligence_events(dry_run: bool = False) -> dict[str, Any]:
    """Run EXTRACTION_SCRIPTS if any (empty by default; use signal_processor in daily)."""
    logger.info("=== Stage 2: Intelligence Extraction ===")
    stage_start = time.perf_counter()
    results: dict[str, Any] = {}
    success_count = 0

    for script in EXTRACTION_SCRIPTS:
        name = Path(script).stem
        ok, elapsed, error = _run_extraction_script(script, dry_run)
        results[name] = {"success": ok, "duration": elapsed, "error": error}
        if ok:
            success_count += 1

    elapsed = time.perf_counter() - stage_start
    logger.info(
        "Extraction: %s/%s succeeded in %.1fs",
        success_count,
        len(EXTRACTION_SCRIPTS),
        elapsed,
    )
    return {
        "stage": "extraction",
        "success_count": success_count,
        "total": len(EXTRACTION_SCRIPTS),
        "duration": elapsed,
        "results": results,
    }


def embed_all(dry_run: bool = False) -> dict[str, Any]:
    """Generate embeddings for companies and intelligence events."""
    logger.info("=== Stage 3: Embedding Generation ===")
    stage_start = time.perf_counter()

    if dry_run:
        logger.info("[DRY RUN] Would generate embeddings")
        return {"stage": "embedding", "embedded": 0, "dry_run": True}

    # Lazy import to avoid loading Ollama if not needed
    try:
        from embeddings import get_embedding
    except ImportError as e:
        logger.warning(f"Embedding module not available: {e}")
        return {"stage": "embedding", "success": False, "error": str(e)}

    stats: dict[str, Any] = {"companies": 0, "events": 0, "errors": []}

    # Embed companies
    try:
        from embed_companies import embed_companies

        embed_companies()
        stats["companies"] = "completed"
        logger.info("✓ Company embeddings updated")
    except Exception as e:
        stats["errors"].append(f"Company embedding: {e}")
        logger.warning("Company embedding skipped: %s", e)

    # Embed intelligence events (batch update)
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, event_type, amount_usd, source
            FROM intelligence_events
            WHERE embedding IS NULL OR embedding = ''
        """)
        rows = cursor.fetchall()

        if not rows:
            logger.info("No new intelligence events to embed")
        else:
            logger.info("Embedding %s intelligence events...", len(rows))
            updated = 0
            failed = 0

            for event_id, event_type, amount, source in rows:
                try:
                    text = f"{event_type or 'Event'} ${amount or 0:,} via {source or 'Unknown'}"
                    emb = get_embedding(text)
                    cursor.execute(
                        "UPDATE intelligence_events SET embedding = ? WHERE id = ?",
                        (json.dumps(emb), event_id),
                    )
                    updated += 1

                    # Commit every 10 to avoid large transactions
                    if updated % 10 == 0:
                        conn.commit()
                        logger.debug("  Committed batch of 10 embeddings")

                except Exception as e:
                    failed += 1
                    logger.warning(f"  Failed to embed event {event_id}: {e}")

            conn.commit()
            stats["events"] = updated
            if failed:
                stats["errors"].append(f"Event embedding: {failed} failures")
            logger.info("[OK] Embedded %s intelligence events (%s failed)", updated, failed)

    except Exception as e:
        stats["errors"].append(f"Event embedding: {e}")
        logger.error("Event embedding failed: %s", e)

    finally:
        if conn:
            conn.close()

    elapsed = time.perf_counter() - stage_start
    stats["duration"] = elapsed
    logger.info("[OK] Embedding stage complete in %.1fs", elapsed)
    return {"stage": "embedding", **stats}


def generate_reports(dry_run: bool = False) -> dict[str, Any]:
    """Generate daily brief and Discord report."""
    logger.info("=== Stage 4: Report Generation ===")
    stage_start = time.perf_counter()
    stats: dict[str, Any] = {"daily_brief": False, "discord": False}
    brief = None

    # Daily brief
    try:
        from daily_brief import export_brief, generate_daily_brief

        brief = generate_daily_brief()
        if not dry_run:
            export_brief(brief)
        stats["daily_brief"] = True
        logger.info("✓ Daily brief generated")
    except Exception as e:
        logger.warning("Daily brief failed: %s", e)

    # Discord report
    try:
        from daily_brief import format_for_discord
        from discord_report import post_to_discord

        if not dry_run and brief is not None:
            embed = format_for_discord(brief)
            post_to_discord(embed)
            stats["discord"] = True
            logger.info("✓ Discord report posted")
        elif brief is None:
            logger.warning("Skipping Discord report: no daily brief")
    except Exception as e:
        logger.warning("Discord report failed: %s", e)

    elapsed = time.perf_counter() - stage_start
    stats["duration"] = elapsed
    logger.info("[OK] Report generation complete in %.1fs", elapsed)
    return {"stage": "reports", **stats}


def run_full_sweep(dry_run: bool = False) -> int:
    """Main entry point — full pipeline.

    Returns:
        0 on success, 1 on critical failure
    """
    logger.info("🚀 Competitor Intelligence Full Sweep v14")
    logger.info("Started: %s", datetime.now().isoformat())
    logger.info("Dry run: %s", dry_run)

    overall_start = time.perf_counter()
    state = PipelineState(STATE_FILE)
    results = []

    # Stage 1: Schema verification
    if not ensure_schema():
        logger.critical("Schema verification failed — aborting")
        return 1
    state.mark_stage_complete("schema")

    # Stage 2: Intelligence extraction (after parallel_collect in daily_intel)
    extraction_results = backfill_intelligence_events(dry_run)
    results.append(extraction_results)
    state.mark_stage_complete("extraction")

    # Stage 3: Embeddings
    embedding_results = embed_all(dry_run)
    results.append(embedding_results)
    state.mark_stage_complete("embedding")

    # Stage 4: Reports
    report_results = generate_reports(dry_run)
    results.append(report_results)
    state.mark_stage_complete("reports")

    # Finalize
    elapsed = time.perf_counter() - overall_start
    summary = {
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": elapsed,
        "dry_run": dry_run,
        "stages": results,
    }
    state.log_run(summary)
    state.save()

    logger.info("[OK] Full sweep complete in %.1fs", elapsed)
    logger.info("   State saved to %s", STATE_FILE)

    if EXTRACTION_SCRIPTS:
        extraction_success = extraction_results.get("success_count", 0)
        if extraction_success < len(EXTRACTION_SCRIPTS):
            logger.warning(
                "Extraction incomplete: %s/%s scripts succeeded",
                extraction_success,
                len(EXTRACTION_SCRIPTS),
            )
            return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description="Competitor Intelligence Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Validate without storing data")
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )
    args = parser.parse_args()

    if args.log_level:
        logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Ensure log directory exists
    (MONOREPO_ROOT / "logs").mkdir(exist_ok=True)

    exit_code = run_full_sweep(dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
