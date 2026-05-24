"""Test fixtures and configuration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from competitor_intel.db.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
PY_CORE = ROOT / "packages" / "py-core"
PY_COLLECTORS = ROOT / "packages" / "py-collectors"

for path in (PY_CORE, PY_COLLECTORS):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


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


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine."""
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="session")
def tables(engine):
    """Create all tables."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    """Create a test database session."""
    connection = engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
