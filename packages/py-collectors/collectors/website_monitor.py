#!/usr/bin/env python3
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from db.connection import get_conn

from collectors.enrichment.utils import safe_request

logger = logging.getLogger("website_monitor")


def fetch_homepage(url: str) -> dict[str, Any] | None:
    if not url:
        return None
    try:
        if not url.startswith("http"):
            url = "https://" + url
        resp = safe_request(url, timeout=15)
        if not resp:
            return None
        text = resp.text
        title = ""
        meta_desc = ""
        if "<title>" in text:
            title_start = text.find("<title>") + 7
            title_end = text.find("</title>")
            if title_end > title_start:
                title = text[title_start:title_end].strip()[:200]
        meta_pos = text.lower().find('name="description"')
        if meta_pos > 0:
            content_pos = text.lower().find("content=", meta_pos)
            if content_pos > 0:
                quote = text[content_pos + 8]
                end = text.find(quote, content_pos + 9)
                if end > content_pos:
                    meta_desc = text[content_pos + 9 : end].strip()[:500]
        page_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
        return {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "hash": page_hash,
            "size_bytes": len(text),
        }
    except Exception as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None


def detect_changes(company_id: int, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT hash, title, meta_description FROM website_snapshots
        WHERE company_id = ? ORDER BY captured_at DESC LIMIT 1
        """,
        (company_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    old_hash, old_title, old_desc = row
    changes = {}
    if old_hash != snapshot["hash"]:
        changes["content_changed"] = True
    if old_title != snapshot["title"]:
        changes["title_changed"] = {"from": old_title, "to": snapshot["title"]}
    if old_desc != snapshot["meta_description"]:
        changes["description_changed"] = True
    return changes if changes else None


def store_snapshot(
    company_id: int, snapshot: dict[str, Any], changes: dict[str, Any] | None = None
):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO website_snapshots
        (company_id, url, title, meta_description, hash, changed_elements, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            snapshot["url"],
            snapshot["title"],
            snapshot["meta_description"],
            snapshot["hash"],
            json.dumps(changes) if changes else None,
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def run() -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, website FROM companies WHERE website IS NOT NULL")
    companies = cursor.fetchall()
    conn.close()
    checked = 0
    changed = 0
    for company_id, name, website in companies:
        snapshot = fetch_homepage(website)
        if not snapshot:
            continue
        checked += 1
        changes = detect_changes(company_id, snapshot)
        store_snapshot(company_id, snapshot, changes)
        if changes:
            changed += 1
            logger.info("Website change detected for %s: %s", name, list(changes.keys()))
    logger.info("Checked %d websites, %d changed", checked, changed)
    return changed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
