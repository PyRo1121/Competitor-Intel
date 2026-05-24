"""Extract team / product / license claims from intelligence_events and raw_signals."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from urllib.parse import quote

from .claims import upsert_license_claim, upsert_product_claim, upsert_team_claim

logger = logging.getLogger("company_data.extract_signals")

# Leadership: conservative — require title keyword near a plausible name
_ROLE_WORDS = (
    r"CEO|CTO|CFO|COO|CPO|CMO|Chief\s+\w+\s+Officer|"
    r"President|Founder|Co-?Founder|General\s+Partner|Managing\s+Director|"
    r"Chair(?:man|woman|person)?|Board\s+member"
)
_ROLE_HINT_RE = re.compile(_ROLE_WORDS, re.I)

_TEAM_EVENT_TYPES = ("hire", "hiring", "executive", "leadership", "team", "appointment")

_BAD_TEAM_NAMES = frozenset(
    {
        "the",
        "and",
        "new",
        "series",
        "round",
        "million",
        "billion",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "artificial",
        "intelligence",
        "venture",
        "capital",
    }
)
_LEADERSHIP_RE = [
    re.compile(
        rf"(?P<name>[A-Z][\w\-']+(?:\s+[A-Z][\w\-']+){{0,2}})\s+"
        rf"(?:named|appointed|joins|joined|named as)\s+"
        rf"(?:as\s+)?(?P<role>{_ROLE_WORDS})",
        re.I,
    ),
    re.compile(
        rf"(?P<role>{_ROLE_WORDS})\s+(?P<name>[A-Z][\w\-']+(?:\s+[A-Z][\w\-']+){{0,2}})",
        re.I,
    ),
    re.compile(
        rf"(?P<name>[A-Z][\w\-']+(?:\s+[A-Z][\w\-']+){{0,2}})\s+is\s+(?:the\s+)?(?P<role>{_ROLE_WORDS})",
        re.I,
    ),
]

_FOUNDER_RE = re.compile(
    r"(?P<name>[A-Z][\w\-']+(?:\s+[A-Z][\w\-']+){{0,2}}),?\s+(?:co-?)?founder",
    re.I,
)

_PRODUCT_NAME_RE = re.compile(
    r"(?:launches?|unveils?|introduces?|releases?)\s+[\"']?(?P<name>[A-Z][\w\s\-]{2,48})[\"']?",
    re.I,
)

_LICENSE_RE = [
    re.compile(
        r"(?P<reg>FCA|ECB|BaFin|FINMA|OCC|state\s+charter)\b.*?"
        r"(?P<status>authorized|licensed|approved|granted|registered)",
        re.I,
    ),
    re.compile(
        r"(?P<status>banking\s+license|payment\s+institution\s+license|e-money\s+license)",
        re.I,
    ),
]


def _row_str(row: sqlite3.Row, key: str, default: str = "") -> str:
    try:
        val = row[key]
    except IndexError:
        return default
    return val if val is not None else default


def _text_blob(row: sqlite3.Row) -> str:
    parts = [
        _row_str(row, "headline"),
        _row_str(row, "description"),
        _row_str(row, "title"),
        _row_str(row, "content"),
    ]
    raw_json = _row_str(row, "data_json")
    if raw_json:
        try:
            data = json.loads(raw_json or "{}")
            if isinstance(data, dict):
                for key in ("title", "summary", "description", "headline", "content"):
                    val = data.get(key)
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())
        except (json.JSONDecodeError, TypeError):
            pass
    return " ".join(p for p in parts if p)


def _source_url(row: sqlite3.Row, suffix: str) -> str:
    base = row["source_url"] if row["source_url"] else _row_str(row, "source", "unknown")
    eid = row["id"]
    return f"{base}#company-data-{suffix}-{eid}"


def extract_from_events(conn: sqlite3.Connection) -> dict[str, int]:
    stats = {"team_claims": 0, "product_claims": 0, "license_claims": 0}
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT ie.id, ie.company_id, ie.event_type, ie.description, ie.source,
               ie.source_url, ie.announced_date, c.website, rs.data_json
        FROM intelligence_events ie
        JOIN companies c ON c.id = ie.company_id
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.company_id IS NOT NULL
        ORDER BY ie.announced_date DESC
        """
    ).fetchall()

    for row in rows:
        text = _text_blob(row)
        if not text or len(text) < 20:
            continue
        company_id = int(row["company_id"])
        website = row["website"]
        event_type = (row["event_type"] or "").lower()
        source = (row["source"] or "").lower()

        team_event = any(k in event_type for k in _TEAM_EVENT_TYPES)
        if team_event or _ROLE_HINT_RE.search(text):
            stats["team_claims"] += _extract_team_from_text(
                conn,
                company_id,
                text,
                source=source or "press",
                source_url=_source_url(row, "team"),
                website=website,
                intelligence_event_id=row["id"],
                announced_date=row["announced_date"],
            )

        is_product_event = any(k in event_type for k in ("product", "launch", "feature"))
        if source == "producthunt" or is_product_event:
            stats["product_claims"] += _extract_products_from_text(
                conn,
                company_id,
                text,
                source=source or "press",
                source_url=_source_url(row, "product"),
                website=website,
                intelligence_event_id=row["id"],
                launch_date=row["announced_date"],
            )

        if any(k in event_type for k in ("regulatory", "license", "compliance", "fintech")):
            stats["license_claims"] += _extract_licenses_from_text(
                conn,
                company_id,
                text,
                source=source or "press",
                source_url=_source_url(row, "license"),
                intelligence_event_id=row["id"],
                effective_date=row["announced_date"],
            )

    return stats


