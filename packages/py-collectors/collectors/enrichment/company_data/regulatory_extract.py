"""Regulatory / SEC bulk → license_claims."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from typing import Any

from collectors.company_match import resolve_company_id

from .claims import upsert_license_claim

logger = logging.getLogger("company_data.regulatory_extract")

_REGULATORY_SOURCES = frozenset({"sec_edgar"})
_REGULATORY_CATEGORIES = frozenset({"regulatory"})
_REGULATORY_SOURCE_HINTS = (
    "fca",
    "sec ",
    "ecb",
    "eba",
    "bank of england",
    "finra",
    "cftc",
    "esma",
)

_LICENSE_PATTERNS = (
    re.compile(
        r"\b(FCA|ECB|EBA|BaFin|FINMA|OCC|CFTC|SEC|ESMA)\b.*?"
        r"\b(authorized|authorised|licensed|approved|granted|registered|cleared)\b",
        re.I,
    ),
    re.compile(
        r"\b(banking\s+license|payment\s+institution|e-money\s+institution|"
        r"broker-dealer|money\s+transmitter)\b",
        re.I,
    ),
    re.compile(r"\b(MiCA|crypto-asset\s+service\s+provider|CASP)\b", re.I),
)

_SCAN_LIMIT = 20_000


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        return json.loads(row["data_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _resolve_company(
    conn: sqlite3.Connection, row: sqlite3.Row, data: dict[str, Any]
) -> int | None:
    if row["company_id"]:
        return int(row["company_id"])
    name = (
        data.get("entity_name") or data.get("commercial_name") or data.get("title") or ""
    ).strip()
    if len(name) < 3:
        return None
    return resolve_company_id(conn.cursor(), name[:200])


def _is_regulatory_rss(source: str, data: dict[str, Any]) -> bool:
    if (data.get("category") or "").strip().lower() in _REGULATORY_CATEGORIES:
        return True
    src = source.lower()
    return any(hint in src for hint in _REGULATORY_SOURCE_HINTS)


def _jurisdiction_from_text(text: str) -> str:
    upper = text.upper()
    if "FCA" in upper or "UK" in upper:
        return "UK"
    if any(k in upper for k in ("ECB", "EBA", "ESMA", "EU", "MICA")):
        return "EU"
    return "US"


def _regulator_from_text(text: str) -> str | None:
    for token in ("FCA", "ECB", "EBA", "SEC", "ESMA", "BaFin", "FINMA", "OCC", "CFTC"):
        if token in text.upper():
            return token
    return None


def _license_type_from_text(text: str) -> str:
    if re.search(r"\bMiCA\b|CASP", text, re.I):
        return "MiCA CASP"
    if re.search(r"payment\s+institution", text, re.I):
        return "payment_institution"
    return "financial_services"


def _license_from_rss_text(
    conn: sqlite3.Connection,
    company_id: int,
    text: str,
    *,
    source: str,
    source_url: str,
    raw_id: int,
) -> int:
    if not any(pat.search(text) for pat in _LICENSE_PATTERNS):
        return 0
    _, is_new = upsert_license_claim(
        conn,
        company_id=company_id,
        jurisdiction=_jurisdiction_from_text(text),
        license_type=_license_type_from_text(text),
        status="reported",
        regulator=_regulator_from_text(text),
        source=source[:64],
        source_url=f"{source_url}#rs-{raw_id}-reg",
        snippet=text[:500],
        extraction_confidence=0.75,
    )
    return 1 if is_new else 0


def _form_d_license(
    conn: sqlite3.Connection,
    company_id: int,
    data: dict[str, Any],
    base_url: str,
    raw_id: int,
) -> int:
    """SEC Form D → US filing record (incorporation state kept in snippet, not jurisdiction)."""
    entity_type = (data.get("entity_type") or "").strip()
    license_type = f"Form D ({entity_type[:40]})" if entity_type else "Form D exemption"
    inc_state = (data.get("jurisdiction") or "").strip()
    snippet_parts = [
        f"Offering {data.get('total_offering_amount') or '?'}",
        f"sold {data.get('total_amount_sold') or '?'}",
    ]
    if inc_state:
        snippet_parts.append(f"inc. {inc_state}")
    _, is_new = upsert_license_claim(
        conn,
        company_id=company_id,
        jurisdiction="US",
        license_type=license_type,
        status="filed",
        regulator="SEC",
        source="sec_edgar",
        source_url=f"{base_url}#rs-{raw_id}-form-d-license",
        license_number=(data.get("cik") or "")[:32] or None,
        snippet="; ".join(snippet_parts)[:500],
        extraction_confidence=0.88,
    )
    return 1 if is_new else 0


def _fetch_candidate_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Bounded scan: bulk regulatory sources + RSS rows tagged regulatory in JSON."""
    placeholders = ",".join("?" * len(_REGULATORY_SOURCES))
    return conn.execute(
        f"""
        SELECT rs.id, rs.company_id, rs.source, rs.signal_type, rs.data_json
        FROM raw_signals rs
        WHERE rs.source IN ({placeholders})
           OR rs.data_json LIKE '%"category": "regulatory"%'
           OR rs.data_json LIKE '%"category":"regulatory"%'
        ORDER BY rs.detected_at DESC
        LIMIT ?
        """,
        (*_REGULATORY_SOURCES, _SCAN_LIMIT),
    ).fetchall()


def extract_regulatory_license_claims(conn: sqlite3.Connection) -> dict[str, int]:
    """SEC Form D bulk and regulatory RSS → license_claims (ESMA MiCA: extract_raw_signals)."""
    stats = {"license_claims": 0, "rss_regulatory_scanned": 0}
    for row in _fetch_candidate_rows(conn):
        source = (row["source"] or "").strip()
        data = _payload(row)
        kind = (data.get("kind") or "").lower()
        company_id = _resolve_company(conn, row, data)
        if not company_id:
            continue
        base_url = data.get("url") or data.get("link") or source
        raw_id = int(row["id"])

        if source == "sec_edgar" and kind == "form_d_bulk":
            stats["license_claims"] += _form_d_license(conn, company_id, data, base_url, raw_id)
            continue

        if not _is_regulatory_rss(source, data):
            continue

        stats["rss_regulatory_scanned"] += 1
        text = " ".join(
            p for p in (data.get("title"), data.get("summary")) if isinstance(p, str) and p
        ).strip()
        if len(text) < 20:
            continue
        stats["license_claims"] += _license_from_rss_text(
            conn,
            company_id,
            text,
            source=source[:64] or "rss",
            source_url=base_url,
            raw_id=raw_id,
        )

    logger.info("Regulatory license extract: %s", stats)
    return stats
