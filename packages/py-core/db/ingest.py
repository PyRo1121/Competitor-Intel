"""SQLite ingest helpers for collectors (deduped raw_signals and legacy x_posts)."""

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from db.connection import get_conn


def url_dedup_key(url: str, nbytes: int = 16) -> str:
    normalized = (url or "").strip()
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
    data: Dict[str, Any],
    company_id: Optional[int] = None,
    detected_at: Optional[str] = None,
    dedup_key: Optional[str] = None,
) -> bool:
    if not url and not dedup_key:
        return False
    key = dedup_key or url_dedup_key(url)
    if raw_signal_exists(cursor, source, key):
        return False
    payload = dict(data)
    payload.setdefault("url", url)
    payload.setdefault("link", url)
    ts = detected_at or datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, detected_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company_id, source, key, json.dumps(payload), ts),
    )
    return True


def get_company_id(name_or_slug: str) -> Optional[int]:
    """Get company ID by name or slug."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM companies 
        WHERE name = ? OR slug = ? OR x_handle = ?
    """, (name_or_slug, name_or_slug, name_or_slug))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def insert_x_post(company_name: str, post_data: Dict[str, Any]) -> bool:
    """Insert X post (from Grok native access)."""
    company_id = get_company_id(company_name)
    if not company_id:
        return False
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Dedup by post_id
    cursor.execute("SELECT 1 FROM x_posts WHERE post_id = ?", (post_data.get("post_id"),))
    if cursor.fetchone():
        conn.close()
        return False
    
    cursor.execute("""
        INSERT INTO x_posts 
        (company_id, post_id, text, posted_at, likes, retweets, replies, url, is_founder_post, sentiment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id,
        post_data.get("post_id"),
        post_data.get("text"),
        post_data.get("posted_at"),
        post_data.get("likes", 0),
        post_data.get("retweets", 0),
        post_data.get("replies", 0),
        post_data.get("url"),
        post_data.get("is_founder_post", 0),
        post_data.get("sentiment")
    ))
    
    conn.commit()
    conn.close()
    return True