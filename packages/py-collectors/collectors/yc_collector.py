#!/usr/bin/env python3
"""Y Combinator public company directory (open JSON, no API key)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from db.staging import ingest_staging_active
from db.writer_lock import writer_lock
from utils.http import close_http_client, safe_request

from collectors.company_match import resolve_company_id
from collectors.signal_company_resolver import build_domain_index

logger = logging.getLogger("yc_collector")

YC_DIRECTORY_URL = "https://yc-oss.github.io/api/companies/all.json"


def _max_rows() -> int:
    try:
        return max(50, int(os.environ.get("YC_COLLECTOR_MAX", "6000")))
    except ValueError:
        return 6000


def run_yc_collector() -> int:
    resp = safe_request(YC_DIRECTORY_URL, timeout=60.0)
    if resp is None:
        logger.warning("YC directory download failed")
        return 0

    try:
        companies: list[dict[str, Any]] = resp.json()
    except Exception as exc:
        logger.warning("YC directory JSON invalid: %s", exc)
        return 0

    conn = get_conn()
    cursor = conn.cursor()
    domain_index = build_domain_index(cursor)
    detected_at = datetime.now(UTC).isoformat()
    inserted = 0
    cap = _max_rows()

    def _ingest_rows() -> None:
        nonlocal inserted
        for row in companies:
            if inserted >= cap:
                break
            name = (row.get("name") or "").strip()
            if not name:
                continue
            website = (row.get("website") or row.get("url") or "").strip() or None
            company_id = resolve_company_id(
                cursor, name, website=website, domain_index=domain_index
            )
            slug = (row.get("slug") or name).replace(" ", "-").lower()[:80]
            url = website or f"https://www.ycombinator.com/companies/{slug}"
            payload = {
                "kind": "yc_directory",
                "name": name,
                "batch": row.get("batch"),
                "status": row.get("status"),
                "industry": row.get("industry"),
                "subindustry": row.get("subindustry"),
                "one_liner": row.get("one_liner") or row.get("oneLine"),
                "long_description": row.get("long_description") or row.get("description"),
                "team_size": row.get("team_size"),
                "website": website,
                "tags": row.get("tags") or [],
                "url": url,
                "link": url,
                "source": "ycombinator",
            }
            if insert_raw_signal_dedup(
                cursor,
                "ycombinator",
                url,
                payload,
                company_id=company_id,
                detected_at=detected_at,
                dedup_key=f"yc_{slug}",
                use_writer_lock=False,
            ):
                inserted += 1

    if ingest_staging_active():
        _ingest_rows()
    else:
        with writer_lock():
            _ingest_rows()
            conn.commit()
    conn.close()
    logger.info("YC collector stored %s signals", inserted)
    return inserted


def run() -> int:
    try:
        return run_yc_collector()
    finally:
        close_http_client()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
