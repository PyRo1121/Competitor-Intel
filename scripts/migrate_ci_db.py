#!/usr/bin/env python3
"""Apply runtime migrations to CI_DB_PATH (API tests, e2e seed)."""

from __future__ import annotations

import sqlite3

from db.connection import active_db_path, transaction
from db.migrations import apply_runtime_migrations
from db.schema import init_database


def main() -> None:
    path = active_db_path()
    conn_probe = sqlite3.connect(str(path))
    try:
        has_companies = (
            conn_probe.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='companies'"
            ).fetchone()
            is not None
        )
    finally:
        conn_probe.close()
    if not has_companies:
        init_database()
    with transaction() as conn:
        apply_runtime_migrations(conn)


if __name__ == "__main__":
    main()
