"""Merge funding claims into canonical rounds with corroboration scores."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any

from db.connection import get_conn

from .company_valuation import sync_all_company_valuations
from .confidence_scoring import compute_corroboration
from .confidence_sync import sync_all_event_confidence
from .funding_investors import sync_round_participants
from .funding_source_trust import reclassify_claim_source_tiers

logger = logging.getLogger("funding_aggregator")

FUNDING_EVENT_TYPES = (
    "Funding Round",
    "Rumored Round",
    "Strategic Investment",
    "Mega Round",
    "Debt Financing",
    "Partnership Deal",
    "Traditional VC",
)


def _normalize_round_type(round_type: str) -> str:
    rt = (round_type or "Funding Round").strip()
    m = __import__("re").search(r"series\s*([a-f])", rt, __import__("re").I)
    if m:
        return f"Series {m.group(1).upper()}"
    return rt


def _amount_bucket(amount: int | None) -> str:
    if amount is None or amount <= 0:
        return "undisclosed"
    # Log-scale bucket for clustering (~±15% within bucket)
    import math

    log_m = math.log10(max(amount, 1))
    return f"{int(log_m * 10)}"


def _date_bucket(announced_date: str | None) -> str:
    if not announced_date:
        return "unknown"
    return str(announced_date)[:7]  # YYYY-MM


def cluster_key(
    company_id: int,
    round_type: str,
    amount_usd: int | None,
    announced_date: str | None,
) -> str:
    return (
        f"{company_id}:{_normalize_round_type(round_type)}:"
        f"{_amount_bucket(amount_usd)}:{_date_bucket(announced_date)}"
    )


def _build_scoring_context(
    conn: sqlite3.Connection,
    company_id: int,
    claim_group: list[sqlite3.Row],
) -> dict[str, Any]:
    claim_ids = [int(c["id"]) for c in claim_group if c["id"] is not None]
    participant_by_claim: dict[int, list[str]] = {}
    if claim_ids:
        placeholders = ",".join("?" * len(claim_ids))
        rows = conn.execute(
            f"""
            SELECT funding_round_claim_id, investor_name_raw
            FROM funding_claim_participants
            WHERE funding_round_claim_id IN ({placeholders})
            """,
            claim_ids,
        ).fetchall()
        for row in rows:
            cid = int(row["funding_round_claim_id"])
            participant_by_claim.setdefault(cid, []).append(row["investor_name_raw"])

    github = conn.execute(
        """
        SELECT star_growth_30d, commits_last_30d, contributor_count
        FROM github_metrics
        WHERE company_id = ?
        ORDER BY extracted_at DESC
        LIMIT 1
        """,
        (company_id,),
    ).fetchone()

    ctx: dict[str, Any] = {}
    if github:
        ctx["github"] = dict(github)
    ctx["participant_by_claim_id"] = participant_by_claim
    return ctx


def _claims_for_scoring(
    claim_group: list[sqlite3.Row],
    scoring_context: dict[str, Any],
) -> list[dict[str, Any]]:
    by_claim = scoring_context.get("participant_by_claim_id") or {}
    out: list[dict[str, Any]] = []
    for row in claim_group:
        d = dict(row)
        cid = d.get("id")
        if cid is not None:
            d["participant_names"] = by_claim.get(int(cid), [])
        out.append(d)
    return out


def _amounts_agree(amounts: list[int], tolerance: float = 0.15) -> bool:
    vals = [a for a in amounts if a and a > 0]
    if len(vals) < 2:
        return True
    lo, hi = min(vals), max(vals)
    if hi == 0:
        return True
    return (hi - lo) / hi <= tolerance


def _pick_weighted_field(
    claims: list[sqlite3.Row], field: str
) -> tuple[Any, str | None, list[str]]:
    """Choose field value from highest-weight claim; list all reporting source_urls."""
    ranked = sorted(
        claims,
        key=lambda c: (float(c["source_weight"] or 0), float(c["extraction_confidence"] or 0)),
        reverse=True,
    )
    sources: list[str] = []
    for c in claims:
        val = c[field]
        if val is not None and val != "":
            url = c["source_url"]
            if url and url not in sources:
                sources.append(url)
    if not ranked:
        return None, None, sources
    best = ranked[0]
    return best[field], best["source_tier"], sources


def _build_provenance(claims: list[sqlite3.Row]) -> str:
    fields = (
        "round_type",
        "amount_usd",
        "valuation_usd",
        "lead_investor",
        "co_investors",
        "announced_date",
        "instrument_type",
        "pre_money_valuation_usd",
        "post_money_valuation_usd",
        "currency",
    )
    prov: dict[str, Any] = {}
    for field in fields:
        value, tier, urls = _pick_weighted_field(claims, field)
        if value is not None:
            prov[field] = {
                "value": value,
                "source_tier": tier,
                "reporting_sources": urls[:10],
                "reports": len(urls),
            }

    investor_reports: dict[str, dict[str, Any]] = {}
    for claim in claims:
        url = claim["source_url"]
        tier = claim["source_tier"]
        lead = claim["lead_investor"]
        if lead:
            key = str(lead).strip()
            bucket = investor_reports.setdefault(
                key, {"roles": set(), "sources": [], "source_tiers": []}
            )
            bucket["roles"].add("lead")
            if url and url not in bucket["sources"]:
                bucket["sources"].append(url)
                bucket["source_tiers"].append(tier)
        co_raw = claim["co_investors"]
        co_names: list[str] = []
        if co_raw:
            try:
                parsed = json.loads(co_raw) if isinstance(co_raw, str) else co_raw
                if isinstance(parsed, list):
                    co_names = [str(n) for n in parsed if n]
            except (json.JSONDecodeError, TypeError):
                co_names = [str(co_raw)]
        for name in co_names:
            key = str(name).strip()
            bucket = investor_reports.setdefault(
                key, {"roles": set(), "sources": [], "source_tiers": []}
            )
            bucket["roles"].add("participant")
            if url and url not in bucket["sources"]:
                bucket["sources"].append(url)
                bucket["source_tiers"].append(tier)

    if investor_reports:
        prov["investors"] = {
            name: {
                "roles": sorted(meta["roles"]),
                "reporting_sources": meta["sources"][:10],
                "reports": len(meta["sources"]),
            }
            for name, meta in investor_reports.items()
        }

    return json.dumps(prov)


def prune_legacy_rounds() -> int:
    """Drop pre-aggregation round rows (one row per outlet, no cluster_key)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM funding_rounds WHERE cluster_key IS NULL")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted:
        logger.info("Pruned %s legacy funding_rounds rows", deleted)
    return deleted


