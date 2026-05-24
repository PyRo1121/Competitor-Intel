"""SQLite lock contention helpers."""

from __future__ import annotations

import sqlite3
import threading

from db.connection import configure_connection, get_conn, transaction
from db.ingest import insert_raw_signal_dedup


def test_configure_connection_sets_busy_timeout(operational_db):
    conn = sqlite3.connect(operational_db, timeout=60)
    configure_connection(conn)
    busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    conn.close()
    assert int(busy) >= 1000


def test_insert_raw_signal_dedup_parallel_connections(operational_db):
    """Simulate parallel collector processes (separate connections per thread)."""
    errors: list[BaseException] = []

    def writer(idx: int) -> None:
        try:
            with transaction(immediate=True) as conn:
                cur = conn.cursor()
                for i in range(10):
                    insert_raw_signal_dedup(
                        cur,
                        "parallel_test",
                        f"https://example.com/parallel-{idx}-{i}",
                        {"title": f"story {idx}-{i}"},
                    )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=120)
    assert not errors, errors
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE source = 'parallel_test'").fetchone()[
        0
    ]
    conn.close()
    assert n == 40
