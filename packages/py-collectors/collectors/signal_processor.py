#!/usr/bin/env python3
"""Process raw_signals into intelligence_events (classification, dedup, company match)."""

import ast
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from typing import Any, TypedDict

from db.connection import get_conn

from collectors.funding_parse import parse_amount_usd as extract_amount
from collectors.signal_company_resolver import build_domain_index, resolve_company_enhanced

logger = logging.getLogger("signal_processor")

# Every raw_signal must produce an intelligence_events row; event_type is the label.
UNLABELED_EVENT_TYPE = "Unlabeled Signal"


class _EventPattern(TypedDict):
    keywords: list[str]
    weight: float
    min_confidence: float


EVENT_PATTERNS: dict[str, _EventPattern] = {
    "funding": {
        "keywords": [
            "raised",
            "raises",
            "funding",
            "series a",
            "series b",
            "series c",
            "seed",
            "investment",
            "million",
            "billion",
            "valuation",
            "round",
            "closes",
            "secured",
            "led by",
            "round closed",
        ],
        "weight": 1.0,
        "min_confidence": 0.45,
    },
    "product_launch": {
        "keywords": [
            "launch",
            "launches",
            "launched",
            "announced a",
            "announced its",
            "announced the",
            "announced new",
            "released a",
            "released its",
            "released new",
            "new product",
            "new feature",
            "introducing",
            "unveiled",
            "now available",
            "shipped",
            "rolled out",
        ],
        "weight": 0.85,
        "min_confidence": 0.32,
    },
    "partnership": {
        "keywords": [
            "partnership",
            "partners with",
            "partnered",
            "collaboration",
            "teams up with",
            "teamed up with",
            "joins forces",
            "alliance",
            "integrates with",
            "works with",
            "deals with",
        ],
        "weight": 0.75,
        "min_confidence": 0.32,
    },
    "acquisition": {
        "keywords": [
            "acquired",
            "acquisition",
            "acquires",
            "acquire",
            "buys",
            "bought",
            "purchased",
            "merger",
            "buys out",
            "takes over",
        ],
        "weight": 0.95,
        "min_confidence": 0.32,
    },
    "hiring": {
        "keywords": [
            "hires",
            "hired",
            "joined",
            "appointed",
            "new ceo",
            "new cto",
            "executive",
            "talent",
            "recruiting",
            "head of",
        ],
        "weight": 0.75,
        "min_confidence": 0.32,
    },
    "research": {
        "keywords": [
            "paper",
            "research",
            "study",
            "arxiv",
            "published",
            "findings",
            "benchmark",
            "model release",
            "dataset",
            "reveals",
        ],
        "weight": 0.6,
        "min_confidence": 0.3,
    },
    "general": {
        "keywords": [],
        "weight": 1.0,
        "min_confidence": 0.28,
    },
}

SIGNAL_TEXT_KEYS = (
    "title",
    "description",
    "summary",
    "text",
    "content",
    "body",
    "headline",
    "name",
)

SOURCE_RELIABILITY = {
    "crunchbase": 0.9,
    "techcrunch": 0.85,
    "hackernews": 0.75,
    "producthunt": 0.8,
    "rss": 0.7,
    "article": 0.78,
    "x": 0.6,
    "github": 0.7,
    "youtube": 0.65,
    "angellist": 0.8,
    "website": 0.65,
}


def parse_signal_data(data_json: str | None) -> dict[str, Any]:
    """Parse raw_signals.data_json (JSON or legacy Python repr)."""
    if not data_json:
        return {}
    try:
        parsed = json.loads(data_json)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(data_json)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, SyntaxError):
            logger.debug("Unparseable data_json for signal payload")
            return {}


def extract_signal_text(data: dict[str, Any]) -> str:
    parts = [str(data[key]) for key in SIGNAL_TEXT_KEYS if data.get(key)]
    return " ".join(parts).strip()


