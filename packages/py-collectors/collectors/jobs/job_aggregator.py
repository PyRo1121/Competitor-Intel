"""Merge job_posting_claims into canonical job_postings with corroboration."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any

from db.connection import get_conn

from .job_parser import normalize_title

logger = logging.getLogger("job_aggregator")


def _norm_title_key(title: str) -> str:
    t = normalize_title(title).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t[:120]


def cluster_key(
    company_id: int,
    title: str,
    location: str | None,
    ats_platform: str | None,
    external_id: str | None,
) -> str:
    if external_id and ats_platform:
        return f"{company_id}:{ats_platform}:{external_id}"
    loc = (location or "unknown").lower()[:40]
    return f"{company_id}:{_norm_title_key(title)}:{loc}"


def compute_corroboration(claims: list[sqlite3.Row]) -> tuple[float, dict[str, Any]]:
    if not claims:
        return 0.0, {}
    domains = set()
    for c in claims:
        url = c["source_url"] or ""
        if "://" in url:
            host = url.split("/")[2].lower()
            if host.startswith("www."):
                host = host[4:]
            domains.add(host)
        elif c["source"]:
            domains.add(str(c["source"]).lower())
    n_claims = len(claims)
    n_domains = len(domains)
    official = sum(1 for c in claims if c["is_official"])
    max_weight = max(float(c["source_weight"] or 0) for c in claims)

    score = (
        min(n_domains, 4) / 4.0 * 0.30
        + min(n_claims, 5) / 5.0 * 0.20
        + (0.25 if official else 0)
        + max_weight * 0.20
        + 0.05
    )
    return min(1.0, round(score, 3)), {
        "claim_count": n_claims,
        "unique_domains": n_domains,
        "official_count": official,
    }


def _pick_field(claims: list[sqlite3.Row], field: str) -> Any:
    ranked = sorted(
        claims,
        key=lambda c: (float(c["source_weight"] or 0), float(c["extraction_confidence"] or 0)),
        reverse=True,
    )
    for c in ranked:
        val = c[field]
        if val is not None and val != "":
            return val
    return None


def _build_provenance(claims: list[sqlite3.Row]) -> str:
    fields = (
        "title",
        "department",
        "location",
        "seniority_band",
        "employment_type",
        "salary_min_usd",
        "salary_max_usd",
        "remote_policy",
        "posted_at",
    )
    prov: dict[str, Any] = {}
    for field in fields:
        val = _pick_field(claims, field)
        if val is not None:
            sources = []
            for c in claims:
                if c[field] is not None and c[field] != "":
                    u = c["source_url"]
                    if u and u not in sources:
                        sources.append(u)
            prov[field] = {
                "value": val,
                "source_tier": _pick_field(claims, "source_tier"),
                "reporting_sources": sources[:10],
                "reports": len(sources),
            }
    skills: dict[str, int] = {}
    for c in claims:
        raw = c["tech_stack_json"]
        if not raw:
            continue
        try:
            items = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        for item in items:
            sk = item.get("skill")
            if sk:
                skills[sk] = skills.get(sk, 0) + 1
    if skills:
        prov["skills"] = skills
    return json.dumps(prov)


def _sync_posting_skills(cur: sqlite3.Cursor, posting_id: int, claims: list[sqlite3.Row]) -> None:
    cur.execute("DELETE FROM job_posting_skills WHERE job_posting_id = ?", (posting_id,))
    merged: dict[str, str] = {}
    for c in claims:
        raw = c["tech_stack_json"]
        if not raw:
            continue
        try:
            items = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        for item in items:
            sk = item.get("skill")
            if sk and sk not in merged:
                merged[sk] = item.get("category", "other")
    for skill, category in merged.items():
        cur.execute(
            """
            INSERT INTO job_posting_skills (job_posting_id, skill, category, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (posting_id, skill, category, 0.85),
        )