def _extract_team_from_text(
    conn: sqlite3.Connection,
    company_id: int,
    text: str,
    *,
    source: str,
    source_url: str,
    website: str | None,
    intelligence_event_id: int | None,
    announced_date: str | None,
) -> int:
    created = 0
    seen: set[str] = set()
    for pat in _LEADERSHIP_RE:
        for m in pat.finditer(text):
            name = (m.groupdict().get("name") or "").strip()
            role = (m.groupdict().get("role") or "").strip()
            if len(name) < 4 or _is_bad_team_name(name):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            _, is_new = upsert_team_claim(
                conn,
                company_id=company_id,
                name=name,
                role=role[:120] if role else None,
                source=source,
                source_url=f"{source_url}-{quote(name)}",
                joined_date=announced_date,
                headline=text[:200],
                intelligence_event_id=intelligence_event_id,
                company_website=website,
            )
            if is_new:
                created += 1

    for m in _FOUNDER_RE.finditer(text):
        name = m.group("name").strip()
        if len(name) < 4 or name.lower() in seen:
            continue
        seen.add(name.lower())
        _, is_new = upsert_team_claim(
            conn,
            company_id=company_id,
            name=name,
            role="Founder",
            is_founder=True,
            source=source,
            source_url=f"{source_url}-founder-{quote(name)}",
            joined_date=announced_date,
            intelligence_event_id=intelligence_event_id,
            company_website=website,
        )
        if is_new:
            created += 1
    return created


def _is_bad_team_name(name: str) -> bool:
    parts = name.lower().replace(".", " ").split()
    if not parts:
        return True
    if parts[0] in _BAD_TEAM_NAMES:
        return True
    return bool(all(p in _BAD_TEAM_NAMES for p in parts))


def _extract_products_from_text(
    conn: sqlite3.Connection,
    company_id: int,
    text: str,
    *,
    source: str,
    source_url: str,
    website: str | None,
    intelligence_event_id: int | None,
    launch_date: str | None,
) -> int:
    created = 0
    for m in _PRODUCT_NAME_RE.finditer(text):
        name = m.group("name").strip().strip('"').strip("'")
        if len(name) < 3 or len(name) > 60:
            continue
        _, is_new = upsert_product_claim(
            conn,
            company_id=company_id,
            name=name,
            source=source,
            source_url=f"{source_url}-{quote(name)}",
            description=text[:500],
            category="product",
            launch_date=launch_date,
            intelligence_event_id=intelligence_event_id,
            company_website=website,
        )
        if is_new:
            created += 1
    return created


def _extract_licenses_from_text(
    conn: sqlite3.Connection,
    company_id: int,
    text: str,
    *,
    source: str,
    source_url: str,
    intelligence_event_id: int | None,
    effective_date: str | None,
) -> int:
    created = 0
    for pat in _LICENSE_RE:
        if not pat.search(text):
            continue
        jurisdiction = "UK" if "FCA" in text.upper() else "EU" if "ECB" in text.upper() else "US"
        _, is_new = upsert_license_claim(
            conn,
            company_id=company_id,
            jurisdiction=jurisdiction,
            license_type="financial_services",
            status="reported",
            regulator="FCA" if "FCA" in text.upper() else None,
            source=source,
            source_url=source_url,
            effective_date=effective_date,
            snippet=text[:400],
            intelligence_event_id=intelligence_event_id,
        )
        if is_new:
            created += 1
        break
    return created
