#!/usr/bin/env python3
"""Copy Hermes cron entrypoints into ~/.hermes/scripts/ (Hermes rejects symlinks)."""

from __future__ import annotations

import shutil
from pathlib import Path

HERMES_SCRIPTS = Path.home() / ".hermes" / "scripts"
SOURCE_DIR = Path(__file__).resolve().parent
FILES = (
    ("ci_cron_daily_prod.py", "cron_daily_prod.py"),
    ("ci_cron_grok_refresh.py", "cron_grok_refresh.py"),
    ("ci_cron_frequent.py", "cron_frequent.py"),
    ("ci_cron_edgar_weekly.py", "cron_edgar_weekly.py"),
)


def main() -> int:
    HERMES_SCRIPTS.mkdir(parents=True, exist_ok=True)
    for dest_name, src_name in FILES:
        dest = HERMES_SCRIPTS / dest_name
        shutil.copy2(SOURCE_DIR / src_name, dest)
        print(f"installed {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
