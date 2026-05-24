#!/usr/bin/env python3
"""CLI: dedupe raw_signals rows and ensure unique (source, signal_type) index."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import DB_PATH, get_conn
from db.raw_signals_dedup import (
    INDEX_NAME,
    count_duplicate_groups,
    count_rows_to_delete,
    dedupe_raw_signals,
    ensure_dedup_index,
)

logger = logging.getLogger("migrate_dedup")


def verify_index(cursor) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (INDEX_NAME,),
    )
    return cursor.fetchone() is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Dedupe raw_signals and add unique index")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    if not DB_PATH.exists():
        logger.error("Database not found: %s", DB_PATH)
        return 1

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM raw_signals")
    total = cursor.fetchone()[0]
    dup_groups = count_duplicate_groups(cursor)
    to_delete = count_rows_to_delete(cursor)
    logger.info(
        "DB: %s (%s raw_signals, %s duplicate groups, %s rows to delete)",
        DB_PATH,
        total,
        dup_groups,
        to_delete,
    )

    if args.dry_run:
        conn.close()
        return 0

    dedupe_raw_signals(conn)
    ok = ensure_dedup_index(conn)
    index_ok = verify_index(conn.cursor())
    conn.close()

    if not index_ok:
        logger.error("Verification failed: %s missing", INDEX_NAME)
        return 1
    if not ok:
        return 1
    logger.info("Migration complete")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
