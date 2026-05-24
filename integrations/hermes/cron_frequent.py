#!/usr/bin/env python3
"""Hermes cron (--no-agent): frequent RSS/open-web tier. See docs/SCHEDULING.md."""

from __future__ import annotations

import os
import subprocess
import sys

from monorepo_env import bootstrap_monorepo


def main() -> int:
    root = bootstrap_monorepo()
    script = root / "apps" / "worker" / "frequent_intel.py"
    result = subprocess.run([sys.executable, str(script)], cwd=root, env=os.environ.copy())
    print(f"competitor-intel frequent: exit {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
