#!/usr/bin/env python3
"""Backward-compatible shim — use: uv run python tests/integration/smoke_hermes_x_pipeline.py"""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    target = (
        Path(__file__).resolve().parents[1] / "tests" / "integration" / "smoke_hermes_x_pipeline.py"
    )
    runpy.run_path(str(target), run_name="__main__")
