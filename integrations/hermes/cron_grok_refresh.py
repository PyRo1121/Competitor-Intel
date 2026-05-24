#!/usr/bin/env python3
"""Hermes cron (--no-agent): Grok/X refresh batch. See docs/SCHEDULING.md."""

from __future__ import annotations

import os
import subprocess
import sys

from monorepo_env import bootstrap_monorepo


def _hermes_disabled() -> bool:
    return os.environ.get("CI_DISABLE_HERMES", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ) or os.environ.get("CI_SKIP_GROK_X", "").strip().lower() in ("1", "true", "yes")


def main() -> int:
    root = bootstrap_monorepo()
    if _hermes_disabled():
        print("competitor-intel grok-refresh: skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)")
        return 0
    script = root / "apps" / "worker" / "grok_refresh.py"
    result = subprocess.run([sys.executable, str(script)], cwd=root, env=os.environ.copy())
    print(f"competitor-intel grok-refresh: exit {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
