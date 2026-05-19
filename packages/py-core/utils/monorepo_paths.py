"""Monorepo root and default data paths for Competitor Intel."""

from __future__ import annotations

import os
from pathlib import Path

# packages/py-core/utils/monorepo_paths.py -> repo root
MONOREPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = MONOREPO_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "competitor_intel.db"
EXPORTS_DIR = DATA_DIR / "exports"
REPORTS_DIR = DATA_DIR / "reports"
OBSIDIAN_DATA_DIR = DATA_DIR / "obsidian"


def db_path() -> Path:
    """Resolve SQLite path from CI_DB_PATH or monorepo default."""
    raw = os.environ.get("CI_DB_PATH")
    if raw:
        return Path(raw)
    return DEFAULT_DB_PATH
