"""Monorepo bootstrap for Hermes cron scripts and call_intel."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def monorepo_root() -> Path:
    raw = os.environ.get("COMPETITOR_INTEL_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def bootstrap_monorepo() -> Path:
    root = monorepo_root()
    os.chdir(root)
    env_file = root / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file)
    os.environ.setdefault("CI_DB_PATH", str(root / "data" / "competitor_intel.db"))
    for sub in (
        "packages/py-core",
        "packages/py-collectors",
        "apps/worker",
        "apps/cli",
    ):
        path = str(root / sub)
        if path not in sys.path:
            sys.path.insert(0, path)
    (root / "logs").mkdir(exist_ok=True)
    return root
