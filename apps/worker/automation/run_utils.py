"""Shared subprocess runner + timing helpers for automation scripts."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

from automation.collector_registry import BASE

LOG_FORMAT = "%(levelname)s: %(message)s"


def configure_logging(logger: logging.Logger, level: int = logging.INFO) -> None:
    if not logger.handlers:
        logging.basicConfig(level=level, format=LOG_FORMAT)


def run_script(
    script: str,
    *args: str,
    cwd: Path | None = None,
    logger: logging.Logger | None = None,
) -> tuple[bool, float]:
    """Run a project script; return (success, elapsed_seconds)."""
    log = logger or logging.getLogger("automation")
    root = cwd or BASE
    cmd = [sys.executable, str(root / script), *args]
    started = time.perf_counter()
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=root)
    elapsed = time.perf_counter() - started
    ok = result.returncode == 0
    if ok:
        log.info("Finished %s in %.1fs", script, elapsed)
    else:
        log.error("Script failed: %s (exit %s, %.1fs)", script, result.returncode, elapsed)
    return ok, elapsed


def log_timings(logger: logging.Logger, timings: list[tuple[str, float]], top_n: int = 8) -> None:
    if not timings:
        return
    logger.info("Slowest steps:")
    for script, elapsed in sorted(timings, key=lambda item: item[1], reverse=True)[:top_n]:
        logger.info("  %.1fs  %s", elapsed, script)
