"""
World-Class Centralized Database Connection Management (2026 Standards)

This module provides the single source of truth for all SQLite access
in the Competitor Intelligence system.

Design goals:
- One database file (competitor_intel.db) for everything
- Consistent, safe connection handling
- Ready for vector embeddings + RAG workloads
- Type-safe, documented, and testable
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from ci_paths import db_path

DB_PATH = db_path()

DEFAULT_TIMEOUT = 30.0


def get_conn(timeout: float = DEFAULT_TIMEOUT) -> sqlite3.Connection:
    """
    Return a properly configured SQLite connection.

    All connections in the system should come from here.
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # ~64MB cache
    return conn


@contextmanager
def transaction(timeout: float = DEFAULT_TIMEOUT) -> Iterator[sqlite3.Connection]:
    """
    Context manager that provides a connection with automatic commit/rollback.
    """
    conn = get_conn(timeout=timeout)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(timeout: float = DEFAULT_TIMEOUT) -> Iterator[sqlite3.Cursor]:
    """
    Convenience context manager that yields a cursor and handles cleanup.
    """
    conn = get_conn(timeout=timeout)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
