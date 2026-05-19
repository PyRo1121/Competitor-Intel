"""
Ingestion Layer - Handles inserting data from all sources into SQLite
Optimized for free-tier sources + Grok native X access
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from db.connection import get_conn, DB_PATH
import hashlib


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

def insert_raw_signal(company_id: Optional[int], source: str, signal_type: str, data: Dict[str, Any]):
    """Insert raw flexible signal."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, ?, ?, ?, 0)
    """, (company_id, source, signal_type, json.dumps(data)))
    conn.commit()
    conn.close()

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

def insert_funding_event(company_name: str, funding_data: Dict[str, Any]) -> bool:
    """Insert funding round."""
    company_id = get_company_id(company_name)
    if not company_id:
        return False
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO funding_events 
        (company_id, round_type, amount_usd, valuation_usd, announced_date, investors, source, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id,
        funding_data.get("round_type"),
        funding_data.get("amount_usd"),
        funding_data.get("valuation_usd"),
        funding_data.get("announced_date"),
        json.dumps(funding_data.get("investors", [])),
        funding_data.get("source", "manual"),
        funding_data.get("source_url")
    ))
    
    source = funding_data.get("source", "x")
    url = funding_data.get("source_url") or funding_data.get("url") or ""
    dedup_key = url_dedup_key(url) if url else f"funding:{company_id}:{funding_data.get('round_type', 'unknown')}"
    insert_raw_signal_dedup(
        cursor,
        source,
        url,
        funding_data,
        company_id=company_id,
        dedup_key=dedup_key,
    )
    conn.commit()
    conn.close()
    return True

def insert_product_update(company_name: str, update_data: Dict[str, Any]) -> bool:
    """Insert product/feature update."""
    company_id = get_company_id(company_name)
    if not company_id:
        return False
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO product_updates 
        (company_id, title, description, update_type, announced_date, source, source_url, semantic_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        company_id,
        update_data.get("title"),
        update_data.get("description"),
        update_data.get("update_type", "feature"),
        update_data.get("announced_date"),
        update_data.get("source"),
        update_data.get("source_url"),
        update_data.get("semantic_hash")
    ))
    
    source = update_data.get("source", "rss")
    url = update_data.get("source_url") or update_data.get("url") or ""
    dedup_key = url_dedup_key(url) if url else f"product:{company_id}:{update_data.get('title', '')[:80]}"
    insert_raw_signal_dedup(
        cursor,
        source,
        url,
        update_data,
        company_id=company_id,
        dedup_key=dedup_key,
    )
    conn.commit()
    conn.close()
    return True

def insert_rss_item(company_name: Optional[str], rss_data: Dict[str, Any]) -> bool:
    """Insert RSS/blog item."""
    company_id = get_company_id(company_name) if company_name else None
    
    conn = get_conn()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO rss_items 
            (company_id, feed_url, title, summary, published_at, url, source_name, semantic_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            rss_data.get("feed_url"),
            rss_data.get("title"),
            rss_data.get("summary"),
            rss_data.get("published_at"),
            rss_data.get("url"),
            rss_data.get("source_name"),
            rss_data.get("semantic_hash")
        ))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate URL
    finally:
        conn.close()

def get_recent_signals(days: int = 7) -> List[Dict]:
    """Get recent high-signal activity."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, source, signal_type, detected_at, data_json
        FROM v_recent_signals
        LIMIT 50
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "company": r[0],
            "source": r[1],
            "type": r[2],
            "detected_at": r[3],
            "data": json.loads(r[4]) if r[4] else {}
        }
        for r in rows
    ]

def get_company_summary(company_name: str) -> Dict:
    """Get rich summary for one company."""
    company_id = get_company_id(company_name)
    if not company_id:
        return {}
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Basic info
    cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    company = dict(zip([col[0] for col in cursor.description], cursor.fetchone()))
    
    # Recent funding
    cursor.execute("""
        SELECT * FROM funding_events 
        WHERE company_id = ? 
        ORDER BY announced_date DESC LIMIT 3
    """, (company_id,))
    funding = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    # Recent X activity
    cursor.execute("""
        SELECT * FROM x_posts 
        WHERE company_id = ? 
        ORDER BY posted_at DESC LIMIT 5
    """, (company_id,))
    x_posts = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    conn.close()
    
    return {
        "company": company,
        "recent_funding": funding,
        "recent_x": x_posts
    }