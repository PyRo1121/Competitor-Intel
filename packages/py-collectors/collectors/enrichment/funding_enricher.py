#!/usr/bin/env python3
"""
Structured funding extraction: per-source claims + aggregated canonical rounds.

Each intelligence event / raw signal becomes a funding_round_claim (source of truth).
aggregate_funding_rounds() merges claims by company/round/amount/date and scores
corroboration (more independent outlets + official company sources = higher).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger("funding_enricher")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from collectors.funding_parse import parse_amount_usd as extract_amount
from db.connection import get_conn

from .funding_aggregator import FUNDING_EVENT_TYPES, aggregate_funding_rounds
from .funding_investors import sync_claim_participants
from .funding_source_trust import classify_source, headline_snippet

# Comprehensive round type patterns
ROUND_PATTERNS = [
    (r"(?:series|round)\s*([a-f])\+?", "Series {}"),
    (r"(?:seed|pre[- ]?seed)\s*(?:round)?", "Seed"),
    (r"(?:series|round)\s*([a-f])", "Series {}"),
    (r"(?:angel|pre[- ]?seed)", "Pre-Seed"),
    (r"(?:growth|late[- ]?stage)\s*(?:round)?", "Growth"),
    (r"(?:ipo|initial\s+public\s+offering)", "IPO"),
    (r"(?:private\s+placement)", "Private Placement"),
]

INVESTOR_KEYWORDS = [
    "led by",
    "led",
    "backed by",
    "investors include",
    "participated",
    "co-led by",
]


def extract_round_type(text: str) -> tuple[str | None, float]:
    text_lower = text.lower()
    for pattern, template in ROUND_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            if "{}" in template:
                return template.format(m.group(1).upper()), 0.9
            return template, 0.9
    if "funding" in text_lower or "raised" in text_lower:
        return "Funding Round", 0.6
    return None, 0.0


def extract_investors(text: str) -> tuple[str | None, list[str]]:
    text.lower()
    lead = None
    co_investors: list[str] = []

    m = re.search(
        r"co[- ]?led\s+by\s+([A-Z][A-Za-z0-9&\s]+?)\s+and\s+([A-Z][A-Za-z0-9&\s]+?)"
        r"(?:,|;|\.|\s+with\s+|\s+participation|\s+alongside|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        if 2 < len(a) < 60 and 2 < len(b) < 60:
            return a, [b]

    m = re.search(
        r"strategic\s+(?:investment|round|funding)\s+from\s+([A-Z][A-Za-z0-9&\s]+?)"
        r"(?:\.|,|;|\s+valued|\s+at\s+|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        name = m.group(1).strip()
        if 2 < len(name) < 60:
            return name, []

    for kw in ["led by", "co-led by", "backed by"]:
        pattern = (
            rf"{re.escape(kw)}\s+([A-Z][A-Za-z0-9&\s]+?)"
            r"(?:,|;|\.\s|and\s|with\s|participation|$)"
        )
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if 2 < len(name) < 60:
                if "co" in kw.lower():
                    co_investors.append(name)
                else:
                    lead = name
                break

    for kw in [
        "including",
        "participation from",
        "joined by",
        "along with",
        "with participation from",
        "existing investors",
    ]:
        pattern = (
            rf"{re.escape(kw)}\s+([A-Z][A-Za-z0-9&\s,]+?)"
            r"(?:\.\s|and\s|with\s|participation|$)"
        )
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if len(n.strip()) > 2]
            co_investors.extend(names[:5])

    m = re.search(
        r"with\s+([A-Z][A-Za-z0-9&\s]+?)\s+participating",
        text,
        re.IGNORECASE,
    )
    if m:
        co_investors.append(m.group(1).strip())

    m = re.search(
        r"participation from\s+([A-Z][A-Za-z0-9&\s,]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        names = [n.strip() for n in m.group(1).split(",") if len(n.strip()) > 2]
        co_investors.extend(names[:5])

    if not lead:
        m = re.search(
            r"(?:series\s+[a-f0-9+]+\s+|seed\s+|round\s+)?led\s+by\s+"
            r"([A-Z][A-Za-z0-9&\s]+?)(?:,|;|\.\s|with\s|participation|$)",
            text,
            re.IGNORECASE,
        )
        if m:
            name = m.group(1).strip()
            if 2 < len(name) < 60:
                lead = name

    if not lead and not co_investors:
        m = re.search(
            r"(?:raised|raises|secured|securing|closed|announced)\s+.+?\s+from\s+(.+?)"
            r"(?:\.|$|\s+valued|\s+at\s+\$)",
            text,
            re.IGNORECASE,
        )
        if m:
            names = [
                n.strip() for n in re.split(r",|\sand\s", m.group(1)) if 2 < len(n.strip()) < 60
            ]
            if names:
                lead = names[0]
                co_investors.extend(names[1:5])

    return lead, list(set(co_investors))[:5]


def extract_valuation(text: str) -> int | None:
    patterns = [
        r"valuation\s*(?:of|at)?\s*\$?\s*([\d,.]+)\s*(billion|b)",
        r"valued\s*(?:at|around)?\s*\$?\s*([\d,.]+)\s*(billion|b)",
        r"valuation\s*(?:of|at)?\s*\$?\s*([\d,.]+)\s*(million|m)",
        r"valued\s*(?:at|around)?\s*\$?\s*([\d,.]+)\s*(million|m)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                num = float(m.group(1).replace(",", ""))
                unit = m.group(2).lower()
                mult = 1_000_000_000 if unit.startswith("b") else 1_000_000
                return int(num * mult)
            except (ValueError, IndexError):
                continue
    return None


def extract_deal_fields(text: str) -> dict[str, str | int | None]:
    """Instrument type and pre/post-money hints from headline/body."""
    instrument = "equity"
    lower = text.lower()
    if re.search(r"\bsafe\b", lower):
        instrument = "safe"
    elif "convertible" in lower:
        instrument = "convertible_note"
    elif re.search(r"\b(debt|credit facility|venture debt|term loan)\b", lower):
        instrument = "debt"

    pre_money = None
    post_money = None
    m = re.search(
        r"pre[- ]?money\s+(?:valuation\s+)?(?:of\s+)?\$?([\d,.]+)\s*(million|billion|m|b)\b",
        text,
        re.I,
    )
    if m:
        pre_money = extract_amount(f"{m.group(1)} {m.group(2)}")
    if pre_money is None:
        m = re.search(
            r"\$?([\d,.]+)\s*(million|billion|m|b)\s+pre[- ]?money",
            text,
            re.I,
        )
        if m:
            pre_money = extract_amount(f"{m.group(1)} {m.group(2)}")
    m = re.search(
        r"post[- ]?money\s+(?:valuation\s+)?(?:of\s+)?\$?([\d,.]+)\s*(million|billion|m|b)\b",
        text,
        re.I,
    )
    if m:
        post_money = extract_amount(f"{m.group(1)} {m.group(2)}")

    return {
        "currency": "USD",
        "instrument_type": instrument,
        "pre_money_valuation_usd": pre_money,
        "post_money_valuation_usd": post_money,
    }


def parse_funding_event(
    _event_id: int,
    company_id: int | None,
    event_type: str,
    amount: int | None,
    text: str,
    source: str,
) -> dict | None:
    if not text:
        return None

    round_type, confidence = extract_round_type(text)
    funding_types = {t.lower() for t in FUNDING_EVENT_TYPES}
    if (
        not round_type
        and event_type.lower() not in {t.lower() for t in funding_types}
        and "fund" not in text.lower()
        and "raised" not in text.lower()
    ):
        return None

    round_type = round_type or event_type or "Funding Round"
    amount_usd = amount or extract_amount(text)
    valuation = extract_valuation(text)
    lead_investor, co_investors = extract_investors(text)

    if not amount_usd and not valuation and not lead_investor:
        return None

    deal = extract_deal_fields(text)
    return {
        "company_id": company_id,
        "round_type": round_type,
        "amount_usd": amount_usd,
        "valuation_usd": valuation
        or deal.get("post_money_valuation_usd")
        or deal.get("pre_money_valuation_usd"),
        "lead_investor": lead_investor,
        "co_investors": json.dumps(co_investors) if co_investors else None,
        "source": source,
        "confidence": confidence,
        "headline": headline_snippet(text, 200),
        "snippet": headline_snippet(text, 500),
        "currency": deal.get("currency"),
        "instrument_type": deal.get("instrument_type"),
        "pre_money_valuation_usd": deal.get("pre_money_valuation_usd"),
        "post_money_valuation_usd": deal.get("post_money_valuation_usd"),
        "deal_terms_text": headline_snippet(text, 800),
    }


def _company_website(company_id: int) -> str | None:
    conn = get_conn()
    row = conn.execute("SELECT website FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return row[0] if row else None


def store_funding_claim(data: dict) -> tuple[int | None, bool]:
    """Insert or refresh one source observation. Returns (claim_id, is_new)."""
    if not data.get("company_id"):
        return None, False

    source_url = (data.get("source_url") or "").strip()
    if not source_url:
        source_url = (
            f"intel:{data['company_id']}:{data['round_type']}:"
            f"{data.get('amount_usd') or 0}:{data.get('source', 'unknown')}"
        )

    company_id = int(data["company_id"])
    conn = get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT 1 FROM companies WHERE id = ?", (company_id,))
        if not cursor.fetchone():
            return None, False

        cursor.execute(
            "SELECT 1 FROM funding_round_claims WHERE source_url = ?",
            (source_url,),
        )
        existed = cursor.fetchone() is not None

        is_rumor = bool(data.get("is_rumor"))
        website = _company_website(company_id)
        tier, weight, is_official = classify_source(
            data.get("source"),
            source_url,
            company_website=website,
            is_rumor=is_rumor,
        )

        cursor.execute(
            """
            INSERT INTO funding_round_claims
            (company_id, intelligence_event_id, raw_signal_id, round_type,
             amount_usd, valuation_usd, lead_investor, co_investors,
             announced_date, source, source_url, source_tier, source_weight,
             is_official, is_rumor, extraction_confidence, headline, snippet,
             currency, pre_money_valuation_usd, post_money_valuation_usd,
             instrument_type, deal_terms_text, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET
                amount_usd = excluded.amount_usd,
                valuation_usd = excluded.valuation_usd,
                lead_investor = excluded.lead_investor,
                co_investors = excluded.co_investors,
                source_tier = excluded.source_tier,
                source_weight = excluded.source_weight,
                is_official = excluded.is_official,
                extraction_confidence = excluded.extraction_confidence,
                headline = excluded.headline,
                snippet = excluded.snippet,
                currency = excluded.currency,
                pre_money_valuation_usd = excluded.pre_money_valuation_usd,
                post_money_valuation_usd = excluded.post_money_valuation_usd,
                instrument_type = excluded.instrument_type,
                deal_terms_text = excluded.deal_terms_text,
                extracted_at = excluded.extracted_at
            """,
            (
                company_id,
                data.get("intelligence_event_id"),
                data.get("raw_signal_id"),
                data["round_type"],
                data.get("amount_usd"),
                data.get("valuation_usd"),
                data.get("lead_investor"),
                data.get("co_investors"),
                data.get("announced_date"),
                data.get("source"),
                source_url,
                tier,
                weight,
                1 if is_official else 0,
                1 if is_rumor else 0,
                data.get("confidence", 0.7),
                data.get("headline"),
                data.get("snippet"),
                data.get("currency", "USD"),
                data.get("pre_money_valuation_usd"),
                data.get("post_money_valuation_usd"),
                data.get("instrument_type"),
                data.get("deal_terms_text"),
                datetime.now().isoformat(),
            ),
        )
        cursor.execute(
            "SELECT id FROM funding_round_claims WHERE source_url = ?",
            (source_url,),
        )
        row = cursor.fetchone()
        claim_id = int(row[0]) if row else None
        conn.commit()
        return claim_id, not existed
    except sqlite3.Error as e:
        logger.error("DB error storing funding claim: %s", e)
        return None, False
    finally:
        conn.close()


def store_funding_round(data: dict) -> bool:
    """Backward-compatible alias: writes a claim; True if newly created."""
    claim_id, is_new = store_funding_claim(data)
    if claim_id:
        sync_claim_participants(claim_id, data)
    return bool(claim_id and is_new)


def extract_from_signals() -> dict:
    """Extract claims from events/signals, then aggregate into funding_rounds."""
    from db.migrations import apply_runtime_migrations

    conn = get_conn()
    apply_runtime_migrations(conn)
    conn.close()

    conn = get_conn()
    cursor = conn.cursor()

    placeholders = ",".join("?" * len(FUNDING_EVENT_TYPES))
    cursor.execute(
        f"""
        SELECT id, company_id, event_type, amount_usd, source, raw_signal_id,
               description, source_url, announced_date
        FROM intelligence_events
        WHERE event_type IN ({placeholders})
          AND company_id IS NOT NULL
        ORDER BY created_at DESC
        """,
        FUNDING_EVENT_TYPES,
    )
    events = cursor.fetchall()

    cursor.execute(
        """
        SELECT id, company_id, source, data_json
        FROM raw_signals
        WHERE data_json LIKE '%raised%' OR data_json LIKE '%funding%'
           OR data_json LIKE '%million%' OR data_json LIKE '%billion%'
        ORDER BY detected_at DESC
        LIMIT 300
        """
    )
    signals = cursor.fetchall()
    conn.close()

    claims_created = 0
    claims_skipped = 0

    for row in events:
        signal_id = row["raw_signal_id"]
        text = row["description"] or ""

        if signal_id:
            conn = get_conn()
            sig_row = conn.execute(
                "SELECT data_json FROM raw_signals WHERE id = ?", (signal_id,)
            ).fetchone()
            conn.close()
            if sig_row:
                try:
                    payload = json.loads(sig_row["data_json"])
                    text = f"{text} {payload.get('title', '')} {payload.get('summary', '')}"
                except json.JSONDecodeError:
                    text = f"{text} {sig_row['data_json']}"

        funding_data = parse_funding_event(
            row["id"],
            row["company_id"],
            row["event_type"],
            row["amount_usd"],
            text,
            row["source"],
        )
        if not funding_data:
            continue

        funding_data["source_url"] = row["source_url"]
        funding_data["announced_date"] = row["announced_date"]
        funding_data["intelligence_event_id"] = row["id"]
        funding_data["raw_signal_id"] = signal_id
        text_lower = text.lower()
        funding_data["is_rumor"] = row["event_type"] == "Rumored Round" or any(
            kw in text_lower for kw in ("rumor", "rumoured", "rumored", "reportedly", "sources say")
        )

        claim_id, is_new = store_funding_claim(funding_data)
        if claim_id:
            sync_claim_participants(claim_id, funding_data)
            if is_new:
                claims_created += 1
            else:
                claims_skipped += 1
        else:
            claims_skipped += 1

    for row in signals:
        try:
            payload = json.loads(row["data_json"])
            text = f"{payload.get('title', '')} {payload.get('summary', '')}"
            url = payload.get("url") or payload.get("link")
        except json.JSONDecodeError:
            text = str(row["data_json"])
            url = None

        funding_data = parse_funding_event(
            row["id"], row["company_id"], "Funding Round", None, text, row["source"]
        )
        if not funding_data:
            continue
        if url:
            funding_data["source_url"] = url
        funding_data["raw_signal_id"] = row["id"]

        claim_id, is_new = store_funding_claim(funding_data)
        if claim_id:
            sync_claim_participants(claim_id, funding_data)
            if is_new:
                claims_created += 1
            else:
                claims_skipped += 1
        else:
            claims_skipped += 1

    backfill = backfill_claim_participants_from_text()
    deal_backfill = backfill_deal_fields_from_text()

    agg = aggregate_funding_rounds()
    logger.info(
        "Funding pipeline: claims_created=%s claims_skipped=%s "
        "participants_backfill=%s deal_backfill=%s %s",
        claims_created,
        claims_skipped,
        backfill,
        deal_backfill,
        agg,
    )
    return {
        "created": claims_created,
        "skipped": claims_skipped,
        "claims_created": claims_created,
        "claims_skipped": claims_skipped,
        "participants_backfill": backfill,
        "deal_fields_backfill": deal_backfill,
        **agg,
    }


def backfill_claim_participants_from_text() -> dict[str, int]:
    """
    Re-parse headline/snippet on existing claims, update lead/co fields, sync
    funding_claim_participants and re-aggregate round rosters.
    """
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, lead_investor, co_investors, headline, snippet
        FROM funding_round_claims
        """
    )
    rows = cur.fetchall()
    updated = 0
    participants = 0
    now = datetime.now().isoformat()
    for row in rows:
        text = f"{row['headline'] or ''} {row['snippet'] or ''}".strip()
        if not text:
            continue
        lead, co = extract_investors(text)
        if not lead and not co:
            continue
        co_json = json.dumps(co) if co else row["co_investors"]
        cur.execute(
            """
            UPDATE funding_round_claims
            SET lead_investor = ?, co_investors = ?, extracted_at = ?
            WHERE id = ?
            """,
            (lead or row["lead_investor"], co_json, now, row["id"]),
        )
        claim = {
            "lead_investor": lead or row["lead_investor"],
            "co_investors": co_json,
            "headline": row["headline"],
            "snippet": row["snippet"],
        }
        participants += sync_claim_participants(int(row["id"]), claim, conn=conn)
        updated += 1
    conn.commit()
    conn.close()
    return {"claims_updated": updated, "claim_participant_rows": participants}


