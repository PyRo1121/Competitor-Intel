"""Structured claims from collector APIs/RSS already stored in raw_signals."""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from collectors.company_match import resolve_company_id

from .claims import (
    upsert_license_claim,
    upsert_product_claim,
    upsert_profile_claim,
    upsert_team_claim,
)

logger = logging.getLogger("company_data.extract_raw_signals")

_BULK_SOURCES = ("sec_edgar", "ycombinator", "esma_mica")


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        return json.loads(row["data_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _company_id(conn: sqlite3.Connection, row: sqlite3.Row, data: dict[str, Any]) -> int | None:
    if row["company_id"]:
        return int(row["company_id"])
    name = (
        data.get("entity_name") or data.get("name") or data.get("commercial_name") or ""
    ).strip()
    if not name:
        return None
    return resolve_company_id(conn.cursor(), name[:200])


def extract_from_raw_signals(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Turn collector payloads in raw_signals into profile / team / product / license claims.
    """
    stats = {
        "profile_claims": 0,
        "team_claims": 0,
        "product_claims": 0,
        "license_claims": 0,
    }
    placeholders = ",".join("?" * len(_BULK_SOURCES))
    rows = conn.execute(
        f"""
        SELECT rs.id, rs.company_id, rs.source, rs.signal_type, rs.data_json, c.website
        FROM raw_signals rs
        LEFT JOIN companies c ON c.id = rs.company_id
        WHERE rs.company_id IS NOT NULL
           OR rs.source IN ({placeholders})
        ORDER BY rs.detected_at DESC
        LIMIT 20000
        """,
        _BULK_SOURCES,
    ).fetchall()

    for row in rows:
        source = (row["source"] or "").lower()
        data = _payload(row)
        company_id = _company_id(conn, row, data)
        if not company_id:
            continue
        website = row["website"]
        base_url = data.get("url") or data.get("link") or source
        raw_id = int(row["id"])
        kind = (data.get("kind") or "").lower()

        if source == "producthunt":
            stats["product_claims"] += _producthunt_claim(
                conn, company_id, data, base_url, website, raw_id
            )
        elif source == "crunchbase":
            stats["profile_claims"] += _crunchbase_rss_claim(
                conn, company_id, data, base_url, website, raw_id
            )
        elif source == "sec_edgar" and kind == "form_d_bulk":
            stats["profile_claims"] += _form_d_profile(
                conn, company_id, data, base_url, website, raw_id
            )
            stats["team_claims"] += _form_d_team(conn, company_id, data, base_url, website, raw_id)
        elif source == "ycombinator" and kind == "yc_directory":
            stats["profile_claims"] += _yc_profile(
                conn, company_id, data, base_url, website, raw_id
            )
            stats["product_claims"] += _yc_product(
                conn, company_id, data, base_url, website, raw_id
            )
        elif source == "esma_mica" and kind == "mica_casp":
            stats["license_claims"] += _esma_license(conn, company_id, data, base_url, raw_id)
        elif source == "hackernews" and kind in ("hn_algolia_show",):
            stats["product_claims"] += _hn_show_product(
                conn, company_id, data, base_url, website, raw_id
            )

    return stats


def _producthunt_claim(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    title = (data.get("title") or "").strip()
    if len(title) < 3:
        return 0
    _, is_new = upsert_product_claim(
        conn,
        company_id=company_id,
        name=title[:80],
        source="producthunt",
        source_url=f"{base_url}#rs-{raw_id}",
        description=(data.get("description") or "")[:500],
        category="product_hunt",
        product_url=base_url if base_url.startswith("http") else None,
        company_website=website,
        extraction_confidence=0.72,
        raw_signal_id=raw_id,
    )
    return 1 if is_new else 0


def _crunchbase_rss_claim(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    desc = (data.get("description") or data.get("title") or "").strip()
    if len(desc) < 20:
        return 0
    _, is_new = upsert_profile_claim(
        conn,
        company_id=company_id,
        field_key="description_long",
        field_value=desc[:4000],
        source="crunchbase",
        source_url=f"{base_url}#rs-{raw_id}",
        company_website=website,
        extraction_confidence=0.68,
        raw_signal_id=raw_id,
    )
    return 1 if is_new else 0


def _form_d_profile(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    created = 0
    fields = {
        "legal_name": data.get("entity_name"),
        "entity_type": data.get("entity_type"),
        "headquarters": data.get("headquarters"),
        "jurisdiction": data.get("jurisdiction"),
        "founded_year": data.get("year_of_inc"),
        "funding_total_offered": data.get("total_offering_amount"),
        "funding_amount_sold": data.get("total_amount_sold"),
    }
    for key, val in fields.items():
        if not val:
            continue
        _, is_new = upsert_profile_claim(
            conn,
            company_id=company_id,
            field_key=key,
            field_value=str(val)[:2000],
            source="sec_edgar",
            source_url=f"{base_url}#rs-{raw_id}-{key}",
            company_website=website,
            extraction_confidence=0.9,
            raw_signal_id=raw_id,
        )
        if is_new:
            created += 1
    return created


def _form_d_team(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    created = 0
    people: list[dict[str, Any]] = data.get("related_persons") or []
    for i, person in enumerate(people):
        name = (person.get("name") or "").strip()
        if len(name) < 3:
            continue
        role = (person.get("relationship") or "Related person")[:120]
        is_founder = "founder" in role.lower() or "executive" in role.lower()
        _, is_new = upsert_team_claim(
            conn,
            company_id=company_id,
            name=name[:120],
            role=role,
            source="sec_edgar",
            source_url=f"{base_url}#rs-{raw_id}-person-{i}",
            is_founder=is_founder,
            company_website=website,
            extraction_confidence=0.85,
            raw_signal_id=raw_id,
        )
        if is_new:
            created += 1
    return created


def _yc_profile(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    created = 0
    mapping = {
        "yc_batch": data.get("batch"),
        "yc_status": data.get("status"),
        "industry": data.get("industry"),
        "description_long": data.get("long_description") or data.get("one_liner"),
        "team_size": data.get("team_size"),
        "website_url": data.get("website"),
    }
    for key, val in mapping.items():
        if val is None or val == "":
            continue
        _, is_new = upsert_profile_claim(
            conn,
            company_id=company_id,
            field_key=key,
            field_value=str(val)[:4000],
            source="ycombinator",
            source_url=f"{base_url}#rs-{raw_id}-{key}",
            company_website=website,
            extraction_confidence=0.76,
            raw_signal_id=raw_id,
        )
        if is_new:
            created += 1
    return created


def _yc_product(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    one_liner = (data.get("one_liner") or "").strip()
    if len(one_liner) < 4:
        return 0
    name = (data.get("name") or "Product")[:80]
    _, is_new = upsert_product_claim(
        conn,
        company_id=company_id,
        name=name,
        source="ycombinator",
        source_url=f"{base_url}#rs-{raw_id}-product",
        description=one_liner[:500],
        category="yc",
        product_url=data.get("website"),
        company_website=website,
        extraction_confidence=0.74,
        raw_signal_id=raw_id,
    )
    return 1 if is_new else 0


def _esma_license(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    raw_id: int,
) -> int:
    jurisdiction = (data.get("home_member_state") or "EU")[:16]
    regulator = (data.get("regulator") or "ESMA MiCA")[:200]
    services = (data.get("services") or "Crypto-Asset Service Provider")[:500]
    lei = (data.get("lei") or "").strip()
    _, is_new = upsert_license_claim(
        conn,
        company_id=company_id,
        jurisdiction=jurisdiction,
        license_type="MiCA CASP",
        status="authorized",
        regulator=regulator,
        source="esma_mica",
        source_url=f"{base_url}#rs-{raw_id}",
        license_number=lei or None,
        effective_date=(data.get("authorisation_date") or "")[:32] or None,
        snippet=services[:500],
        extraction_confidence=0.92,
    )
    return 1 if is_new else 0


def _hn_show_product(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    website: str | None,
    raw_id: int,
) -> int:
    title = (data.get("title") or "").strip()
    if len(title) < 5:
        return 0
    clean = title.replace("Show HN:", "").replace("Show HN", "").strip()
    _, is_new = upsert_product_claim(
        conn,
        company_id=company_id,
        name=clean[:80] or "Show HN launch",
        source="hackernews",
        source_url=f"{base_url}#rs-{raw_id}",
        description=clean[:500],
        category="show_hn",
        product_url=data.get("url"),
        company_website=website,
        extraction_confidence=0.7,
        raw_signal_id=raw_id,
    )
    return 1 if is_new else 0