def aggregate_job_postings() -> dict[str, int]:
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM job_posting_claims WHERE is_active = 1 ORDER BY company_id")
    all_claims = cur.fetchall()
    if not all_claims:
        conn.close()
        return {"postings_upserted": 0, "claims_linked": 0}

    by_company: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in all_claims:
        by_company[row["company_id"]].append(row)

    postings_upserted = 0
    claims_linked = 0
    now = datetime.now().isoformat()

    for company_id, company_claims in by_company.items():
        company_seen_urls: set[str] = set()
        clusters: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for claim in company_claims:
            key = cluster_key(
                company_id,
                claim["title"],
                claim["location"],
                claim["ats_platform"],
                claim["external_id"],
            )
            clusters[key].append(claim)

        for claim_group in clusters.values():
            score, _ = compute_corroboration(claim_group)
            ckey = cluster_key(
                company_id,
                _pick_field(claim_group, "title") or "",
                _pick_field(claim_group, "location"),
                _pick_field(claim_group, "ats_platform"),
                _pick_field(claim_group, "external_id"),
            )
            best = max(claim_group, key=lambda c: float(c["source_weight"] or 0))

            cur.execute("SELECT id FROM job_postings WHERE cluster_key = ?", (ckey,))
            existing = cur.fetchone()
            provenance = _build_provenance(claim_group)
            fields = {
                "company_id": company_id,
                "cluster_key": ckey,
                "title": _pick_field(claim_group, "title"),
                "department": _pick_field(claim_group, "department"),
                "team": _pick_field(claim_group, "team"),
                "location": _pick_field(claim_group, "location"),
                "location_type": _pick_field(claim_group, "location_type"),
                "remote_policy": _pick_field(claim_group, "remote_policy"),
                "seniority_band": _pick_field(claim_group, "seniority_band"),
                "employment_type": _pick_field(claim_group, "employment_type"),
                "job_type": _pick_field(claim_group, "employment_type"),
                "salary_range": _pick_field(claim_group, "salary_range"),
                "salary_min_usd": _pick_field(claim_group, "salary_min_usd"),
                "salary_max_usd": _pick_field(claim_group, "salary_max_usd"),
                "source": best["source"],
                "source_url": best["source_url"],
                "ats_platform": _pick_field(claim_group, "ats_platform"),
                "external_id": _pick_field(claim_group, "external_id"),
                "posted_at": _pick_field(claim_group, "posted_at"),
                "description_snippet": _pick_field(claim_group, "description_snippet"),
                "description_text": _pick_field(claim_group, "description_text"),
                "tech_stack_json": _pick_field(claim_group, "tech_stack_json"),
                "corroboration_score": score,
                "report_count": len(claim_group),
                "official_report_count": sum(1 for c in claim_group if c["is_official"]),
                "source_tier_best": best["source_tier"],
                "fields_provenance": provenance,
                "is_active": 1,
                "updated_at": now,
            }

            if existing:
                posting_id = int(existing["id"])
                cur.execute(
                    """
                    UPDATE job_postings SET
                        title = :title, department = :department, team = :team,
                        location = :location, location_type = :location_type,
                        remote_policy = :remote_policy, seniority_band = :seniority_band,
                        employment_type = :employment_type, job_type = :job_type,
                        salary_range = :salary_range, salary_min_usd = :salary_min_usd,
                        salary_max_usd = :salary_max_usd, source = :source,
                        source_url = :source_url, ats_platform = :ats_platform,
                        external_id = :external_id, posted_at = :posted_at,
                        description_snippet = :description_snippet,
                        description_text = :description_text,
                        tech_stack_json = :tech_stack_json,
                        corroboration_score = :corroboration_score,
                        report_count = :report_count,
                        official_report_count = :official_report_count,
                        source_tier_best = :source_tier_best,
                        fields_provenance = :fields_provenance,
                        is_active = 1, updated_at = :updated_at
                    WHERE id = :posting_id
                    """,
                    {**fields, "posting_id": posting_id},
                )
            else:
                cur.execute(
                    """
                    INSERT INTO job_postings
                    (company_id, cluster_key, title, department, team, location, location_type,
                     remote_policy, seniority_band, employment_type, job_type, salary_range,
                     salary_min_usd, salary_max_usd, source, source_url, ats_platform,
                     external_id, posted_at, description_snippet, description_text,
                     tech_stack_json, corroboration_score, report_count, official_report_count,
                     source_tier_best, fields_provenance, is_active, extracted_at, updated_at)
                    VALUES
                    (:company_id, :cluster_key, :title, :department, :team, :location,
                     :location_type, :remote_policy, :seniority_band, :employment_type,
                     :job_type, :salary_range, :salary_min_usd, :salary_max_usd, :source,
                     :source_url, :ats_platform, :external_id, :posted_at, :description_snippet,
                     :description_text, :tech_stack_json, :corroboration_score, :report_count,
                     :official_report_count, :source_tier_best, :fields_provenance, 1,
                     :updated_at, :updated_at)
                    """,
                    fields,
                )
                if cur.lastrowid is None:
                    continue
                posting_id = int(cur.lastrowid)
                postings_upserted += 1

            if best["source_url"]:
                company_seen_urls.add(best["source_url"])

            _sync_posting_skills(cur, posting_id, claim_group)
            for c in claim_group:
                cur.execute(
                    """
                    UPDATE job_posting_claims SET job_posting_id = ? WHERE id = ?
                    """,
                    (posting_id, c["id"]),
                )
                claims_linked += 1

        # Deactivate stale openings for this company only (X-04)
        if company_seen_urls:
            placeholders = ",".join("?" * len(company_seen_urls))
            cur.execute(
                f"""
                UPDATE job_postings SET is_active = 0, removed_at = date('now'), updated_at = ?
                WHERE company_id = ?
                  AND is_active = 1 AND source_url IS NOT NULL
                  AND source_url NOT IN ({placeholders})
                  AND ats_platform IS NOT NULL
                """,
                [now, company_id, *company_seen_urls],
            )

    conn.commit()
    conn.close()
    logger.info(
        "Job aggregation: postings_upserted=%s claims_linked=%s",
        postings_upserted,
        claims_linked,
    )
    return {"postings_upserted": postings_upserted, "claims_linked": claims_linked}