def backfill_deal_fields_from_text() -> dict[str, int]:
    """Re-parse instrument and pre/post-money on existing claims from headline/snippet."""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, headline, snippet, instrument_type,
               pre_money_valuation_usd, post_money_valuation_usd, deal_terms_text
        FROM funding_round_claims
        """
    )
    rows = cur.fetchall()
    updated = 0
    now = datetime.now().isoformat()
    for row in rows:
        text = f"{row['headline'] or ''} {row['snippet'] or ''}".strip()
        if not text:
            continue
        deal = extract_deal_fields(text)
        instrument = deal.get("instrument_type") or row["instrument_type"]
        pre = deal.get("pre_money_valuation_usd") or row["pre_money_valuation_usd"]
        post = deal.get("post_money_valuation_usd") or row["post_money_valuation_usd"]
        terms = (text[:800] if len(text) > 80 else None) or row["deal_terms_text"]
        if (
            instrument == row["instrument_type"]
            and pre == row["pre_money_valuation_usd"]
            and post == row["post_money_valuation_usd"]
            and not terms
        ):
            continue
        cur.execute(
            """
            UPDATE funding_round_claims
            SET instrument_type = ?, pre_money_valuation_usd = ?,
                post_money_valuation_usd = ?, deal_terms_text = COALESCE(?, deal_terms_text),
                extracted_at = ?
            WHERE id = ?
            """,
            (instrument, pre, post, terms, now, row["id"]),
        )
        updated += 1
    conn.commit()
    conn.close()
    return {"claims_deal_fields_updated": updated}


def apply_structured_funding_enrichment(row: dict[str, Any]) -> bool:
    """
    Apply Hermes/Grok structured funding row to an existing claim by source_url or claim_id.
    Expected keys: claim_id OR source_url, plus optional lead_investor, co_investors,
    amount_usd, valuation_usd, instrument_type, pre_money_valuation_usd,
    post_money_valuation_usd, round_type, announced_date.
    """
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    claim_row = None
    if row.get("claim_id"):
        cur.execute(
            "SELECT * FROM funding_round_claims WHERE id = ?",
            (int(row["claim_id"]),),
        )
        claim_row = cur.fetchone()
    elif row.get("source_url"):
        cur.execute(
            "SELECT * FROM funding_round_claims WHERE source_url = ?",
            (str(row["source_url"]).strip(),),
        )
        claim_row = cur.fetchone()
    if not claim_row:
        conn.close()
        return False

    co = row.get("co_investors")
    if isinstance(co, list):
        co_json = json.dumps(co)
    elif co is not None:
        co_json = str(co)
    else:
        co_json = claim_row["co_investors"]

    now = datetime.now().isoformat()
    cur.execute(
        """
        UPDATE funding_round_claims SET
            round_type = COALESCE(?, round_type),
            amount_usd = COALESCE(?, amount_usd),
            valuation_usd = COALESCE(?, valuation_usd),
            lead_investor = COALESCE(?, lead_investor),
            co_investors = COALESCE(?, co_investors),
            announced_date = COALESCE(?, announced_date),
            instrument_type = COALESCE(?, instrument_type),
            pre_money_valuation_usd = COALESCE(?, pre_money_valuation_usd),
            post_money_valuation_usd = COALESCE(?, post_money_valuation_usd),
            extraction_confidence = MAX(COALESCE(extraction_confidence, 0), 0.85),
            extracted_at = ?
        WHERE id = ?
        """,
        (
            row.get("round_type"),
            row.get("amount_usd"),
            row.get("valuation_usd"),
            row.get("lead_investor"),
            co_json,
            row.get("announced_date"),
            row.get("instrument_type"),
            row.get("pre_money_valuation_usd"),
            row.get("post_money_valuation_usd"),
            now,
            claim_row["id"],
        ),
    )
    claim_id = int(claim_row["id"])
    claim = dict(claim_row)
    claim.update({k: v for k, v in row.items() if v is not None})
    if isinstance(co, list):
        claim["co_investors"] = co_json
    sync_claim_participants(claim_id, claim, conn=conn)
    conn.commit()
    conn.close()
    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    extract_from_signals()
