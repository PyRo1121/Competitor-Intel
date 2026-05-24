"""Test fixtures and configuration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PY_CORE = ROOT / "packages" / "py-core"
PY_COLLECTORS = ROOT / "packages" / "py-collectors"
WORKER = ROOT / "apps" / "worker"

for path in (ROOT, PY_CORE, PY_COLLECTORS, WORKER):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture(autouse=True)
def _isolate_staging_env(monkeypatch):
    """Prevent CI_INGEST_STAGING leakage across tests (order-dependent failures)."""
    monkeypatch.delenv("CI_INGEST_STAGING", raising=False)
    monkeypatch.delenv("CI_STAGING_RUN_ID", raising=False)
    monkeypatch.delenv("CI_STAGING_SLOT", raising=False)


@pytest.fixture()
def operational_db(monkeypatch, tmp_path):
    """Isolated SQLite DB with full operational schema (WAL, migrations)."""
    db_file = tmp_path / "operational_test.db"
    monkeypatch.setenv("CI_DB_PATH", str(db_file))
    from db import connection as db_connection
    from db.schema import init_database

    db_connection._test_db_override = db_file
    init_database()

    try:
        from collectors import signal_processor as sp

        sp._aliases_loaded = False
        sp.COMPANY_ALIASES.clear()
    except ImportError:
        pass

    yield db_file
    db_connection._test_db_override = None
