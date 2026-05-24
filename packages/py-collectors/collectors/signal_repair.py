#!/usr/bin/env python3
"""Repair intelligence_events linkage, dedupe, and funding labels."""

from __future__ import annotations

import logging

from db.connection import get_conn
from db.migrations import apply_runtime_migrations

from collectors.signal_company_resolver import (
    build_domain_index,
    resolve_company_enhanced,
)
from collectors.signal_processor import (
    UNLABELED_EVENT_TYPE,
    classify_for_storage,
    extract_amount,
    extract_signal_text,
    fuzzy_match_company,
    parse_signal_data,
    relink_orphan_companies,
    resolve_company_from_data,
)

logger = logging.getLogger("signal_repair")

_MONEY_MARKERS = (
    "million",
    "billion",
    "raised",
    "funding",
    "$",
    "series a",
    "seed round",
)


def dedupe_events_by_raw_signal(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT raw_signal_id, GROUP_CONCAT(id) AS ids
        FROM intelligence_events
        WHERE raw_signal_id IS NOT NULL
        GROUP BY raw_signal_id
        HAVING COUNT(*) > 1
        """
    )
    deleted = 0
    for _raw_id, id_csv in cur.fetchall():
        ids = [int(x) for x in id_csv.split(",")]
        keep = max(ids)
        for eid in ids:
            if eid != keep:
                cur.execute("DELETE FROM intelligence_events WHERE id = ?", (eid,))
                deleted += 1
    conn.commit()
    return deleted


def sync_company_from_raw_signals(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE intelligence_events
        SET company_id = (
            SELECT rs.company_id FROM raw_signals rs
            WHERE rs.id = intelligence_events.raw_signal_id
        )
        WHERE company_id IS NULL
          AND raw_signal_id IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM raw_signals rs
            WHERE rs.id = intelligence_events.raw_signal_id
              AND rs.company_id IS NOT NULL
          )
        """
    )
    n = cur.rowcount
    conn.commit()
    return n


