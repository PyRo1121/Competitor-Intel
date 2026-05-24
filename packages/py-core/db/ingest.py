"""SQLite ingest helpers for collectors (deduped raw_signals and legacy x_posts)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

from db.connection import get_conn
from db.sqlite_retry import retry_locked
from db.writer_lock import writer_lock

_RAW_SIGNAL_SQL = """
INSERT OR IGNORE INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
VALUES (?, ?, ?, ?, ?)
"""


def cursor_execute_retry(
    cursor: sqlite3.Cursor,
    sql: str,
    params: tuple[Any, ...] | list[Any] = (),
    *,
    max_retries: int | None = None,
    use_writer_lock: bool = True,
) -> sqlite3.Cursor:
    """
    Execute with exponential backoff + jitter and optional cross-process writer flock.

    Requires UNIQUE(source, signal_type) on raw_signals (idx_raw_signals_dedup).
    """

    def _run() -> sqlite3.Cursor:
        if use_writer_lock:
            with writer_lock():
                return cursor.execute(sql, params)
        return cursor.execute(sql, params)

    return retry_locked(_run, max_retries=max_retries)


def canonical_url_for_dedup(url: str) -> str:
    """
    Normalize URLs for ingest dedup: strip fragments (#rs-*), lower host, trim trailing slash.
    Claim/event source_url may still use #rs{signal_id} — that is intentional downstream.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    scheme = (parsed.scheme or "https").lower()
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def url_dedup_key(url: str, nbytes: int = 16) -> str:
    normalized = canonical_url_for_dedup(url)
    if not normalized:
        return hashlib.sha256(b"empty").hexdigest()[:nbytes]
    return hashlib.sha256(normalized.encode()).hexdigest()[:nbytes]


def raw_signal_exists(cursor: sqlite3.Cursor, source: str, signal_type: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM raw_signals WHERE source = ? AND signal_type = ? LIMIT 1",
        (source, signal_type),
    )
    return cursor.fetchone() is not None


def insert_raw_signal_dedup(
    cursor: sqlite3.Cursor,
    source: str,
    url: str,
    data: dict[str, Any],
    company_id: int | None = None,
    detected_at: str | None = None,
    dedup_key: str | None = None,
    *,
    use_writer_lock: bool = True,
) -> bool:
    """
    Insert raw signal if (source, signal_type) not present.

    Uses INSERT OR IGNORE (unique idx_raw_signals_dedup) — no SELECT-before-INSERT,
    fewer locks, safe under parallel collectors when writer_lock is enabled.

    When CI_INGEST_STAGING=1 and CI_STAGING_SLOT is set (parallel collectors),
    appends JSONL only (merge via ingest_staging.py).
    """
    from db.staging import ingest_staging_active, stage_raw_signal

    if ingest_staging_active():
        return stage_raw_signal(
            source,
            url,
            data,
            company_id=company_id,
            detected_at=detected_at,
            dedup_key=dedup_key,
        )
    if not url and not dedup_key:
        return False
    key = dedup_key or url_dedup_key(url)
    payload = dict(data)
    payload.setdefault("url", url)
    payload.setdefault("link", url)
    ts = detected_at or datetime.now().isoformat()
    cursor_execute_retry(
        cursor,
        _RAW_SIGNAL_SQL,
        (company_id, source, key, json.dumps(payload), ts),
        use_writer_lock=use_writer_lock,
    )
    return cursor.rowcount > 0


def get_company_id(name_or_slug: str) -> int | None:
    """Get company ID by name or slug (short-lived read connection)."""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM companies
            WHERE name = ? OR slug = ? OR x_handle = ?
               OR LOWER(name) = LOWER(?)
            """,
            (name_or_slug, name_or_slug, name_or_slug, name_or_slug),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def insert_x_post(company_name: str, post_data: dict[str, Any]) -> bool:
    """Insert X post (from Grok native access)."""
    company_id = get_company_id(company_name)
    if not company_id:
        return False

    conn = get_conn()
    cursor = conn.cursor()
    try:
        with writer_lock():
            cursor.execute(
                "SELECT 1 FROM x_posts WHERE post_id = ?",
                (post_data.get("post_id"),),
            )
            if cursor.fetchone():
                return False
            cursor.execute(
                """
                INSERT INTO x_posts
                (company_id, post_id, text, posted_at, likes, retweets, replies,
                 url, is_founder_post, sentiment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    post_data.get("post_id"),
                    post_data.get("text"),
                    post_data.get("posted_at"),
                    post_data.get("likes", 0),
                    post_data.get("retweets", 0),
                    post_data.get("replies", 0),
                    post_data.get("url"),
                    post_data.get("is_founder_post", 0),
                    post_data.get("sentiment"),
                ),
            )
            conn.commit()
        return True
    finally:
        conn.close()