def normalize_source(source: str) -> str:
    """Map feed display names / URLs to SOURCE_RELIABILITY keys."""
    s = (source or "").strip().lower()
    if "techcrunch" in s:
        return "techcrunch"
    if "hacker" in s or s == "hn":
        return "hackernews"
    if "producthunt" in s or "product hunt" in s:
        return "producthunt"
    if "crunchbase" in s:
        return "crunchbase"
    if "github" in s:
        return "github"
    if "youtube" in s:
        return "youtube"
    if "angellist" in s or "angel list" in s:
        return "angellist"
    if "website" in s:
        return "website"
    if s.startswith("http") or "feed" in s or "rss" in s:
        return "rss"
    return s or "rss"


def levenshtein(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    rows = len(a) + 1
    cols = len(b) + 1
    dist = list(range(cols))
    for i in range(1, rows):
        prev = dist[0]
        dist[0] = i
        for j in range(1, cols):
            temp = dist[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dist[j] = min(dist[j] + 1, dist[j - 1] + 1, prev + cost)
            prev = temp
    return 1.0 - dist[-1] / max(len(a), len(b))


COMPANY_ALIASES: dict[str, str] = {}
_aliases_loaded = False


def load_aliases(cursor: sqlite3.Cursor) -> dict[str, str]:
    global _aliases_loaded, COMPANY_ALIASES
    if _aliases_loaded:
        return COMPANY_ALIASES
    cursor.execute("SELECT id, name, slug, x_handle FROM companies")
    for row in cursor.fetchall():
        cid, name, slug, handle = row
        canonical = name.lower()
        COMPANY_ALIASES[canonical] = canonical
        if slug:
            COMPANY_ALIASES[slug.lower()] = canonical
        if handle:
            COMPANY_ALIASES[handle.lower().lstrip("@")] = canonical
        for token in canonical.replace("-", " ").replace("_", " ").split():
            if len(token) > 3:
                COMPANY_ALIASES[token] = canonical
    _aliases_loaded = True
    return COMPANY_ALIASES


def resolve_company_from_data(
    data: dict[str, Any],
    cursor: sqlite3.Cursor,
) -> tuple[int, str, float] | None:
    channel_company = data.get("channel_company") or data.get("channel")
    if channel_company:
        matched = fuzzy_match_company(str(channel_company), cursor)
        if matched:
            return matched

    for key in ("mentioned_companies", "companies_detected", "companies"):
        items = data.get(key) or []
        if isinstance(items, str):
            items = [items]
        for item in items:
            matched = fuzzy_match_company(str(item), cursor)
            if matched:
                return matched

    title = (data.get("title") or "").lower()
    if not title:
        return None

    aliases = load_aliases(cursor)
    best: tuple[int, str, float] | None = None
    best_len = 0
    for alias, canonical in aliases.items():
        if len(alias) < 4 or alias not in title:
            continue
        cursor.execute("SELECT id, name FROM companies WHERE LOWER(name) = ?", (canonical,))
        row = cursor.fetchone()
        if row and len(alias) > best_len:
            best = (row[0], row[1], 0.9)
            best_len = len(alias)
    return best


def _word_boundary_name_match(needle: str, haystack: str) -> bool:
    """True when needle appears as a whole token in haystack (not naive substring)."""
    if len(needle) < 2:
        return False
    return re.search(rf"\b{re.escape(needle)}\b", haystack, re.IGNORECASE) is not None


def fuzzy_match_company(name: str, cursor: sqlite3.Cursor) -> tuple[int, str, float] | None:
    if not name or len(name) < 2:
        return None
    aliases = load_aliases(cursor)
    name_lower = name.lower().strip()
    if name_lower in aliases:
        canonical = aliases[name_lower]
        cursor.execute("SELECT id, name FROM companies WHERE LOWER(name) = ?", (canonical,))
        row = cursor.fetchone()
        if row:
            return row[0], row[1], 1.0
    cursor.execute("SELECT id, name FROM companies")
    best_score = 0.0
    best_match = None
    for row in cursor.fetchall():
        cid, cname = row
        cname_lower = cname.lower()
        if cname_lower == name_lower:
            return cid, cname, 1.0
        if _word_boundary_name_match(cname_lower, name_lower) or _word_boundary_name_match(
            name_lower, cname_lower
        ):
            score = len(cname_lower) / max(len(name_lower), len(cname_lower))
            if score > best_score:
                best_score = score
                best_match = (cid, cname, score)
        lev = levenshtein(name_lower, cname_lower)
        if lev > best_score and lev > 0.75:
            best_score = lev
            best_match = (cid, cname, lev)
    if best_score > 0.6:
        return best_match
    return None


def _keyword_matches(text_lower: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text_lower
    stem = keyword.rstrip("e")
    pattern = rf"\b(?:{re.escape(keyword)}|{re.escape(stem)}(?:s|ed|ing)?)\b"
    return re.search(pattern, text_lower, re.IGNORECASE) is not None


def classify_event(text: str, source: str) -> tuple[str, float]:
    text_lower = text.lower()
    reliability = SOURCE_RELIABILITY.get(normalize_source(source), 0.55)
    scores: dict[str, float] = {}
    for event_type, config in EVENT_PATTERNS.items():
        if event_type == "general":
            continue
        keywords = config["keywords"]
        matches = sum(1 for kw in keywords if _keyword_matches(text_lower, kw))
        if matches == 0:
            continue
        keyword_score = min(0.55 + 0.22 * matches, 1.0)
        scores[event_type] = keyword_score * reliability * config["weight"]
    if not scores:
        floor = EVENT_PATTERNS["general"]["min_confidence"]
        return "general", max(floor, 0.35 * reliability)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best, best_score = ranked[0]
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 0.06:
        # Prefer specific label when top two are close but winner has a strong keyword hit.
        if ranked[0][1] >= EVENT_PATTERNS[ranked[0][0]]["min_confidence"]:
            best, best_score = ranked[0]
        else:
            best = "general"
            best_score = max(EVENT_PATTERNS["general"]["min_confidence"], 0.35 * reliability)
    if extract_amount(text) and scores.get("funding", 0) >= best_score * 0.65:
        best = "funding"
        best_score = scores["funding"]
    min_conf = EVENT_PATTERNS[best]["min_confidence"]
    if best_score < min_conf:
        return "general", max(EVENT_PATTERNS["general"]["min_confidence"], best_score)
    return best, best_score


def event_type_label(internal_type: str) -> str:
    """Map classifier keys to dashboard event_type labels."""
    return {
        "funding": "Funding Round",
        "product_launch": "Product Launch",
        "partnership": "Partnership",
        "acquisition": "Acquisition",
        "hiring": "Hiring",
        "research": "Research Publication",
        "general": "General News",
    }.get(internal_type, internal_type.replace("_", " ").title())


def is_duplicate(
    cursor: sqlite3.Cursor,
    event_type: str,
    company_id: int | None,
    source_url: str,
    window_days: int = 7,
) -> bool:
    if not company_id or not source_url:
        return False
    cursor.execute(
        """
        SELECT COUNT(*) FROM intelligence_events
        WHERE company_id = ? AND event_type = ?
          AND source_url = ?
          AND created_at >= datetime('now', ?)
        """,
        (company_id, event_type, source_url, f"-{window_days} days"),
    )
    return cursor.fetchone()[0] > 0


def link_existing_event_by_url(
    cursor: sqlite3.Cursor,
    source_url: str,
    raw_signal_id: int,
) -> bool:
    """Attach raw_signal_id when this article URL already has an unlinked event row."""
    if not source_url or source_url.startswith("raw_signal:"):
        return False
    cursor.execute(
        """
        SELECT id, raw_signal_id FROM intelligence_events
        WHERE source_url = ? OR source_url LIKE ? || '#%'
        ORDER BY (raw_signal_id IS NULL) DESC, id DESC
        LIMIT 1
        """,
        (source_url, source_url),
    )
    row = cursor.fetchone()
    if not row:
        return False
    event_id, existing_raw = row[0], row[1]
    if existing_raw == raw_signal_id:
        return True
    if existing_raw is not None:
        return False
    cursor.execute(
        "UPDATE intelligence_events SET raw_signal_id = ? WHERE id = ?",
        (raw_signal_id, event_id),
    )
    return cursor.rowcount > 0


def _try_link_on_url_conflict(
    cursor: sqlite3.Cursor,
    source_url: str,
    raw_signal_id: int,
) -> bool:
    cursor.execute(
        "SELECT id, raw_signal_id FROM intelligence_events WHERE source_url = ? LIMIT 1",
        (source_url,),
    )
    row = cursor.fetchone()
    if not row:
        return False
    event_id, existing_raw = row[0], row[1]
    if existing_raw == raw_signal_id:
        return True
    if existing_raw is None:
        cursor.execute(
            "UPDATE intelligence_events SET raw_signal_id = ? WHERE id = ?",
            (raw_signal_id, event_id),
        )
        return cursor.rowcount > 0
    return False


def resolve_source_url(
    data: dict[str, Any],
    sig_id: int,
    company_id: int | None,
) -> str:
    """Canonical URL for insert; suffix when multiple signals share one article."""
    base = (data.get("url") or data.get("link") or "").strip()
    if not base:
        return f"raw_signal:{sig_id}"
    if company_id:
        return f"{base}#c{company_id}-rs{sig_id}"
    return f"{base}#rs{sig_id}"


def fallback_signal_text(
    data: dict[str, Any],
    source: str,
    signal_type: str,
    sig_id: int,
) -> str:
    """Minimal text so empty payloads still get a label."""
    for key in ("url", "link", "id", "kind", "category"):
        if data.get(key):
            return f"{source} {signal_type} {data[key]}"
    return f"{source} {signal_type} signal-{sig_id}"


def classify_for_storage(text: str, source: str) -> tuple[str, str, float]:
    """
    Return (dashboard event_type label, internal key, confidence). Never drops.

    Deterministic keyword classifier for the batch pipeline (daily_intel / worker).
    Semantic RAG uses Ollama embeddings + rerank in this repo; Hermes + Grok handle
    agent orchestration, synthesis, and X ingest (see docs/architecture/HERMES_INTEGRATION.md).
    """
    internal, confidence = classify_event(text, source)
    return event_type_label(internal), internal, confidence


def _event_exists_for_signal(cursor: sqlite3.Cursor, sig_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM intelligence_events WHERE raw_signal_id = ? LIMIT 1",
        (sig_id,),
    )
    return cursor.fetchone() is not None


def _insert_intelligence_event(
    cursor: sqlite3.Cursor,
    *,
    company_id: int | None,
    event_type: str,
    amount: int | None,
    source: str,
    source_url: str,
    sig_id: int,
    confidence: float,
    announced: str,
    description: str | None = None,
) -> bool:
    cursor.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url,
         raw_signal_id, confidence, description, announced_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            event_type,
            amount,
            source,
            source_url,
            sig_id,
            confidence,
            description,
            announced,
            announced,
        ),
    )
    return True


def process_signals(batch_size: int = 500) -> dict[str, Any]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, company_id, source, signal_type, data_json, detected_at
        FROM raw_signals
        WHERE processed = 0
           OR NOT EXISTS (
               SELECT 1 FROM intelligence_events ie
               WHERE ie.raw_signal_id = raw_signals.id
           )
        ORDER BY detected_at DESC
        LIMIT ?
        """,
        (batch_size,),
    )
    signals = cursor.fetchall()
    domain_index = build_domain_index(cursor)
    processed = 0
    created = 0
    skipped = 0
    for signal in signals:
        sig_id, company_id, source, signal_type, data_json, detected_at = signal
        if _event_exists_for_signal(cursor, sig_id):
            cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
            processed += 1
            continue
        data = parse_signal_data(data_json)
        text = extract_signal_text(data)
        if not text.strip():
            text = fallback_signal_text(data, source, signal_type, sig_id)
        url_hint = (data.get("url") or data.get("link") or "").strip()
        if url_hint and url_hint not in text:
            text = f"{text} {url_hint}".strip()
        if not company_id:
            matched = resolve_company_enhanced(
                data,
                cursor,
                domain_index=domain_index,
                fuzzy_match_fn=fuzzy_match_company,
                resolve_from_data_fn=resolve_company_from_data,
            )
            if matched:
                company_id, _matched_company, _match_score = matched
                cursor.execute(
                    "UPDATE raw_signals SET company_id = ? WHERE id = ?",
                    (company_id, sig_id),
                )

        event_type, _internal, confidence = classify_for_storage(text, source)
        if not text.strip():
            event_type = UNLABELED_EVENT_TYPE
            confidence = 0.0

        base_url = (data.get("url") or data.get("link") or "").strip()
        source_url = resolve_source_url(data, sig_id, company_id)
        amount = extract_amount(text)
        announced = detected_at or datetime.now(UTC).isoformat()
        description = text[:500] if text else None

        saved = False
        if base_url and link_existing_event_by_url(cursor, base_url, sig_id):
            saved = True
        else:
            for attempt_url in (source_url, f"raw_signal:{sig_id}"):
                try:
                    _insert_intelligence_event(
                        cursor,
                        company_id=company_id,
                        event_type=event_type,
                        amount=amount,
                        source=source,
                        source_url=attempt_url,
                        sig_id=sig_id,
                        confidence=confidence,
                        announced=announced,
                        description=description,
                    )
                    created += 1
                    saved = True
                    break
                except sqlite3.IntegrityError:
                    if _try_link_on_url_conflict(cursor, attempt_url, sig_id):
                        saved = True
                        break
                    continue
                except Exception as e:
                    logger.warning("Failed to insert event for signal %s: %s", sig_id, e)
                    break

        if saved or _event_exists_for_signal(cursor, sig_id):
            cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
        else:
            skipped += 1
        processed += 1
    conn.commit()
    conn.close()
    logger.info("Processed %d signals, created %d events, skipped %d", processed, created, skipped)
    return {"processed": processed, "created": created, "skipped": skipped}


def process_all_signals(batch_size: int = 100) -> dict[str, Any]:
    return process_signals(batch_size=batch_size)


def backfill_all_signals(max_batches: int = 200) -> dict[str, Any]:
    total = {"processed": 0, "created": 0, "skipped": 0, "batches": 0}
    stall_rounds = 0
    while total["batches"] < max_batches:
        batch = process_signals(batch_size=100)
        if batch["processed"] == 0:
            break
        total["batches"] += 1
        for key in ("processed", "created", "skipped"):
            total[key] += batch.get(key, 0)
        if batch.get("created", 0) == 0:
            stall_rounds += 1
            if stall_rounds >= 3:
                logger.warning(
                    "Backfill stalled (no new events in %s batches); stopping",
                    stall_rounds,
                )
                break
        else:
            stall_rounds = 0
    logger.info(
        "Backfill complete: processed=%s created=%s skipped=%s",
        total["processed"],
        total["created"],
        total["skipped"],
    )
    return total


def relink_orphan_companies(batch_size: int = 500) -> dict[str, int]:
    """Backfill company_id on events linked to raw_signals but missing company."""
    conn = get_conn()
    cur = conn.cursor()
    domain_index = build_domain_index(cur)
    cur.execute(
        """
        SELECT ie.id, rs.data_json
        FROM intelligence_events ie
        JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.company_id IS NULL
        LIMIT ?
        """,
        (batch_size,),
    )
    rows = cur.fetchall()
    updated = 0
    for event_id, data_json in rows:
        data = parse_signal_data(data_json)
        matched = resolve_company_enhanced(
            data,
            cur,
            domain_index=domain_index,
            fuzzy_match_fn=fuzzy_match_company,
            resolve_from_data_fn=resolve_company_from_data,
        )
        if matched:
            cid = matched[0]
            cur.execute(
                "UPDATE intelligence_events SET company_id = ? WHERE id = ?",
                (cid, event_id),
            )
            cur.execute(
                """
                UPDATE raw_signals SET company_id = ?
                WHERE id = (SELECT raw_signal_id FROM intelligence_events WHERE id = ?)
                  AND company_id IS NULL
                """,
                (cid, event_id),
            )
            updated += 1
    conn.commit()
    conn.close()
    return {"candidates": len(rows), "updated": updated}


def run(batch_size: int = 1000) -> int:
    result = process_signals(batch_size=batch_size)
    return result["created"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_all_signals()
