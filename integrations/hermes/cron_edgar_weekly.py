#!/usr/bin/env python3
"""Hermes cron (--no-agent): weekly SEC Form D bulk ingest. See docs/SCHEDULING.md."""

from __future__ import annotations

import os
import subprocess
import sys

from monorepo_env import bootstrap_monorepo


def main() -> int:
    root = bootstrap_monorepo()
    env = os.environ.copy()
    env["EDGAR_FORM_D_BULK"] = "1"
    script = root / "apps" / "worker" / "edgar_form_d_weekly.py"
    result = subprocess.run([sys.executable, str(script)], cwd=root, env=env)
    print(f"competitor-intel edgar-form-d-weekly: exit {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
