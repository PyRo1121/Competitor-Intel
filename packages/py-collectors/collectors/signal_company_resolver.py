"""Multi-strategy company resolution for raw signals."""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("signal_company_resolver")

Match = tuple[int, str, float]


def extract_domain(url: str) -> str | None:
    if not url or not url.strip():
        return None
    raw = url.strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    try:
        host = urlparse(raw).netloc.lower().split(":")[0]
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def build_domain_index(cursor: sqlite3.Cursor) -> dict[str, Match]:
    """Map registrable domain → (company_id, name, score)."""
    index: dict[str, Match] = {}
    cursor.execute("SELECT id, name, website, slug, github_org, x_handle FROM companies")
    for cid, name, website, slug, github_org, _x_handle in cursor.fetchall():
        for raw in (website,):
            domain = extract_domain(raw or "")
            if domain and domain not in index:
                index[domain] = (cid, name, 0.95)
        if slug:
            for suffix in (f"{slug}.com", f"{slug}.io", f"{slug}.ai"):
                if suffix not in index:
                    index[suffix] = (cid, name, 0.75)
        if github_org:
            index[f"github.com/{github_org.lower()}"] = (cid, name, 0.92)
    return index


def resolve_from_url(
    url: str,
    domain_index: dict[str, Match],
) -> Match | None:
    domain = extract_domain(url)
    if not domain:
        return None
    if domain in domain_index:
        return domain_index[domain]
    parts = domain.split(".")
    if len(parts) >= 2:
        base = ".".join(parts[-2:])
        if base in domain_index:
            return domain_index[base]
    return None


def resolve_from_github_url(
    url: str,
    domain_index: dict[str, Match],
) -> Match | None:
    if "github.com/" not in (url or "").lower():
        return None
    m = re.search(r"github\.com/([^/]+)", url, re.I)
    if not m:
        return None
    key = f"github.com/{m.group(1).lower()}"
    return domain_index.get(key)


def resolve_company_enhanced(
    data: dict[str, Any],
    cursor: sqlite3.Cursor,
    *,
    domain_index: dict[str, Match] | None = None,
    fuzzy_match_fn,
    resolve_from_data_fn,
) -> Match | None:
    """
    Layered resolution: structured fields → URL domain → GitHub → title aliases → fuzzy.
    """
    if domain_index is None:
        domain_index = build_domain_index(cursor)

    for key in ("company_id", "company"):
        val = data.get(key)
        if isinstance(val, int):
            cursor.execute("SELECT id, name FROM companies WHERE id = ?", (val,))
            row = cursor.fetchone()
            if row:
                return row[0], row[1], 1.0
        if isinstance(val, str) and val.strip():
            matched = fuzzy_match_fn(val.strip(), cursor)
            if matched:
                return matched

    url = (data.get("url") or data.get("link") or "").strip()
    if url:
        for resolver in (resolve_from_github_url, resolve_from_url):
            hit = resolver(url, domain_index)
            if hit:
                return hit

    from_data = resolve_from_data_fn(data, cursor)
    if from_data:
        return from_data

    blob = " ".join(
        str(data.get(k, "")) for k in ("title", "headline", "description", "summary", "content")
    )
    if blob:
        cursor.execute("SELECT id, name FROM companies ORDER BY LENGTH(name) DESC")
        blob_lower = blob.lower()
        for cid, name in cursor.fetchall():
            nl = name.lower()
            if len(nl) >= 4 and re.search(rf"\b{re.escape(nl)}\b", blob_lower):
                return cid, name, 0.88

    title = data.get("title") or data.get("headline") or ""
    if title and len(title) > 8:
        matched = fuzzy_match_fn(title[:120], cursor)
        if matched and matched[2] >= 0.72:
            return matched

    return None
