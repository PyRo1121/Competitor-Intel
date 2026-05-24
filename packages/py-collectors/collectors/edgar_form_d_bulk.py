"""SEC Form D quarterly data sets (public ZIP, SEC User-Agent only)."""

from __future__ import annotations

import csv
import io
import logging
import os
import zipfile
from datetime import datetime
from typing import Any

from db.batch import RawSignalBatchWriter
from db.connection import get_conn
from utils.http import safe_request

from collectors.company_match import resolve_company_id
from collectors.signal_company_resolver import Match, build_domain_index
from collectors.sources_registry import SEC_USER_AGENT

logger = logging.getLogger("edgar_form_d_bulk")

SEC_ZIP_BASE = "https://www.sec.gov/files/structureddata/data/form-d-data-sets"
SEC_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept": "*/*"}

DEFAULT_QUARTER_ZIPS = ("2025q4_d.zip", "2025q3_d.zip")


def _quarter_zips() -> list[str]:
    raw = os.environ.get("EDGAR_FORM_D_QUARTER_ZIPS", "").strip()
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return list(DEFAULT_QUARTER_ZIPS)


def _row_cap() -> int:
    try:
        return max(100, int(os.environ.get("EDGAR_FORM_D_BULK_MAX", "20000")))
    except ValueError:
        return 8000


def _read_tsv(zf: zipfile.ZipFile, suffix: str) -> list[dict[str, str]]:
    name = next((n for n in zf.namelist() if n.endswith(suffix)), None)
    if not name:
        return []
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
        return list(csv.DictReader(text, delimiter="\t"))


def ingest_form_d_quarter(
    batch: RawSignalBatchWriter,
    zip_name: str,
    *,
    domain_index: dict[str, Match],
    remaining: int,
    detected_at: str,
) -> tuple[int, int]:
    url = f"{SEC_ZIP_BASE}/{zip_name}"
    resp = safe_request(url, timeout=120.0, headers=SEC_HEADERS)
    if resp is None:
        logger.warning("Form D ZIP download failed: %s", url)
        return 0, remaining

    try:
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
    except zipfile.BadZipFile as exc:
        logger.warning("Invalid Form D ZIP %s: %s", zip_name, exc)
        return 0, remaining

    issuers = _read_tsv(zf, "ISSUERS.tsv")
    offerings = {
        (r.get("ACCESSIONNUMBER") or "").strip(): r
        for r in _read_tsv(zf, "OFFERING.tsv")
        if (r.get("ACCESSIONNUMBER") or "").strip()
    }
    related: dict[str, list[dict[str, str]]] = {}
    for row in _read_tsv(zf, "RELATEDPERSONS.tsv"):
        acc = (row.get("ACCESSIONNUMBER") or "").strip()
        if not acc:
            continue
        bucket = related.setdefault(acc, [])
        if len(bucket) < 12:
            bucket.append(row)

    inserted = 0
    for row in issuers:
        if remaining <= 0:
            break
        if (row.get("IS_PRIMARYISSUER_FLAG") or "").upper() != "YES":
            continue
        acc = (row.get("ACCESSIONNUMBER") or "").strip()
        name = (row.get("ENTITYNAME") or "").strip()
        if not acc or not name:
            continue
        entity_type = (row.get("ENTITYTYPE") or "").strip()
        company_id = resolve_company_id(batch.cursor, name, domain_index=domain_index)
        city = (row.get("CITY") or "").strip()
        state = (row.get("STATEORCOUNTRY") or "").strip()
        hq = ", ".join(p for p in (city, state) if p)
        offer = offerings.get(acc, {})
        people = related.get(acc, [])
        cik = (row.get("CIK") or "").strip()
        filing_url = (
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
            f"&CIK={cik}&type=D&dateb=&owner=exclude&count=40"
        )
        payload: dict[str, Any] = {
            "kind": "form_d_bulk",
            "accession": acc,
            "entity_name": name,
            "cik": cik,
            "entity_type": entity_type,
            "headquarters": hq,
            "jurisdiction": (row.get("JURISDICTIONOFINC") or "").strip(),
            "phone": (row.get("ISSUERPHONENUMBER") or "").strip(),
            "year_of_inc": (row.get("YEAROFINC_VALUE_ENTERED") or "").strip(),
            "total_offering_amount": (offer.get("TOTALOFFERINGAMOUNT") or "").strip(),
            "total_amount_sold": (offer.get("TOTALAMOUNTSOLD") or "").strip(),
            "related_persons": [
                {
                    "name": f"{p.get('FIRSTNAME', '')} {p.get('LASTNAME', '')}".strip(),
                    "relationship": (p.get("RELATIONSHIP") or "").strip(),
                }
                for p in people
                if (p.get("FIRSTNAME") or p.get("LASTNAME"))
            ],
            "filing_date": zip_name,
            "url": filing_url,
            "link": filing_url,
            "source": "sec_edgar",
            "category": "funding",
        }
        if batch.insert(
            "sec_edgar",
            filing_url,
            payload,
            company_id=company_id,
            detected_at=detected_at,
            dedup_key=f"form_d_bulk_{acc}",
        ):
            inserted += 1
            remaining -= 1

    logger.info("Form D bulk %s: inserted %s (remaining cap %s)", zip_name, inserted, remaining)
    return inserted, remaining


def run_form_d_bulk_ingest() -> int:
    if os.environ.get("EDGAR_FORM_D_BULK", "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return 0
    read_conn = get_conn(profile="ingest_bulk")
    try:
        domain_index = build_domain_index(read_conn.cursor())
    finally:
        read_conn.close()

    detected_at = datetime.now().isoformat()
    cap = _row_cap()
    total = 0
    commit_every = max(100, int(os.environ.get("CI_SQLITE_BATCH_COMMIT", "500")))
    with RawSignalBatchWriter(commit_every=commit_every) as batch:
        for zip_name in _quarter_zips():
            if cap <= 0:
                break
            n, cap = ingest_form_d_quarter(
                batch,
                zip_name,
                domain_index=domain_index,
                remaining=cap,
                detected_at=detected_at,
            )
            total += n
    return total
