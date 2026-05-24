"""
High-throughput ingest helpers — one connection, batched commits, prepared INSERT.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from db.connection import get_conn
from db.ingest import RAW_SIGNAL_INSERT_SQL, prepare_raw_signal
from db.sqlite_tuning import ProfileName
from db.writer_lock import writer_lock


class RawSignalBatchWriter:
    """
    Reuse one ingest_bulk connection; commit every N inserts.

    Use in long-running collectors (EDGAR bulk) instead of per-row commit.
    """

    def __init__(
        self,
        *,
        commit_every: int = 500,
        profile: ProfileName = "ingest_bulk",
        use_writer_lock: bool = True,
    ) -> None:
        self.commit_every = max(1, commit_every)
        self._use_writer_lock = use_writer_lock
        self._conn = get_conn(profile=profile)
        self._cursor = self._conn.cursor()
        self._pending = 0
        self.inserted = 0
        self._detected_default = datetime.now().isoformat()

    def insert(
        self,
        source: str,
        url: str,
        data: dict[str, Any],
        company_id: int | None = None,
        detected_at: str | None = None,
        dedup_key: str | None = None,
    ) -> bool:
        prepared = prepare_raw_signal(
            source,
            url,
            data,
            company_id=company_id,
            detected_at=detected_at,
            dedup_key=dedup_key,
            default_detected_at=self._detected_default,
        )
        if prepared is None:
            return False
        self._cursor.execute(
            RAW_SIGNAL_INSERT_SQL,
            (
                prepared.company_id,
                prepared.source,
                prepared.signal_type,
                prepared.data_json,
                prepared.detected_at,
            ),
        )
        ok = self._cursor.rowcount > 0
        if ok:
            self.inserted += 1
        self._pending += 1
        if self._pending >= self.commit_every:
            self.flush()
        return ok

    def flush(self) -> None:
        if self._pending <= 0:
            return
        if self._use_writer_lock:
            with writer_lock():
                self._conn.commit()
        else:
            self._conn.commit()
        self._pending = 0

    def close(self) -> None:
        self.flush()
        self._cursor.close()
        self._conn.close()

    @property
    def cursor(self) -> sqlite3.Cursor:
        return self._cursor

    def __enter__(self) -> RawSignalBatchWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