def backfill_funding_amounts(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ie.id, ie.description, rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.event_type LIKE '%Funding%'
          AND COALESCE(ie.amount_usd, 0) = 0
        """
    )
    updated = 0
    for eid, desc, data_json in cur.fetchall():
        data = parse_signal_data(data_json) if data_json else {}
        text = (desc or "") + " " + extract_signal_text(data)
        amount = extract_amount(text)
        if amount:
            cur.execute(
                "UPDATE intelligence_events SET amount_usd = ? WHERE id = ?",
                (amount, eid),
            )
            updated += 1
    conn.commit()
    return updated


def reclassify_misfunded_events(conn) -> int:
    """Funding label without money signals in event + raw_signal text → General News."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ie.id, ie.description, rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.event_type LIKE '%Funding%'
          AND COALESCE(ie.amount_usd, 0) = 0
        """
    )
    updated = 0
    for eid, desc, data_json in cur.fetchall():
        data = parse_signal_data(data_json) if data_json else {}
        text = ((desc or "") + " " + extract_signal_text(data)).lower()
        if any(m in text for m in _MONEY_MARKERS):
            continue
        cur.execute(
            """
            UPDATE intelligence_events
            SET event_type = 'General News',
                confidence = MIN(COALESCE(confidence, 0.5), 0.4)
            WHERE id = ?
            """,
            (eid,),
        )
        updated += 1
    conn.commit()
    return updated


def _merged_event_text(
    description: str | None,
    data: dict,
) -> str:
    """Match signal_processor text merge for re-classification."""
    text = extract_signal_text(data)
    desc = (description or "").strip()
    if desc:
        if not text.strip():
            text = desc
        elif desc not in text:
            text = f"{desc} {text}".strip()
    url = (data.get("url") or data.get("link") or "").strip()
    if url and url not in text:
        text = f"{text} {url}".strip()
    return text


def reclassify_general_news_events(conn, *, min_confidence: float = 0.35) -> int:
    """Re-run keyword classifier on General News rows with merged text."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ie.id, ie.description, COALESCE(ie.source, rs.source, 'unknown'),
               rs.data_json, COALESCE(ie.amount_usd, 0)
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.event_type = 'General News'
        """
    )
    updated = 0
    for eid, desc, source, data_json, amount_usd in cur.fetchall():
        data = parse_signal_data(data_json) if data_json else {}
        text = _merged_event_text(desc, data)
        if not text.strip():
            continue
        event_type, _internal, confidence = classify_for_storage(text, source)
        if event_type == "General News" or confidence < min_confidence:
            continue
        amount = amount_usd or extract_amount(text)
        cur.execute(
            """
            UPDATE intelligence_events
            SET event_type = ?, confidence = ?, amount_usd = COALESCE(NULLIF(?, 0), amount_usd)
            WHERE id = ?
            """,
            (event_type, confidence, amount or 0, eid),
        )
        updated += 1
    conn.commit()
    return updated


def relabel_minimal_general_news(conn, *, max_merged_len: int = 25) -> int:
    """
    Feed stubs (title-only or empty description) mis-tagged as General News → Unlabeled.

    Uses the same merged text as signal_processor / reclassify_general_news_events.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ie.id, ie.description, COALESCE(ie.source, rs.source, 'unknown'), rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.event_type = 'General News'
        """
    )
    updated = 0
    for eid, desc, _source, data_json in cur.fetchall():
        data = parse_signal_data(data_json) if data_json else {}
        text = _merged_event_text(desc, data)
        if len(text.strip()) >= max_merged_len:
            continue
        cur.execute(
            """
            UPDATE intelligence_events
            SET event_type = ?, confidence = 0.0
            WHERE id = ?
            """,
            (UNLABELED_EVENT_TYPE, eid),
        )
        updated += 1
    conn.commit()
    return updated


def seed_company_identifiers(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS company_identifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            id_type TEXT NOT NULL,
            id_value TEXT NOT NULL,
            UNIQUE(id_type, id_value),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
        """
    )
    from collectors.signal_company_resolver import extract_domain

    cur.execute("SELECT id, website, slug, x_handle, github_org FROM companies")
    inserted = 0
    for cid, website, slug, handle, gh in cur.fetchall():
        pairs = []
        dom = extract_domain(website or "")
        if dom:
            pairs.append(("domain", dom))
        if slug:
            pairs.append(("alias", slug.lower()))
        if handle:
            pairs.append(("alias", handle.lower().lstrip("@")))
        if gh:
            pairs.append(("github", gh.lower()))
        for id_type, id_value in pairs:
            try:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO company_identifiers (company_id, id_type, id_value)
                    VALUES (?, ?, ?)
                    """,
                    (cid, id_type, id_value),
                )
                if cur.rowcount:
                    inserted += 1
            except Exception:
                pass
    conn.commit()
    return inserted


def ensure_indexes(conn) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT raw_signal_id FROM intelligence_events
            WHERE raw_signal_id IS NOT NULL
            GROUP BY raw_signal_id HAVING COUNT(*) > 1
        )
        """
    )
    if cur.fetchone()[0] > 0:
        return 0
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_intel_raw_signal_unique
        ON intelligence_events(raw_signal_id)
        WHERE raw_signal_id IS NOT NULL
        """
    )
    conn.commit()
    return 1


def relink_actionable_orphans(batch_size: int = 500) -> dict[str, int]:
    """Relink events whose text names a tracked company but company_id is null."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT LOWER(name) FROM companies WHERE LENGTH(name) >= 4")
    names = [r[0] for r in cur.fetchall()]
    if not names:
        conn.close()
        return {"candidates": 0, "updated": 0}

    cur.execute(
        """
        SELECT ie.id, ie.description, rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        WHERE ie.company_id IS NULL
        LIMIT ?
        """,
        (batch_size * 3,),
    )
    rows = cur.fetchall()
    domain_index = build_domain_index(cur)
    updated = 0
    candidates = 0

    for event_id, description, data_json in rows:
        blob = (description or "").lower()
        data = parse_signal_data(data_json)
        blob += (
            " "
            + " ".join(
                str(data.get(k, ""))
                for k in ("title", "headline", "description", "summary", "content")
            ).lower()
        )
        if not any(n in blob for n in names):
            continue
        candidates += 1
        matched = resolve_company_enhanced(
            data,
            cur,
            domain_index=domain_index,
            fuzzy_match_fn=fuzzy_match_company,
            resolve_from_data_fn=resolve_company_from_data,
        )
        if not matched:
            continue
        cid = matched[0]
        cur.execute(
            "UPDATE intelligence_events SET company_id = ? WHERE id = ?",
            (cid, event_id),
        )
        if data_json:
            cur.execute(
                """
                UPDATE raw_signals SET company_id = ?
                WHERE id = (SELECT raw_signal_id FROM intelligence_events WHERE id = ?)
                  AND company_id IS NULL
                """,
                (cid, event_id),
            )
        updated += 1
        if updated >= batch_size:
            break

    conn.commit()
    conn.close()
    return {"candidates": candidates, "updated": updated}


def run() -> dict[str, int]:
    conn = get_conn()
    apply_runtime_migrations(conn)
    conn.commit()

    stats = {
        "deduped": dedupe_events_by_raw_signal(conn),
        "synced_from_raw": sync_company_from_raw_signals(conn),
        "relinked": 0,
        "amounts_backfilled": backfill_funding_amounts(conn),
        "reclassified": reclassify_misfunded_events(conn),
        "general_news_reclassified": reclassify_general_news_events(conn),
        "minimal_general_unlabeled": relabel_minimal_general_news(conn),
        "identifiers_seeded": seed_company_identifiers(conn),
    }
    try:
        ensure_indexes(conn)
    except Exception as exc:
        logger.warning("Index create skipped: %s", exc)

    for _ in range(50):
        batch = relink_orphan_companies(500)
        stats["relinked"] += batch["updated"]
        if batch["candidates"] == 0:
            break

    conn.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO)
    if args and args[0] == "actionable":
        stats = relink_actionable_orphans()
        logger.info("Actionable relink: %s", stats)
        return 0
    stats = run()
    logger.info("Signal repair: %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
