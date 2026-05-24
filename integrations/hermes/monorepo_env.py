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
    py_core = str(root / "packages" / "py-core")
    if py_core not in sys.path:
        sys.path.insert(0, py_core)
    from ci_paths import bootstrap_external_runner  # noqa: PLC0415

    os.environ.setdefault("COMPETITOR_INTEL_ROOT", str(root))
    return bootstrap_external_runner()
