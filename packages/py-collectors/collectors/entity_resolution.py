"""Company entity resolution (Track 4 P4-6)."""

from __future__ import annotations

import re
import sqlite3
from typing import NamedTuple

from collectors.signal_processor import fuzzy_match_company

_ALIAS_RE = re.compile(r"[^a-z0-9]+")


class EntityMatch(NamedTuple):
    company_id: int
    company_name: str
    confidence: float
    method: str


def normalize_alias(name: str) -> str:
    return _ALIAS_RE.sub(" ", name.lower()).strip()


def lookup_alias(cursor: sqlite3.Cursor, name: str) -> EntityMatch | None:
    norm = normalize_alias(name)
    if len(norm) < 2:
        return None
    row = cursor.execute(
        """
        SELECT ca.company_id, c.name, ca.confidence
        FROM company_aliases ca
        JOIN companies c ON c.id = ca.company_id
        WHERE ca.alias_normalized = ?
        LIMIT 1
        """,
        (norm,),
    ).fetchone()
    if not row:
        return None
    return EntityMatch(
        int(row[0]),
        str(row[1]),
        float(row[2] or 0.95),
        "alias",
    )


def resolve_company_entity(
    cursor: sqlite3.Cursor,
    name: str,
    *,
    record_alias: bool = False,
    alias_source: str = "resolver",
) -> EntityMatch | None:
    """Resolve external name: alias table → fuzzy match."""
    if not name or not name.strip():
        return None
    hit = lookup_alias(cursor, name)
    if hit:
        return hit

    matched = fuzzy_match_company(name, cursor)
    if not matched:
        return None
    company_id, company_name, score = matched
    confidence = min(0.99, max(0.5, float(score)))
    if record_alias and confidence >= 0.85:
        register_alias(
            cursor,
            company_id=int(company_id),
            alias=name.strip(),
            source=alias_source,
            confidence=confidence,
        )
    return EntityMatch(int(company_id), str(company_name), confidence, "fuzzy")


def register_alias(
    cursor: sqlite3.Cursor,
    *,
    company_id: int,
    alias: str,
    source: str,
    confidence: float = 0.9,
) -> None:
    norm = normalize_alias(alias)
    if len(norm) < 2:
        return
    cursor.execute(
        """
        INSERT INTO company_aliases (
            company_id, alias_display, alias_normalized, source, confidence
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(alias_normalized) DO UPDATE SET
            company_id = excluded.company_id,
            confidence = MAX(confidence, company_aliases.confidence),
            source = excluded.source
        """,
        (company_id, alias.strip()[:200], norm, source[:64], confidence),
    )
