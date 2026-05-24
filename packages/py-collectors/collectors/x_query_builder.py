"""
Build X search queries from pipeline state (labels, companies, claims).

Used after daily/frequent collectors so full-sweep can run targeted Hermes x_search
instead of only static registry queries.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from db.connection import get_conn

from collectors.sources_registry import get_x_monitor_queries

logger = logging.getLogger("x_query_builder")

_EVENT_X_FRAGMENTS: dict[str, str] = {
    "funding": '(raised OR funding OR "Series A" OR seed)',
    "product_launch": "(launch OR launched OR announces OR unveiled)",
    "acquisition": "(acquires OR acquisition OR acquired)",
    "hiring": "(hiring OR hires OR joined OR appoints)",
    "partnership": "(partnership OR partners OR integrates)",
}

_DEFAULT_FRAGMENT = "(funding OR launch OR raised OR hiring)"


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _days_back() -> int:
    raw = os.environ.get("CI_X_QUERY_LOOKBACK_DAYS", "7").strip()
    try:
        return max(1, min(30, int(raw)))
    except ValueError:
        return 7


def _since_clause(days: int) -> str:
    start = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    return f"since:{start}"


def _sanitize_query(q: str, *, max_len: int = 220) -> str:
    q = " ".join((q or "").split())
    if len(q) > max_len:
        q = q[: max_len - 3].rstrip() + "..."
    return q


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        q = _sanitize_query(q)
        if not q or len(q) < 8:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def _event_fragment(event_type: str) -> str:
    et = (event_type or "").strip().lower().replace(" ", "_")
    for key, frag in _EVENT_X_FRAGMENTS.items():
        if key in et:
            return frag
    return _DEFAULT_FRAGMENT


def _parse_signal_json(data_json: str | None) -> dict[str, Any]:
    if not data_json:
        return {}
    try:
        data = json.loads(data_json)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def derive_queries_from_db(
    conn=None,
    *,
    lookback_days: int | None = None,
    max_derived: int | None = None,
    max_company: int | None = None,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """
    Return (targeted_queries, context_snippets, stats).

    targeted_queries: short X search strings from recent intel + tracked companies.
    context_snippets: bullets for optional AI query expansion.
    """
    days = lookback_days if lookback_days is not None else _days_back()
    max_derived = (
        max_derived
        if max_derived is not None
        else int(os.environ.get("CI_X_MAX_DERIVED_QUERIES", "10"))
    )
    max_company = (
        max_company
        if max_company is not None
        else int(os.environ.get("CI_X_MAX_COMPANY_QUERIES", "8"))
    )
    since = _since_clause(days)
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    cur = conn.cursor()
    targeted: list[str] = []
    snippets: list[str] = []
    stats: dict[str, Any] = {"lookback_days": days}

    # Recent classified events → company + label driven queries
    cur.execute(
        """
        SELECT c.name, ie.event_type, ie.description, ie.amount_usd, ie.announced_date
        FROM intelligence_events ie
        JOIN companies c ON c.id = ie.company_id
        WHERE COALESCE(ie.announced_date, ie.created_at, '') >= ?
        ORDER BY ie.confidence DESC, COALESCE(ie.announced_date, ie.created_at) DESC
        LIMIT 40
        """,
        (cutoff[:10],),
    )
    event_rows = cur.fetchall()
    stats["intel_events_scanned"] = len(event_rows)
    for name, event_type, description, amount_usd, _ann in event_rows:
        frag = _event_fragment(str(event_type or ""))
        q = f'"{name}" {frag} min_faves:3 {since}'
        targeted.append(q)
        desc = (description or "")[:200]
        amt = f" ${amount_usd:,}" if amount_usd else ""
        snippets.append(f"{name}: {event_type}{amt} — {desc}".strip(" —"))

    # High-signal raw_signals (titles + detected companies)
    cur.execute(
        """
        SELECT source, signal_type, data_json
        FROM raw_signals
        WHERE detected_at >= ?
        ORDER BY detected_at DESC
        LIMIT 60
        """,
        (cutoff,),
    )
    raw_rows = cur.fetchall()
    stats["raw_signals_scanned"] = len(raw_rows)
    for source, signal_type, data_json in raw_rows:
        data = _parse_signal_json(data_json)
        title = (data.get("title") or data.get("text") or "")[:160]
        if not title:
            continue
        companies = data.get("companies_detected") or []
        if isinstance(companies, list) and companies:
            for comp in companies[:2]:
                comp_s = str(comp).strip()
                if not comp_s or len(comp_s) < 2:
                    continue
                frag = _event_fragment(str(signal_type or ""))
                targeted.append(f'"{comp_s}" {frag} min_faves:3 {since}')
                snippets.append(f"{comp_s} ({source}): {title}")
        elif signal_type in ("funding", "product_launch", "acquisition", "hiring"):
            snippets.append(f"{source}/{signal_type}: {title}")

    # Tracked companies with X handles (activity-weighted)
    cur.execute(
        """
        SELECT c.name, c.x_handle,
               (SELECT COUNT(*) FROM intelligence_events ie
                WHERE ie.company_id = c.id AND ie.created_at >= ?) AS recent_events
        FROM companies c
        WHERE c.x_handle IS NOT NULL AND trim(c.x_handle) != ''
        ORDER BY recent_events DESC, c.name
        LIMIT ?
        """,
        (cutoff, max_company * 2),
    )
    company_rows = cur.fetchall()
    stats["companies_with_handle"] = len(company_rows)
    company_queries = 0
    for name, handle, _recent in company_rows:
        if company_queries >= max_company:
            break
        h = str(handle or "").lstrip("@").strip()
        if not h:
            continue
        targeted.append(f'(@{h} OR "{name}") {_DEFAULT_FRAGMENT} min_faves:2 {since}')
        company_queries += 1

    # Product claims → product + company searches
    try:
        cur.execute(
            """
            SELECT c.name, pc.name
            FROM product_claims pc
            JOIN companies c ON c.id = pc.company_id
            WHERE pc.extracted_at >= ?
            LIMIT 15
            """,
            (cutoff,),
        )
        for name, product in cur.fetchall():
            product_s = (product or "").strip()
            if len(product_s) < 3:
                continue
            targeted.append(f'"{name}" "{product_s}" (launch OR announces) min_faves:2 {since}')
            snippets.append(f"{name} product: {product_s}")
    except Exception:
        pass

    targeted = _dedupe_queries(targeted)[:max_derived]
    snippets = _dedupe_queries(snippets)[:25]
    stats["derived_count"] = len(targeted)
    stats["snippet_count"] = len(snippets)

    if own_conn:
        conn.close()
    return targeted, snippets, stats


def expand_queries_with_xai(
    snippets: list[str],
    *,
    max_extra: int | None = None,
) -> list[str]:
    """Optional Hermes/xAI chat pass to propose extra X search strings."""
    if not _env_truthy("CI_X_QUERY_AI_EXPAND"):
        return []
    max_extra = (
        max_extra if max_extra is not None else int(os.environ.get("CI_X_MAX_AI_QUERIES", "5"))
    )
    if not snippets or max_extra <= 0:
        return []

    from utils.http import post_json

    from collectors.grok_x_fetcher import resolve_xai_credentials

    key, base, provider = resolve_xai_credentials()
    url = f"{base.rstrip('/')}/chat/completions"
    model = os.environ.get("CI_X_QUERY_AI_MODEL", "grok-4-fast").strip()
    body = "\n".join(f"- {s}" for s in snippets[:25])
    prompt = (
        f"Given competitive-intel snippets from our pipeline, propose {max_extra} "
        "X.com search queries.\n"
        "Return ONLY a JSON array of strings. Each query must use X syntax "
        "(OR, quotes, min_faves:N, since:YYYY-MM-DD).\n"
        "Target funding, launches, acquisitions, hiring. No markdown.\n"
        "\n"
        "Snippets:\n"
        f"{body}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = post_json(url, payload, headers=headers, timeout=90.0)
    if not data:
        logger.warning("AI query expand: no response from xAI (%s)", provider)
        return []

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.warning("AI query expand: unexpected xAI response shape")
        return []

    text = str(content).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, list):
        return []
    out: list[str] = []
    for item in parsed:
        if isinstance(item, str):
            out.append(item)
    return _dedupe_queries(out)[:max_extra]


def build_query_payload(
    *,
    enriched: bool = True,
    conn=None,
) -> dict[str, Any]:
    """Build x_monitor_queries.json document."""
    baseline = get_x_monitor_queries()
    derived: list[str] = []
    ai_queries: list[str] = []
    snippets: list[str] = []
    stats: dict[str, Any] = {}

    if enriched:
        derived, snippets, stats = derive_queries_from_db(conn=conn)
        ai_queries = expand_queries_with_xai(snippets)

    global_queries = _dedupe_queries(list(baseline) + derived + ai_queries)
    return {
        "baseline_queries": baseline,
        "derived_queries": derived,
        "ai_queries": ai_queries,
        "global_queries": global_queries,
        "enriched": enriched,
        "build_stats": stats,
        "output_schema_note": (
            "Write Grok results to data/hermes_enrich/grok_x_results.json as "
            '[{"query": "...", "results": [{post_id, text, url, urls: [...]}, ...]}]'
        ),
    }


def queries_for_fetch(payload: dict[str, Any]) -> list[str]:
    """Ordered deduped list used by fetch_x / grok_x_fetcher."""
    if not payload:
        return get_x_monitor_queries()
    merged: list[str] = []
    for key in (
        "global_queries",
        "baseline_queries",
        "derived_queries",
        "targeted_queries",
        "ai_queries",
    ):
        for q in payload.get(key) or []:
            if isinstance(q, str):
                merged.append(q)
    if not merged:
        merged = list(get_x_monitor_queries())
    return _dedupe_queries(merged)


def load_queries_file(path: Path) -> list[str]:
    if not path.is_file():
        return get_x_monitor_queries()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return get_x_monitor_queries()
    return queries_for_fetch(data)