def aggregate_funding_rounds() -> dict[str, Any]:
    """Cluster claims → upsert funding_rounds; link claims to round ids."""
    prune_legacy_rounds()
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    reclassify_claim_source_tiers(conn)
    conn.commit()

    cur.execute(
        """
        SELECT * FROM funding_round_claims
        ORDER BY company_id, announced_date DESC, source_weight DESC
        """
    )
    all_claims = cur.fetchall()
    if not all_claims:
        conn.close()
        return {"rounds_upserted": 0, "claims_linked": 0}

    # Group by company then cluster
    by_company: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in all_claims:
        by_company[row["company_id"]].append(row)

    rounds_upserted = 0
    claims_linked = 0
    now = datetime.now().isoformat()

    for company_id, company_claims in by_company.items():
        clusters: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for claim in company_claims:
            key = cluster_key(
                company_id,
                claim["round_type"],
                claim["amount_usd"],
                claim["announced_date"],
            )
            clusters[key].append(claim)

        # Merge clusters with same round_type + close amounts (second pass)
        merged: list[list[sqlite3.Row]] = []
        for group in clusters.values():
            placed = False
            for bucket in merged:
                if bucket[0]["round_type"] != group[0]["round_type"]:
                    continue
                a1 = [c["amount_usd"] for c in bucket if c["amount_usd"]]
                a2 = [c["amount_usd"] for c in group if c["amount_usd"]]
                if _amounts_agree(a1 + a2, tolerance=0.18):
                    bucket.extend(group)
                    placed = True
                    break
            if not placed:
                merged.append(list(group))

        for claim_group in merged:
            scoring_ctx = _build_scoring_context(conn, company_id, claim_group)
            score, _meta = compute_corroboration(
                _claims_for_scoring(claim_group, scoring_ctx),
                scoring_context=scoring_ctx,
            )
            round_type, _, _ = _pick_weighted_field(claim_group, "round_type")
            amount, _, _ = _pick_weighted_field(claim_group, "amount_usd")
            valuation, _, _ = _pick_weighted_field(claim_group, "valuation_usd")
            lead, _, _ = _pick_weighted_field(claim_group, "lead_investor")
            co_json, _, _ = _pick_weighted_field(claim_group, "co_investors")
            announced, _, _ = _pick_weighted_field(claim_group, "announced_date")
            instrument, _, _ = _pick_weighted_field(claim_group, "instrument_type")
            pre_money, _, _ = _pick_weighted_field(claim_group, "pre_money_valuation_usd")
            post_money, _, _ = _pick_weighted_field(claim_group, "post_money_valuation_usd")
            currency, _, _ = _pick_weighted_field(claim_group, "currency")

            official_count = sum(1 for c in claim_group if c["is_official"])
            best = max(claim_group, key=lambda c: float(c["source_weight"] or 0))
            primary_url = best["source_url"]
            ckey = cluster_key(company_id, round_type or "Funding Round", amount, announced)
            provenance = _build_provenance(claim_group)

            cur.execute(
                "SELECT id FROM funding_rounds WHERE cluster_key = ?",
                (ckey,),
            )
            existing = cur.fetchone()

            if existing:
                round_id = int(existing["id"])
                cur.execute(
                    """
                    UPDATE funding_rounds SET
                        round_type = ?, amount_usd = ?, valuation_usd = ?,
                        lead_investor = ?, co_investors = ?, announced_date = ?,
                        source = ?, source_url = ?, confidence = ?,
                        report_count = ?, official_report_count = ?,
                        corroboration_score = ?, source_tier_best = ?,
                        fields_provenance = ?, currency = ?, instrument_type = ?,
                        pre_money_valuation_usd = ?, post_money_valuation_usd = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        round_type or "Funding Round",
                        amount,
                        valuation,
                        lead,
                        co_json,
                        announced,
                        best["source"],
                        primary_url,
                        score,
                        len(claim_group),
                        official_count,
                        score,
                        best["source_tier"],
                        provenance,
                        currency or "USD",
                        instrument,
                        pre_money,
                        post_money,
                        now,
                        round_id,
                    ),
                )
                sync_round_participants(round_id, claim_group, conn=conn)
            else:
                cur.execute(
                    """
                    INSERT INTO funding_rounds
                    (company_id, round_type, amount_usd, valuation_usd, lead_investor,
                     co_investors, source, source_url, confidence, announced_date,
                     extracted_at, cluster_key, report_count, official_report_count,
                     corroboration_score, source_tier_best, fields_provenance,
                     currency, instrument_type, pre_money_valuation_usd,
                     post_money_valuation_usd, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_id,
                        round_type or "Funding Round",
                        amount,
                        valuation,
                        lead,
                        co_json,
                        best["source"],
                        primary_url,
                        score,
                        announced,
                        now,
                        ckey,
                        len(claim_group),
                        official_count,
                        score,
                        best["source_tier"],
                        provenance,
                        currency or "USD",
                        instrument,
                        pre_money,
                        post_money,
                        now,
                    ),
                )
                inserted_id = cur.lastrowid
                if inserted_id is None:
                    continue
                round_id = int(inserted_id)
            rounds_upserted += 1
            sync_round_participants(round_id, claim_group, conn=conn)

            for c in claim_group:
                cur.execute(
                    "UPDATE funding_round_claims SET funding_round_id = ? WHERE id = ?",
                    (round_id, c["id"]),
                )
                claims_linked += 1

    sync_stats = sync_all_event_confidence(conn)
    valuation_stats = sync_all_company_valuations(conn)
    conn.commit()
    conn.close()
    logger.info(
        "Funding aggregation: rounds_upserted=%s claims_linked=%s confidence_sync=%s valuations=%s",
        rounds_upserted,
        claims_linked,
        sync_stats,
        valuation_stats,
    )
    return {
        "rounds_upserted": rounds_upserted,
        "claims_linked": claims_linked,
        "confidence_sync": sync_stats,
        "company_valuations": valuation_stats,
    }
