"""Enterprise SQLite layer: tuning, writer lock, batch writer, INSERT OR IGNORE."""

from __future__ import annotations

import sqlite3
import threading

from db.batch import RawSignalBatchWriter
from db.ingest import insert_raw_signal_dedup
from db.sqlite_tuning import apply_profile, profile
from db.writer_lock import lock_path, writer_lock


def test_profiles_defined():
    assert profile("default").journal_mode == "WAL"
    assert abs(profile("ingest_bulk").cache_size_kib) >= abs(profile("default").cache_size_kib)


def test_apply_profile_wal(operational_db):
    conn = sqlite3.connect(operational_db, timeout=60)
    resolved = apply_profile(conn, "default")
    assert resolved["journal_mode"].lower() == "wal"
    conn.close()


def test_insert_or_ignore_dedup(operational_db):
    conn = sqlite3.connect(operational_db, timeout=60)
    apply_profile(conn, "default")
    cur = conn.cursor()
    first = insert_raw_signal_dedup(
        cur,
        "test_src",
        "https://example.com/dedup-1",
        {"title": "one"},
        dedup_key="dedup_key_1",
    )
    second = insert_raw_signal_dedup(
        cur,
        "test_src",
        "https://example.com/dedup-1",
        {"title": "duplicate"},
        dedup_key="dedup_key_1",
    )
    conn.commit()
    conn.close()
    assert first is True
    assert second is False


def test_batch_writer_commits(operational_db, monkeypatch):
    monkeypatch.setenv("CI_SQLITE_WRITER_LOCK", "0")
    with RawSignalBatchWriter(commit_every=3) as batch:
        for i in range(7):
            batch.insert(
                "batch_test",
                f"https://example.com/batch-{i}",
                {"n": i},
            )
    conn = sqlite3.connect(operational_db)
    n = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE source = 'batch_test'").fetchone()[0]
    conn.close()
    assert n == 7


def test_writer_lock_serializes(operational_db, monkeypatch):
    monkeypatch.setenv("CI_SQLITE_WRITER_LOCK", "1")
    assert lock_path(operational_db).name.endswith(".write.lock")
    order: list[int] = []

    def job(n: int) -> None:
        with writer_lock(operational_db):
            order.append(n)

    threads = [threading.Thread(target=job, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(order) == 3
