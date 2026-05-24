#!/usr/bin/env python3
"""Install Hermes cron launchers into ~/.hermes/scripts/ (Hermes rejects symlinks)."""

from __future__ import annotations

from pathlib import Path

HERMES_SCRIPTS = Path.home() / ".hermes" / "scripts"

JOBS = (
    ("ci_cron_daily_prod.py", "daily-prod"),
    ("ci_cron_grok_refresh.py", "grok-refresh"),
    ("ci_cron_frequent.py", "frequent"),
    ("ci_cron_edgar_weekly.py", "edgar-weekly"),
)

_LAUNCHER = '''#!/usr/bin/env python3
"""Hermes cron launcher — set COMPETITOR_INTEL_ROOT to the repo checkout."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    root = os.environ.get("COMPETITOR_INTEL_ROOT", "").strip()
    if not root:
        print(
            "COMPETITOR_INTEL_ROOT must point at the Competitor-Intel repo",
            file=sys.stderr,
        )
        return 1
    runner = os.path.join(root, "integrations", "hermes", "cron_runner.py")
    return subprocess.run(
        [sys.executable, runner, "{job}"],
        cwd=root,
        env=os.environ.copy(),
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
'''


def main() -> int:
    HERMES_SCRIPTS.mkdir(parents=True, exist_ok=True)
    for dest_name, job in JOBS:
        dest = HERMES_SCRIPTS / dest_name
        dest.write_text(_LAUNCHER.format(job=job), encoding="utf-8")
        dest.chmod(0o755)
        print(f"installed {dest}")
    print(
        "Note: set COMPETITOR_INTEL_ROOT in Hermes gateway env to your repo path.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