def record_velocity_snapshots() -> int:
    """Daily per-company hiring velocity rollup."""
    conn = get_conn()
    cur = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute(
        """
        SELECT company_id,
               COUNT(*) AS active_openings,
               COUNT(DISTINCT department) AS departments_hiring,
               COUNT(DISTINCT location) AS locations_hiring,
               COUNT(DISTINCT seniority_band) AS seniority_levels
        FROM job_postings
        WHERE is_active = 1
        GROUP BY company_id
        """
    )
    rows = cur.fetchall()
    n = 0
    for row in rows:
        cid, active, depts, locs, seniority = row
        cur.execute(
            """
            SELECT COUNT(*) FROM job_postings
            WHERE company_id = ? AND posted_at >= date('now', '-30 days')
            """,
            (cid,),
        )
        new_30d = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO job_velocity_snapshots
            (company_id, snapshot_date, active_openings, new_postings_30d,
             departments_hiring, locations_hiring, seniority_levels, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(company_id, snapshot_date) DO UPDATE SET
                active_openings = excluded.active_openings,
                new_postings_30d = excluded.new_postings_30d,
                departments_hiring = excluded.departments_hiring,
                locations_hiring = excluded.locations_hiring,
                seniority_levels = excluded.seniority_levels,
                extracted_at = excluded.extracted_at
            """,
            (cid, today, active, new_30d, depts, locs, seniority),
        )
        n += 1
    conn.commit()
    conn.close()
    return n
