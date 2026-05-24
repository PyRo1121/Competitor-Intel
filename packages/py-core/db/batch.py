"""
High-throughput ingest helpers — one connection, batched commits, prepared INSERT.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from db.connection import get_conn
from db.ingest import url_dedup_key
from db.sqlite_tuning import ProfileName
from db.writer_lock import writer_lock

_RAW_SIGNAL_INSERT = """
INSERT OR IGNORE INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
VALUES (?, ?, ?, ?, ?)
"""


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
    ) -> None:
        self.commit_every = max(1, commit_every)
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
        if not url and not dedup_key:
            return False
        key = dedup_key or url_dedup_key(url)
        payload = dict(data)
        payload.setdefault("url", url)
        payload.setdefault("link", url)
        ts = detected_at or self._detected_default
        with writer_lock():
            self._cursor.execute(
                _RAW_SIGNAL_INSERT,
                (company_id, source, key, json.dumps(payload), ts),
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
        with writer_lock():
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
