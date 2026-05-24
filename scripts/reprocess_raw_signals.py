#!/usr/bin/env python3
"""Backward-compatible shim — use: uv run python -m db.reprocess"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from db.reprocess import main

if __name__ == "__main__":
    raise SystemExit(main())
