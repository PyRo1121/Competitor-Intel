"""
Centralized SQLite connection management (2026).

All Python code must use get_conn() / transaction() — never sqlite3.connect() directly
except tests that intentionally bypass pragmas.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ci_paths import db_path

from db.sqlite_tuning import (
    ProfileName,
    apply_profile,
    busy_timeout_ms,
    run_optimize_on_close,
)

DEFAULT_TIMEOUT = 60.0

_test_db_override: Path | None = None
_runtime_migrations_applied: set[str] = set()


def active_db_path() -> Path:
    """Resolved DB path (honours CI_DB_PATH and optional test override)."""
    if _test_db_override is not None:
        return _test_db_override
    return db_path()


def __getattr__(name: str):
    if name == "DB_PATH":
        return active_db_path()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def configure_connection(
    conn: sqlite3.Connection,
    profile: ProfileName = "default",
) -> dict[str, str]:
    """Apply enterprise PRAGMA profile. Prefer get_conn(profile=...) instead."""
    return apply_profile(conn, profile)


def get_conn(
    timeout: float = DEFAULT_TIMEOUT,
    *,
    profile: ProfileName = "default",
) -> sqlite3.Connection:
    """
    Configured SQLite connection.

    Profiles:
    - default: collectors, workers, CLI
    - ingest_bulk: long sequential ingest (EDGAR bulk, staging merge)
    - api_read: SELECT-only API handlers (query_only=ON)
    - maintenance: migrations, dedupe (EXCLUSIVE locking_mode)
    """
    conn = sqlite3.connect(str(active_db_path()), timeout=timeout)
    conn.row_factory = sqlite3.Row
    apply_profile(conn, profile)
    return conn


def get_read_conn(timeout: float = DEFAULT_TIMEOUT) -> sqlite3.Connection:
    """Read-optimized connection (query_only when supported)."""
    return get_conn(timeout=timeout, profile="api_read")


def ensure_runtime_migrations(conn: sqlite3.Connection) -> None:
    """Apply additive schema once per DB path (cap_table_holdings, claim tables, etc.)."""
    key = str(active_db_path().resolve())
    if key in _runtime_migrations_applied:
        return
    from db.migrations import apply_runtime_migrations
    from db.sqlite_retry import retry_locked

    def _run() -> None:
        apply_runtime_migrations(conn)

    retry_locked(_run, max_retries=30)
    _runtime_migrations_applied.add(key)


@contextmanager
def transaction(
    timeout: float = DEFAULT_TIMEOUT,
    *,
    profile: ProfileName = "default",
    immediate: bool = False,
) -> Iterator[sqlite3.Connection]:
    """
    Connection with automatic commit/rollback.

    immediate=True uses BEGIN IMMEDIATE for write-heavy sections (reduces SQLITE_BUSY).
    """
    conn = get_conn(timeout=timeout, profile=profile)
    try:
        ensure_runtime_migrations(conn)
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        run_optimize_on_close(conn)
        conn.close()


@contextmanager
def get_cursor(
    timeout: float = DEFAULT_TIMEOUT,
    *,
    profile: ProfileName = "default",
) -> Iterator[sqlite3.Cursor]:
    """Cursor with automatic commit on success."""
    conn = get_conn(timeout=timeout, profile=profile)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        run_optimize_on_close(conn)
        conn.close()


def connection_info() -> dict[str, str]:
    """Lightweight health snapshot for operators."""
    conn = get_conn(profile="default")
    try:
        from db.sqlite_tuning import read_pragma_snapshot, wal_status

        info = read_pragma_snapshot(conn)
        info.update(wal_status(conn))
        info["path"] = str(active_db_path())
        info["busy_timeout_ms"] = str(busy_timeout_ms())
        wal = Path(f"{active_db_path()}-wal")
        if wal.is_file():
            info["wal_bytes"] = str(wal.stat().st_size)
        return info
    finally:
        conn.close()
