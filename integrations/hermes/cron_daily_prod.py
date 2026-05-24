#!/usr/bin/env python3
"""Hermes cron (--no-agent): production daily pipeline. See docs/SCHEDULING.md."""

from __future__ import annotations

import os
import subprocess
import sys

from monorepo_env import bootstrap_monorepo


def main() -> int:
    root = bootstrap_monorepo()
    env = os.environ.copy()
    env["CI_SKIP_GROK_X"] = "1"
    env["CI_STRICT_PIPELINE"] = "1"
    env["CI_REQUIRE_DEDUP_INDEX"] = "1"
    script = root / "apps" / "worker" / "daily_intel.py"
    result = subprocess.run([sys.executable, str(script)], cwd=root, env=env)
    print(f"competitor-intel daily-prod: exit {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
