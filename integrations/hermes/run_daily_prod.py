#!/usr/bin/env python3
"""Deprecated: use integrations/hermes/call_intel.sh daily or make daily-prod (6-H05)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
os.environ.setdefault("CI_DB_PATH", str(ROOT / "data" / "competitor_intel.db"))

sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))

from ci_paths import ensure_app_paths  # noqa: E402

ensure_app_paths()

from daily_intel import main  # noqa: E402

if __name__ == "__main__":
    print(
        "WARNING: run_daily_prod.py is deprecated — use call_intel.sh daily or make daily-prod",
        file=sys.stderr,
    )
    raise SystemExit(main())
