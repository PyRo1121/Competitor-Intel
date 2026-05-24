#!/usr/bin/env python3
"""Single Hermes cron entry: subprocess worker scripts with shared bootstrap."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from monorepo_env import bootstrap_monorepo

JobEnv = Callable[[], dict[str, str]] | None


def _daily_prod_env() -> dict[str, str]:
    from env_presets import apply_daily_prod_env  # noqa: PLC0415

    return apply_daily_prod_env()


def _hermes_grok_disabled() -> bool:
    return os.environ.get("CI_DISABLE_HERMES", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ) or os.environ.get("CI_SKIP_GROK_X", "").strip().lower() in ("1", "true", "yes")


def _edgar_weekly_env() -> dict[str, str]:
    env = os.environ.copy()
    env["EDGAR_FORM_D_BULK"] = "1"
    return env


JOBS: dict[str, tuple[str, JobEnv, str]] = {
    "daily-prod": ("apps/worker/daily_intel.py", _daily_prod_env, "daily-prod"),
    "grok-refresh": ("apps/worker/grok_refresh.py", None, "grok-refresh"),
    "frequent": ("apps/worker/frequent_intel.py", None, "frequent"),
    "edgar-weekly": ("apps/worker/edgar_form_d_weekly.py", _edgar_weekly_env, "edgar-weekly"),
}


def run_job(name: str, *, root: Path | None = None) -> int:
    if name not in JOBS:
        raise ValueError(f"unknown cron job: {name}")
    script_rel, env_fn, label = JOBS[name]
    repo = root or bootstrap_monorepo()
    if name == "grok-refresh" and _hermes_grok_disabled():
        print(f"competitor-intel {label}: skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)")
        return 0
    env = env_fn() if env_fn else os.environ.copy()
    script = repo / script_rel
    result = subprocess.run([sys.executable, str(script)], cwd=repo, env=env)
    print(f"competitor-intel {label}: exit {result.returncode}")
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes cron runner for Competitor Intel")
    parser.add_argument("job", choices=sorted(JOBS))
    args = parser.parse_args(argv)
    return run_job(args.job)


if __name__ == "__main__":
    raise SystemExit(main())
