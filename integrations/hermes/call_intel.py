#!/usr/bin/env python3
"""
Hermes → Competitor Intel entrypoint (Python; no shell shim).

Usage:
  uv run python integrations/hermes/call_intel.py daily-prod
  uv run python integrations/hermes/call_intel.py grok-refresh
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from monorepo_env import bootstrap_monorepo


def _hermes_disabled() -> bool:
    return os.environ.get("CI_DISABLE_HERMES", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ) or os.environ.get("CI_SKIP_GROK_X", "").strip().lower() in ("1", "true", "yes")


def _run(root: Path, script: str, *args: str, env: dict[str, str] | None = None) -> int:
    cmd = [sys.executable, str(root / script), *args]
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, cwd=root, env=merged).returncode


def _run_make(root: Path, target: str) -> int:
    return subprocess.run(["make", target], cwd=root, env=os.environ.copy()).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes Competitor Intel bridge")
    parser.add_argument(
        "mode",
        choices=(
            "status",
            "daily",
            "daily-prod",
            "frequent",
            "grok-refresh",
            "full-sweep",
            "grok-x-ingest",
            "intel",
            "cli",
            "companies",
            "grok-x",
            "grok-x-fetch",
            "x-fetch",
            "x-check",
            "export-x-queries",
            "edgar-weekly",
        ),
    )
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    root = bootstrap_monorepo()
    mode = args.mode.replace("_", "-")
    rest = args.rest

    if mode == "status":
        return _run(root, "apps/cli/intel.py", "status")
    if mode == "daily":
        return _run(
            root,
            "apps/worker/daily_intel.py",
            env={"CI_SKIP_GROK_X": "1"},
        )
    if mode in ("daily-prod", "frequent", "grok-refresh", "edgar-weekly"):
        from cron_runner import run_job  # noqa: PLC0415

        return run_job(mode, root=root)
    if mode == "full-sweep":
        return _run_make(root, "full-sweep")
    if mode == "grok-x-ingest":
        return _run_make(root, "grok-x-ingest")
    if mode == "intel":
        return _run(root, "apps/cli/run_intel.py", *rest)
    if mode == "cli":
        return _run(root, "apps/cli/intel.py", *rest)
    if mode == "companies":
        limit = rest[0] if rest else "20"
        return _run(root, "apps/cli/intel.py", "companies", "--limit", limit)
    if mode == "grok-x":
        if _hermes_disabled():
            print("Hermes/Grok skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)", file=sys.stderr)
            return 0
        return _run(root, "integrations/hermes/ingest_grok_x.py", *rest)
    if mode == "grok-x-fetch":
        if _hermes_disabled():
            print("Hermes/Grok skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)", file=sys.stderr)
            return 0
        return _run(root, "apps/worker/x_refresh/fetch.py", *rest)
    if mode == "x-fetch":
        return _run(root, "apps/worker/x_refresh/fetch_xurl.py", *rest)
    if mode == "x-check":
        return _run(root, "apps/worker/x_refresh/fetch_xurl.py", "--check")
    if mode == "export-x-queries":
        cmd = [sys.executable, "-m", "collectors.grok_x_export", "export", *rest]
        merged = os.environ.copy()
        py = str(root / "packages" / "py-collectors")
        merged["PYTHONPATH"] = (
            py if not merged.get("PYTHONPATH") else f"{py}{os.pathsep}{merged['PYTHONPATH']}"
        )
        return subprocess.run(cmd, cwd=root, env=merged).returncode
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
