"""SQLite busy/locked retry with exponential backoff + jitter."""

from __future__ import annotations

import os
import random
import sqlite3
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

_DEFAULT_RETRIES = 16
_DEFAULT_BASE_SEC = 0.05
_DEFAULT_CAP_SEC = 2.0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def is_locked_error(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        return "locked" in msg or "busy" in msg
    return False


def retry_locked(
    fn: Callable[[], T],
    *,
    max_retries: int | None = None,
    base_delay_sec: float | None = None,
    cap_delay_sec: float | None = None,
    jitter: bool = True,
) -> T:
    """
    Retry on SQLITE_BUSY / database is locked with exponential backoff + jitter.

    Pairs with PRAGMA busy_timeout (connection-level wait) and writer_lock (process-level).
    """
    retries = (
        max_retries
        if max_retries is not None
        else _env_int("CI_SQLITE_LOCK_RETRIES", _DEFAULT_RETRIES)
    )
    base = (
        base_delay_sec
        if base_delay_sec is not None
        else _env_float("CI_SQLITE_RETRY_BASE_SEC", _DEFAULT_BASE_SEC)
    )
    cap = (
        cap_delay_sec
        if cap_delay_sec is not None
        else _env_float("CI_SQLITE_RETRY_CAP_SEC", _DEFAULT_CAP_SEC)
    )
    delay = base
    last: BaseException | None = None

    for attempt in range(retries):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if not is_locked_error(exc) or attempt >= retries - 1:
                raise
            last = exc
            sleep_for = min(delay, cap)
            if jitter:
                sleep_for *= 0.5 + random.random()
            time.sleep(sleep_for)
            delay = min(delay * 2.0, cap)
    if last:
        raise last
    raise RuntimeError("retry_locked: unreachable")
