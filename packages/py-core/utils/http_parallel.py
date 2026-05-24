"""Parallel HTTP helpers for collectors (thread pool over sync httpx)."""

from __future__ import annotations

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def fetch_workers(default: int = 16, env_var: str = "CI_HTTP_FETCH_WORKERS") -> int:
    raw = os.environ.get(env_var, str(default)).strip()
    try:
        return max(1, min(64, int(raw)))
    except ValueError:
        return default


def parallel_map(
    fn: Callable[[T], R],
    items: list[T],
    *,
    workers: int | None = None,
    env_var: str = "CI_HTTP_FETCH_WORKERS",
) -> list[R]:
    """Run fn over items with a bounded thread pool (order preserved)."""
    if not items:
        return []
    max_workers = workers if workers is not None else fetch_workers(env_var=env_var)
    max_workers = min(max_workers, len(items))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(fn, items))
