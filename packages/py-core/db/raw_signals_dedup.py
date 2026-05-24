"""raw_signals (source, signal_type) dedupe index and optional row cleanup."""

from __future__ import annotations

import logging
import os
import sqlite3

logger = logging.getLogger("db.raw_signals_dedup")

INDEX_NAME = "idx_raw_signals_dedup"
DEDUP_INDEX_DDL = f"CREATE UNIQUE INDEX {INDEX_NAME} ON raw_signals(source, signal_type)"


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


def ensure_raw_signals_dedup_index(conn: sqlite3.Connection) -> None:
    """Ensure UNIQUE(source, signal_type) on raw_signals; fail loud in prod modes."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (INDEX_NAME,),
    )
    if cursor.fetchone():
        return
    try:
        conn.execute(DEDUP_INDEX_DDL)
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        msg = (
            f"Cannot create {INDEX_NAME}: duplicate (source, signal_type) rows. "
            "Run: make migrate-dedup"
        )
        strict = os.environ.get("CI_STRICT_PIPELINE", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        require = os.environ.get("CI_REQUIRE_DEDUP_INDEX", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if strict or require:
            raise RuntimeError(msg) from exc
        logger.warning("Skipped %s: %s", INDEX_NAME, exc)


def ensure_dedup_index(conn: sqlite3.Connection) -> bool:
    """CLI-oriented ensure; returns False if duplicates block index creation."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
        (INDEX_NAME,),
    )
    if cursor.fetchone():
        logger.info("Index %s already exists", INDEX_NAME)
        return True
    try:
        conn.execute(DEDUP_INDEX_DDL)
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
