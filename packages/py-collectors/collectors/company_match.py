"""Resolve external entity names / URLs to tracked companies."""

from __future__ import annotations

import sqlite3

from collectors.entity_resolution import resolve_company_entity
from collectors.signal_company_resolver import build_domain_index, resolve_from_url

Match = tuple[int, str, float]


def resolve_company_id(
    cursor: sqlite3.Cursor,
    name: str,
    *,
    website: str | None = None,
    domain_index: dict[str, Match] | None = None,
    record_alias: bool = False,
) -> int | None:
    idx = domain_index if domain_index is not None else build_domain_index(cursor)
    if website:
        hit = resolve_from_url(website, idx)
        if hit:
            return int(hit[0])
    if name:
        entity = resolve_company_entity(
            cursor,
            name,
            record_alias=record_alias,
            alias_source="company_match",
        )
        if entity:
            return entity.company_id
    return None
