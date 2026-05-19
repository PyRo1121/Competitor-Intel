#!/usr/bin/env python3
import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import DB_PATH, get_conn

logger = logging.getLogger("migrate_dedup")
INDEX_NAME = "idx_raw_signals_dedup"


def count_duplicate_groups(cursor: sqlite3.Cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT source, signal_type
            FROM raw_signals
            GROUP BY source, signal_type
            HAVING COUNT(*) > 1
        )
        """
    )
    return int(cursor.fetchone()[0])


def count_rows_to_delete(cursor: sqlite3.Cursor) -> int:
    cursor.execute(
        """
        SELECT COUNT(*) FROM raw_signals
        WHERE id NOT IN (
            SELECT MAX(id) FROM raw_signals GROUP BY source, signal_type
        )
        """
    )
    return int(cursor.fetchone()[0])


def dedupe_raw_signals(conn: sqlite3.Connection) -> int:
    cursor = conn.cursor()
    before = count_rows_to_delete(cursor)
    if before == 0:
        logger.info("No duplicate (source, signal_type) rows to remove")
        return 0
    cursor.execute(
        """
        DELETE FROM raw_signals
        WHERE id NOT IN (
            SELECT MAX(id) FROM raw_signals GROUP BY source, signal_type
        )
        """
    )
    conn.commit()
    logger.info("Removed %s duplicate raw_signals rows", before)
    return before


def ensure_dedup_index(conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (INDEX_NAME,),
    )
    if cursor.fetchone():
        logger.info("Index %s already exists", INDEX_NAME)
        return True
    try:
        conn.execute(
            f"CREATE UNIQUE INDEX {INDEX_NAME} ON raw_signals(source, signal_type)"
        )
        conn.commit()
        logger.info("Created unique index %s", INDEX_NAME)
        return True
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        groups = count_duplicate_groups(conn.cursor())
        logger.error(
            "Cannot create %s: %s duplicate groups remain (%s)",
            INDEX_NAME,
            groups,
            exc,
        )
        return False


def verify_index(cursor: sqlite3.Cursor) -> bool:
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
    logger.info("DB: %s (%s raw_signals, %s duplicate groups, %s rows to delete)",
                DB_PATH, total, dup_groups, to_delete)

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
