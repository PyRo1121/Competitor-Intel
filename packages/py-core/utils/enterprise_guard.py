"""Guardrails for py-enterprise shadow runs (Track 4 P4-2 / X-11)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ci_paths import DEFAULT_DB_PATH, db_path


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def resolve_operational_db() -> Path:
    return db_path().resolve()


def is_default_prod_sqlite(path: Path | None = None) -> bool:
    """True when CI_DB_PATH unset or points at the canonical prod SQLite file."""
    target = (path or resolve_operational_db()).resolve()
    return target == DEFAULT_DB_PATH.resolve()


def assert_enterprise_sqlite_safe(*, context: str = "enterprise collect") -> None:
    """
    Block enterprise SQLAlchemy collectors against the default prod SQLite unless
    CI_ENTERPRISE_ALLOW_PROD=1 (operator override).
    """
    if not is_default_prod_sqlite():
        return
    if _truthy("CI_ENTERPRISE_ALLOW_PROD"):
        return
    target = resolve_operational_db()
    msg = (
        f"{context}: refused to run against default prod SQLite ({target}). "
        "Set CI_DB_PATH to a copy, use make enterprise-rss (dry-run), or set "
        "CI_ENTERPRISE_ALLOW_PROD=1 to override."
    )
    print(msg, file=sys.stderr)
    raise SystemExit(1)
