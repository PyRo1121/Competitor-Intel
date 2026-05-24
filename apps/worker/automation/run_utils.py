"""Shared subprocess runner + timing helpers for automation scripts."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from automation.collector_registry import BASE

LOG_FORMAT = "%(levelname)s: %(message)s"


def configure_logging(logger: logging.Logger, level: int = logging.INFO) -> None:
    if not logger.handlers:
        logging.basicConfig(level=level, format=LOG_FORMAT)


def log_pipeline_step(
    step_id: str,
    script: str,
    ok: bool,
    elapsed_s: float,
    *,
    logger: logging.Logger | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    """Structured one-line JSON for log aggregators (Track 4 P4-4)."""
    log = logger or logging.getLogger("automation")
    payload: dict[str, object] = {
        "event": "pipeline_step",
        "step_id": step_id,
        "script": script,
        "ok": ok,
        "elapsed_ms": round(elapsed_s * 1000, 1),
    }
    if extra:
        payload.update(extra)
    log.info("%s", json.dumps(payload, default=str))


def subprocess_env(cwd: Path) -> dict[str, str]:
    """Ensure child scripts can import automation.*, db.*, and collectors.*."""
    env = os.environ.copy()
    paths = [
        str(cwd / "apps" / "worker"),
        str(cwd / "packages" / "py-core"),
        str(cwd / "packages" / "py-collectors"),
    ]
    existing = env.get("PYTHONPATH", "")
    prefix = os.pathsep.join(paths)
    env["PYTHONPATH"] = prefix if not existing else f"{prefix}{os.pathsep}{existing}"
    return env


def run_script(
    script: str,
    *args: str,
    cwd: Path | None = None,
    logger: logging.Logger | None = None,
    step_id: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[bool, float]:
    """Run a project script; return (success, elapsed_seconds)."""
    log = logger or logging.getLogger("automation")
    sid = step_id or script
    if os.environ.get("CI_DAILY_DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        log.info("DRY-RUN skip: %s %s", script, " ".join(args))
        log_pipeline_step(sid, script, True, 0.0, logger=log, extra={"dry_run": True})
        return True, 0.0
    root = cwd or BASE
    cmd = [sys.executable, str(root / script), *args]
    started = time.perf_counter()
    log.info("Running: %s", " ".join(cmd))
    env = subprocess_env(root)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(cmd, cwd=root, env=env)
    elapsed = time.perf_counter() - started
    ok = result.returncode == 0
    if ok:
        log.info("Finished %s in %.1fs", script, elapsed)
    else:
        log.error("Script failed: %s (exit %s, %.1fs)", script, result.returncode, elapsed)
    log_pipeline_step(
        sid,
        script,
        ok,
        elapsed,
        logger=log,
        extra={"exit_code": result.returncode},
    )
    return ok, elapsed


def log_timings(logger: logging.Logger, timings: list[tuple[str, float]], top_n: int = 8) -> None:
    if not timings:
        return
    logger.info("Slowest steps:")
    for script, elapsed in sorted(timings, key=lambda item: item[1], reverse=True)[:top_n]:
        logger.info("  %.1fs  %s", elapsed, script)
