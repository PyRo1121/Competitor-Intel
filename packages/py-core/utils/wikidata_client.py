"""Wikidata SPARQL lookups — free structured company facts (no scraping)."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

from utils.http import safe_request

logger = logging.getLogger("intel_wikidata")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_UA = "CompetitorIntel/1.0 (research; mailto:contact@example.com)"

_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$", re.I)


def _normalize_domain(website: str | None) -> str | None:
    if not website:
        return None
    raw = website.strip().lower()
    if raw.startswith("http"):
        from urllib.parse import urlparse

        raw = urlparse(raw).netloc
    raw = raw.split("/")[0].removeprefix("www.")
    if not raw or not _DOMAIN_RE.match(raw):
        return None
    return raw


def _sparql(query: str, timeout: float = 25.0) -> list[dict[str, Any]]:
    resp = safe_request(
        SPARQL_ENDPOINT,
        timeout=timeout,
        headers={
            "User-Agent": WIKIDATA_UA,
            "Accept": "application/sparql-results+json",
        },
        params={"query": query},
    )
    if resp is None:
        return []
    try:
        data = resp.json()
        bindings = data.get("results", {}).get("bindings", [])
        out: list[dict[str, Any]] = []
        for row in bindings:
            parsed: dict[str, Any] = {}
            for key, cell in row.items():
                if "value" in cell:
                    parsed[key] = cell["value"]
            out.append(parsed)
        return out
    except (ValueError, AttributeError, TypeError) as exc:
        logger.warning("Wikidata parse error: %s", exc)
        return []


def lookup_by_domain(domain: str) -> dict[str, Any]:
    """Return profile fields and optional Wikidata entity id."""
    normalized = _normalize_domain(domain)
    if not normalized:
        return {}
    domain = normalized

    safe_domain = domain.replace('"', "")
    query = f"""
SELECT ?item ?itemLabel ?inception ?hqLabel ?employees ?desc WHERE {{
  ?item wdt:P856 ?website .
  FILTER(CONTAINS(LCASE(STR(?website)), "{safe_domain}"))
  OPTIONAL {{ ?item wdt:P571 ?inception. }}
  OPTIONAL {{
    ?item wdt:P159 ?hq .
    ?hq rdfs:label ?hqLabel .
    FILTER(LANG(?hqLabel) = "en")
  }}
  OPTIONAL {{ ?item wdt:P1128 ?employees. }}
  OPTIONAL {{
    ?item schema:description ?desc .
    FILTER(LANG(?desc) = "en")
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 3
"""
    rows = _sparql(query)
    if not rows:
        return {}

    row = rows[0]
    profile: dict[str, Any] = {
        "wikidata_id": row.get("item"),
        "wikidata_label": row.get("itemLabel"),
        "source_url": row.get("item")
        or f"https://www.wikidata.org/wiki/Special:Search?search={quote(domain)}",
    }
    inception = row.get("inception", "")
    if inception and len(inception) >= 4:
        year = inception[:4]
        if year.isdigit():
            profile["founded_year"] = int(year)
    if row.get("hqLabel"):
        profile["headquarters"] = row["hqLabel"]
    if row.get("employees"):
        try:
            profile["team_size"] = int(float(row["employees"]))
            profile["team_size_source"] = "wikidata"
        except (TypeError, ValueError):
            pass
    if row.get("desc"):
        profile["description_long"] = row["desc"][:4000]

    return profile


def lookup_key_people(wikidata_entity: str, limit: int = 8) -> list[dict[str, Any]]:
    """CEO / founder roles from Wikidata when entity id is known."""
    if not wikidata_entity or "wikidata.org/entity/" not in wikidata_entity:
        return []
    entity = wikidata_entity.rsplit("/", 1)[-1]
    if not entity.startswith("Q"):
        return []

    query = f"""
SELECT ?personLabel ?roleLabel WHERE {{
  VALUES ?company {{ wd:{entity} }}
  {{
    ?company p:P169 ?stmt . ?stmt ps:P169 ?person .
    BIND("CEO" AS ?roleLabel)
  }} UNION {{
    ?company p:P112 ?stmt . ?stmt ps:P112 ?person .
    BIND("Founder" AS ?roleLabel)
  }} UNION {{
    ?company p:P1037 ?stmt . ?stmt ps:P1037 ?person .
    ?person rdfs:label ?personLabel .
    BIND("Director" AS ?roleLabel)
  }}
  ?person rdfs:label ?personLabel .
  FILTER(LANG(?personLabel) = "en")
}}
LIMIT {int(limit)}
"""
    rows = _sparql(query)
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        name = (row.get("personLabel") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        role = (row.get("roleLabel") or "").strip() or None
        people.append(
            {
                "name": name,
                "role": role,
                "is_founder": bool(role and "founder" in role.lower()),
                "source_url": f"{wikidata_entity}#person-{quote(name)}",
                "extraction_confidence": 0.72,
            }
        )
    return people
