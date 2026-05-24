"""
SQLite tuning profiles — single source of truth for PRAGMA configuration.

References:
- https://sqlite.org/wal.html
- https://sqlite.org/pragma.html
- https://phiresky.github.io/blog/2020/sqlite-performance-tuning/

Throughput notes (local SSD, WAL + batch transactions):
- Tens of thousands of simple INSERTs/sec in one process with executemany + periodic commit
- Many processes writing concurrently still serialize at SQLite layer; use writer_lock or staging
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
from dataclasses import dataclass
from typing import Literal

ProfileName = Literal["default", "ingest_bulk", "api_read", "maintenance"]

# Negative cache_size = KiB pages in cache (see sqlite.org/pragma.html#pragma_cache_size)
DEFAULT_CACHE_KIB = -512_000  # ~512 MiB
DEFAULT_MMAP_BYTES = 536_870_912  # 512 MiB
DEFAULT_BUSY_TIMEOUT_MS = 120_000
DEFAULT_WAL_AUTOCHECKPOINT = 10_000  # pages
DEFAULT_INGEST_WAL_AUTOCHECKPOINT = 5_000  # shorter WAL during bulk (checkpoint starvation guard)
OPTIMIZE_ON_OPEN_MASK = 0x10002  # 0x10000 all tables + 0x00002 analyze (SQLite 3.46+)


@dataclass(frozen=True)
class SqliteProfile:
    name: ProfileName
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    foreign_keys: bool = True
    cache_size_kib: int = DEFAULT_CACHE_KIB
    mmap_size: int = DEFAULT_MMAP_BYTES
    temp_store: str = "MEMORY"
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS
    wal_autocheckpoint: int = DEFAULT_WAL_AUTOCHECKPOINT
    journal_size_limit: int | None = 64_000_000
    query_only: bool = False
    locking_mode: str | None = None  # NORMAL | EXCLUSIVE (maintenance)


PROFILES: dict[ProfileName, SqliteProfile] = {
    "default": SqliteProfile(name="default"),
    "ingest_bulk": SqliteProfile(
        name="ingest_bulk",
        synchronous="NORMAL",
        cache_size_kib=-512_000,
        mmap_size=536_870_912,
        wal_autocheckpoint=DEFAULT_INGEST_WAL_AUTOCHECKPOINT,
    ),
    "api_read": SqliteProfile(
        name="api_read",
        query_only=True,
        synchronous="NORMAL",
        wal_autocheckpoint=0,
    ),
    "maintenance": SqliteProfile(
        name="maintenance",
        synchronous="FULL",
        locking_mode="EXCLUSIVE",
        journal_size_limit=None,
    ),
}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def busy_timeout_ms() -> int:
    return _env_int("CI_SQLITE_BUSY_TIMEOUT_MS", DEFAULT_BUSY_TIMEOUT_MS)


def profile(name: ProfileName = "default") -> SqliteProfile:
    base = PROFILES[name]
    return SqliteProfile(
        name=base.name,
        journal_mode=base.journal_mode,
        synchronous=base.synchronous,
        foreign_keys=base.foreign_keys,
        cache_size_kib=_env_int("CI_SQLITE_CACHE_KIB", base.cache_size_kib),
        mmap_size=_env_int("CI_SQLITE_MMAP_BYTES", base.mmap_size),
        temp_store=base.temp_store,
        busy_timeout_ms=busy_timeout_ms(),
        wal_autocheckpoint=_env_int("CI_SQLITE_WAL_AUTOCHECKPOINT", base.wal_autocheckpoint),
        journal_size_limit=base.journal_size_limit,
        query_only=base.query_only,
        locking_mode=base.locking_mode,
    )


def apply_profile(conn: sqlite3.Connection, name: ProfileName = "default") -> dict[str, str]:
    """Apply PRAGMA profile; return resolved journal_mode and key settings."""
    p = profile(name)
    resolved: dict[str, str] = {"profile": name}

    jm = conn.execute(f"PRAGMA journal_mode = {p.journal_mode}").fetchone()
    resolved["journal_mode"] = str(jm[0]) if jm else p.journal_mode

    conn.execute(f"PRAGMA synchronous = {p.synchronous}")
    resolved["synchronous"] = p.synchronous

    conn.execute(f"PRAGMA foreign_keys = {'ON' if p.foreign_keys else 'OFF'}")
    conn.execute(f"PRAGMA cache_size = {p.cache_size_kib}")
    conn.execute(f"PRAGMA temp_store = {p.temp_store}")
    conn.execute(f"PRAGMA mmap_size = {p.mmap_size}")
    conn.execute(f"PRAGMA busy_timeout = {p.busy_timeout_ms}")
    resolved["busy_timeout_ms"] = str(p.busy_timeout_ms)

    if p.wal_autocheckpoint:
        conn.execute(f"PRAGMA wal_autocheckpoint = {p.wal_autocheckpoint}")
    if p.journal_size_limit is not None:
        conn.execute(f"PRAGMA journal_size_limit = {p.journal_size_limit}")
    if p.locking_mode:
        conn.execute(f"PRAGMA locking_mode = {p.locking_mode}")
    if p.query_only:
        conn.execute("PRAGMA query_only = ON")

    if name in ("default", "api_read"):
        run_optimize_on_open(conn)

    return resolved


def run_optimize_on_open(conn: sqlite3.Connection) -> None:
    """SQLite 3.46+ — warm planner stats on long-lived connections (see pragma optimize)."""
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute(f"PRAGMA optimize = {OPTIMIZE_ON_OPEN_MASK}")


def run_optimize_on_close(conn: sqlite3.Connection) -> None:
    """Run before closing long-lived writer connections."""
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("PRAGMA optimize")


def read_pragma_snapshot(conn: sqlite3.Connection) -> dict[str, str]:
    """Introspect effective connection settings (for health checks)."""
    keys = (
        "journal_mode",
        "synchronous",
        "foreign_keys",
        "cache_size",
        "mmap_size",
        "busy_timeout",
        "wal_autocheckpoint",
        "page_size",
        "page_count",
        "freelist_count",
        "locking_mode",
    )
    out: dict[str, str] = {}
    for key in keys:
        row = conn.execute(f"PRAGMA {key}").fetchone()
        if row:
            out[key] = str(row[0])
    with contextlib.suppress(sqlite3.OperationalError):
        out["data_version"] = str(conn.execute("PRAGMA data_version").fetchone()[0])
    return out


def wal_status(conn: sqlite3.Connection) -> dict[str, str]:
    """Passive WAL checkpoint stats: (busy, log_frames, checkpointed_frames)."""
    row = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
    if not row:
        return {}
    return {
        "wal_checkpoint_busy": str(row[0]),
        "wal_log_frames": str(row[1]),
        "wal_checkpointed_frames": str(row[2]),
    }


def wal_checkpoint(
    conn: sqlite3.Connection,
    mode: str = "PASSIVE",
) -> tuple[str, int, int]:
    """Run WAL checkpoint (TRUNCATE|PASSIVE|RESTART|FULL). Returns (mode, log, ckpt)."""
    row = conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
    if not row:
        return mode, -1, -1
    return mode, int(row[1]), int(row[2])


def post_ingest_wal_maintenance(
    mode: str = "RESTART",
) -> dict[str, str]:
    """
    After large daily ingest: checkpoint WAL + optimize planner stats.

    Call from daily_intel when pipeline succeeds. RESTART is a good default
    (shrinks WAL without requiring quiescent readers like TRUNCATE).
    """
    from db.connection import get_conn

    conn = get_conn(profile="ingest_bulk")
    try:
        ck_mode, log_frames, ckpt_frames = wal_checkpoint(conn, mode)
        conn.commit()
        run_optimize_on_close(conn)
        return {
            "checkpoint_mode": ck_mode,
            "wal_log_frames": str(log_frames),
            "wal_checkpointed_frames": str(ckpt_frames),
        }
    finally:
        conn.close()
