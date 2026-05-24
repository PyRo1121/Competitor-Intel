#!/usr/bin/env python3
"""Backward-compatible shim — use: uv run python -m collectors.grok_x_export export"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.grok_x_export import main_export

if __name__ == "__main__":
    raise SystemExit(main_export())
