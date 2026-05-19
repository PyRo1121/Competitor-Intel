#!/usr/bin/env python3
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("signal_processor_v2")

from db.connection import get_conn

EVENT_PATTERNS = {
    "funding": {
        "keywords": ["raised", "funding", "series a", "series b", "series c", "seed", "investment", "million", "billion", "valuation", "round"],
        "weight": 1.0,
        "min_confidence": 0.6,
    },
    "product_launch": {
        "keywords": ["launch", "announced", "released", "new product", "new feature", "introducing", "unveiled", "now available", "shipped"],
        "weight": 0.85,
        "min_confidence": 0.5,
    },
    "partnership": {
        "keywords": ["partnership", "collaboration", "teams up with", "joins forces", "alliance", "integrates with", "works with", "deals with"],
        "weight": 0.75,
        "min_confidence": 0.5,
    },
    "acquisition": {
        "keywords": ["acquired", "acquisition", "buys", "purchased", "merger", "buys out", "takes over"],
        "weight": 0.95,
        "min_confidence": 0.7,
    },
    "hiring": {
        "keywords": ["hires", "joined", "appointed", "new ceo", "new cto", "executive", "talent", "recruiting", "head of"],
        "weight": 0.6,
        "min_confidence": 0.5,
    },
    "research": {
        "keywords": ["paper", "research", "study", "arxiv", "published", "findings", "benchmark", "model release", "dataset"],
        "weight": 0.5,
        "min_confidence": 0.4,
    },
}

SOURCE_RELIABILITY = {
    "crunchbase": 0.9,
    "techcrunch": 0.85,
    "hackernews": 0.75,
    "producthunt": 0.8,
    "rss": 0.7,
    "x": 0.6,
    "github": 0.7,
    "youtube": 0.65,
    "angellist": 0.8,
}


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


COMPANY_ALIASES: Dict[str, str] = {}
_aliases_loaded = False


def load_aliases(cursor: sqlite3.Cursor) -> Dict[str, str]:
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
    data: Dict[str, Any],
    cursor: sqlite3.Cursor,
) -> Optional[Tuple[int, str, float]]:
    channel_company = data.get("channel_company") or data.get("channel")
    if channel_company:
        matched = fuzzy_match_company(str(channel_company), cursor)
        if matched:
            return matched

    for key in ("mentioned_companies", "companies_detected", "companies"):
        items = data.get(key) or []
        if items:
            matched = fuzzy_match_company(str(items[0]), cursor)
            if matched:
                return matched

    title = (data.get("title") or "").lower()
    if not title:
        return None

    aliases = load_aliases(cursor)
    best: Optional[Tuple[int, str, float]] = None
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


def fuzzy_match_company(name: str, cursor: sqlite3.Cursor) -> Optional[Tuple[int, str, float]]:
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
        if cname_lower in name_lower or name_lower in cname_lower:
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


def classify_event(text: str, source: str) -> Tuple[str, float]:
    text_lower = text.lower()
    scores = {}
    for event_type, config in EVENT_PATTERNS.items():
        matches = sum(1 for kw in config["keywords"] if kw in text_lower)
        if matches == 0:
            continue
        keyword_score = min(matches / 3, 1.0)
        source_reliability = SOURCE_RELIABILITY.get(source, 0.5)
        scores[event_type] = keyword_score * source_reliability * config["weight"]
    if not scores:
        return "general", 0.3
    best = max(scores, key=scores.get)
    return best, scores[best]


def extract_amount(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\$?([\d,.]+)\s*(billion|b)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1).replace(",", "")) * 1_000_000_000)
        except ValueError:
            pass
    m = re.search(r"\$?([\d,.]+)\s*(million|m)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1).replace(",", "")) * 1_000_000)
        except ValueError:
            pass
    m = re.search(r"\$([\d,]+)\b", text)
    if m:
        try:
            val = int(m.group(1).replace(",", ""))
            if val >= 100_000:
                return val
        except ValueError:
            pass
    return None


def is_duplicate(cursor: sqlite3.Cursor, event_type: str, company_id: Optional[int], text: str, window_days: int = 7) -> bool:
    if not company_id:
        return False
    snippet = text.lower().strip()[:120]
    cursor.execute(
        """
        SELECT COUNT(*) FROM intelligence_events
        WHERE company_id = ? AND event_type = ?
        AND created_at >= datetime('now', ?)
        AND LOWER(description) LIKE ?
        """,
        (company_id, event_type, f"-{window_days} days", f"%{snippet[:80]}%"),
    )
    return cursor.fetchone()[0] > 0


def process_signals(batch_size: int = 500) -> Dict[str, Any]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, company_id, source, signal_type, data_json, detected_at
        FROM raw_signals
        WHERE processed = 0
        ORDER BY detected_at DESC
        LIMIT ?
        """,
        (batch_size,),
    )
    signals = cursor.fetchall()
    processed = 0
    created = 0
    skipped = 0
    for signal in signals:
        sig_id, company_id, source, signal_type, data_json, detected_at = signal
        try:
            data = json.loads(data_json or "{}")
        except json.JSONDecodeError:
            data = {}
        text = data.get("title", "") + " " + data.get("description", "") + " " + data.get("text", "")
        if not text.strip():
            cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
            processed += 1
            continue
        matched_company = None
        if not company_id:
            matched = resolve_company_from_data(data, cursor)
            if matched:
                company_id, matched_company, _match_score = matched
        event_type, confidence = classify_event(text, source)
        config = EVENT_PATTERNS.get(event_type, {})
        min_conf = config.get("min_confidence", 0.5)
        if confidence < min_conf:
            cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
            processed += 1
            skipped += 1
            continue
        if company_id and is_duplicate(cursor, event_type, company_id, text):
            cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
            processed += 1
            skipped += 1
            continue
        amount = extract_amount(text)
        try:
            cursor.execute(
                """
                INSERT INTO intelligence_events
                (company_id, event_type, amount_usd, source, source_url, description, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    event_type,
                    amount,
                    source,
                    data.get("url") or data.get("link", ""),
                    text[:500],
                    confidence,
                    detected_at or datetime.now(timezone.utc).isoformat(),
                ),
            )
            created += 1
        except Exception as e:
            logger.warning("Failed to insert event: %s", e)
        cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
        processed += 1
    conn.commit()
    conn.close()
    logger.info("Processed %d signals, created %d events, skipped %d", processed, created, skipped)
    return {"processed": processed, "created": created, "skipped": skipped}


def run(batch_size: int = 1000) -> int:
    result = process_signals(batch_size=batch_size)
    return result["created"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
