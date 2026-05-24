"""Re-queue raw_signals missing intelligence_events."""

from __future__ import annotations

import argparse
import logging

from ci_paths import db_path, ensure_app_paths

from db.connection import get_conn
from db.migrations import apply_runtime_migrations

logger = logging.getLogger("db.reprocess")
ensure_app_paths()


def count_orphan_processed(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM raw_signals rs
        WHERE rs.processed = 1
          AND NOT EXISTS (
              SELECT 1 FROM intelligence_events ie
              WHERE ie.raw_signal_id = rs.id
          )
        """
    )
    return int(cur.fetchone()[0])


def count_without_event(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM raw_signals rs
        WHERE NOT EXISTS (
            SELECT 1 FROM intelligence_events ie WHERE ie.raw_signal_id = rs.id
        )
        """
    )
    return int(cur.fetchone()[0])


def reset_orphans(conn, *, dry_run: bool) -> int:
    n = count_orphan_processed(conn)
    if n == 0:
        logger.info("No orphan processed signals to reset")
        return 0
    if dry_run:
        logger.info("Would reset %d raw_signals to processed=0", n)
        return n
    conn.execute(
        """
        UPDATE raw_signals
        SET processed = 0
        WHERE processed = 1
          AND NOT EXISTS (
              SELECT 1 FROM intelligence_events ie
              WHERE ie.raw_signal_id = raw_signals.id
          )
        """
    )
    conn.commit()
    logger.info("Reset %d raw_signals to processed=0", n)
    return n


def reset_without_event(conn, *, dry_run: bool) -> int:
    n = count_without_event(conn)
    if n == 0:
        logger.info("No raw_signals missing intelligence_events")
        return 0
    if dry_run:
        logger.info("Would reset %d raw_signals (no linked event)", n)
        return n
    conn.execute(
        """
        UPDATE raw_signals
        SET processed = 0
        WHERE NOT EXISTS (
            SELECT 1 FROM intelligence_events ie
            WHERE ie.raw_signal_id = raw_signals.id
        )
        """
    )
    conn.commit()
    logger.info("Reset %d raw_signals (no linked event)", n)
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-queue orphan processed raw_signals")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report count only; do not update rows",
    )
    parser.add_argument(
        "--run-processor",
        action="store_true",
        help="After reset, run signal_processor once",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Database: %s", db_path())
    conn = get_conn()
    apply_runtime_migrations(conn)

    reset_orphans(conn, dry_run=args.dry_run)
    reset_without_event(conn, dry_run=args.dry_run)
    conn.close()

    if args.run_processor and not args.dry_run:
        from collectors.signal_processor import process_signals

        totals = {"processed": 0, "created": 0, "skipped": 0}
        while True:
            batch = process_signals(batch_size=500)
            for key in totals:
                totals[key] += batch.get(key, 0)
            logger.info("Batch: %s", batch)
            if batch.get("processed", 0) == 0:
                break
        logger.info("Processor totals: %s", totals)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
