#!/usr/bin/env python3
"""Backward-compatible shim — use: signal_repair actionable subcommand."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))

from collectors.signal_repair import main

if __name__ == "__main__":
    raise SystemExit(main(["actionable"]))
