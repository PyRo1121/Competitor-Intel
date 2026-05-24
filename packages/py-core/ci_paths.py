"""Monorepo root and default data paths for Competitor Intel."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# packages/py-core/ci_paths.py -> repo root
MONOREPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = MONOREPO_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "competitor_intel.db"
EXPORTS_DIR = DATA_DIR / "exports"
REPORTS_DIR = DATA_DIR / "reports"
OBSIDIAN_DATA_DIR = DATA_DIR / "obsidian"
CONFIG_DIR = MONOREPO_ROOT / "packages" / "py-core" / "config"


def db_path() -> Path:
    """Resolve SQLite path from CI_DB_PATH or monorepo default."""
    raw = os.environ.get("CI_DB_PATH")
    if raw:
        return Path(raw)
    return DEFAULT_DB_PATH


def bootstrap_external_runner(*, load_dotenv: bool = True, mkdir_logs: bool = True) -> Path:
    """
    Hermes/cron bootstrap: chdir to monorepo, optional .env, default CI_DB_PATH, import paths.
    """
    import os

    os.chdir(MONOREPO_ROOT)
    if load_dotenv:
        env_file = MONOREPO_ROOT / ".env"
        if env_file.is_file():
            from dotenv import load_dotenv as _load

            _load(env_file)
    os.environ.setdefault("CI_DB_PATH", str(DEFAULT_DB_PATH))
    for sub in ("packages/py-core", "packages/py-collectors", "apps/worker", "apps/cli"):
        path = str(MONOREPO_ROOT / sub)
        if path not in sys.path:
            sys.path.insert(0, path)
    if mkdir_logs:
        (MONOREPO_ROOT / "logs").mkdir(exist_ok=True)
    return MONOREPO_ROOT


def ensure_app_paths() -> None:
    """Ensure worker/cli script dirs are importable when run via `uv run python ...`."""
    bootstrap_external_runner(load_dotenv=False, mkdir_logs=False)
