#!/usr/bin/env python3
"""Dispatch X fetch to xurl or Grok based on CI_X_PROVIDER (default: grok)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    provider = os.environ.get("CI_X_PROVIDER", "grok").strip().lower()
    if provider not in ("xurl", "grok"):
        print(f"Invalid CI_X_PROVIDER={provider!r} (use xurl or grok)", file=sys.stderr)
        return 1

    script = "fetch_xurl.py" if provider == "xurl" else "fetch_grok_x.py"
    cmd = [sys.executable, str(ROOT / "scripts" / script), *sys.argv[1:]]
    print(f"CI_X_PROVIDER={provider} → {script}", file=sys.stderr)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
