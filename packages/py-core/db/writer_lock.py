"""
Cross-process SQLite writer serialization.

SQLite WAL allows one writer at a time. Parallel collector subprocesses each open
their own connection; without coordination they hit SQLITE_BUSY / "database is locked".

When CI_SQLITE_WRITER_LOCK=1 (default), all write paths acquire a POSIX flock on
<db>.write.lock so writes serialize but HTTP fetch stays parallel.
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from db.connection import active_db_path


def _writer_lock_enabled() -> bool:
    return os.environ.get("CI_SQLITE_WRITER_LOCK", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def lock_path(db_path: Path | None = None) -> Path:
    path = db_path or active_db_path()
    return path.with_suffix(path.suffix + ".write.lock")


def _lock_timeout_sec() -> float:
    raw = os.environ.get("CI_SQLITE_WRITER_LOCK_TIMEOUT_SEC", "300").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 300.0


@contextmanager
def writer_lock(db_path: Path | None = None) -> Iterator[None]:
    """
    Exclusive flock for DB write sections across processes.

    No-op when CI_SQLITE_WRITER_LOCK=0 (expert / single-writer staging ingest only).
    """
    if not _writer_lock_enabled():
        yield
        return

    path = lock_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + _lock_timeout_sec()
    with open(path, "a+", encoding="utf-8") as fh:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for SQLite writer lock ({path})"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            with suppress(OSError):
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
