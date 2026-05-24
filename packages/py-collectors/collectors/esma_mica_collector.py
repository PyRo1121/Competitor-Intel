#!/usr/bin/env python3
"""ESMA interim MiCA CASP register (public CSV, no API key)."""

from __future__ import annotations

import csv
import io
import logging
import os
from datetime import UTC, datetime

from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from utils.http import close_http_client, safe_request

from collectors.company_match import resolve_company_id
from collectors.signal_company_resolver import build_domain_index

logger = logging.getLogger("esma_mica_collector")

CASPS_CSV_URL = "https://www.esma.europa.eu/sites/default/files/2024-12/CASPS.csv"
REGISTER_URL = (
    "https://www.esma.europa.eu/esmas-activities/digital-finance-and-innovation/"
    "markets-crypto-assets-regulation-mica"
)


def _max_rows() -> int:
    try:
        return max(50, int(os.environ.get("ESMA_MICA_MAX", "500")))
    except ValueError:
        return 500


def run_esma_mica_collector() -> int:
    resp = safe_request(CASPS_CSV_URL, timeout=60.0)
    if resp is None:
        logger.warning("ESMA CASPS CSV download failed")
        return 0

    text = resp.content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    conn = get_conn()
    cursor = conn.cursor()
    domain_index = build_domain_index(cursor)
    detected_at = datetime.now(UTC).isoformat()
    inserted = 0
    cap = _max_rows()

    for row in reader:
        if inserted >= cap:
            break
        commercial = (row.get("ae_commercial_name") or row.get("ae_lei_name") or "").strip()
        if not commercial:
            continue
        website = (row.get("ae_website") or "").strip() or None
        company_id = resolve_company_id(
            cursor, commercial, website=website, domain_index=domain_index
        )
        if not company_id:
            continue
        lei = (row.get("ae_lei") or "").strip()
        url = website or REGISTER_URL
        payload = {
            "kind": "mica_casp",
            "commercial_name": commercial,
            "lei": lei,
            "home_member_state": (row.get("ae_homeMemberState") or "").strip(),
            "regulator": (row.get("ae_competentAuthority") or "").strip(),
            "services": (row.get("ac_serviceCode") or "").strip(),
            "authorisation_date": (row.get("ac_authorisationNotificationDate") or "").strip(),
            "website": website,
            "url": url,
            "link": url,
            "source": "esma_mica",
        }
        dedup = f"mica_{lei}" if lei else f"mica_{commercial[:48].lower().replace(' ', '_')}"
        if insert_raw_signal_dedup(
            cursor,
            "esma_mica",
            url,
            payload,
            company_id=company_id,
            detected_at=detected_at,
            dedup_key=dedup,
        ):
            inserted += 1

    conn.commit()
    conn.close()
    logger.info("ESMA MiCA collector stored %s signals", inserted)
    return inserted


def run() -> int:
    try:
        return run_esma_mica_collector()
    finally:
        close_http_client()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
