"""Merge company-data claims into canonical tables with corroboration scores."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("company_data.aggregate")


def _unique_domains(rows: list[sqlite3.Row]) -> int:
    domains = set()
    for r in rows:
        url = r["source_url"] or ""
        try:
            d = (urlparse(url).netloc or "").lower().replace("www.", "")
            if d:
                domains.add(d)
        except Exception:
            pass
    return len(domains)


def _corroboration_from_claims(rows: list[sqlite3.Row]) -> tuple[float, int, int]:
    """Simple deal-style score from claim count + domain diversity + mean weight."""
    if not rows:
        return 0.0, 0, 0
    n = len(rows)
    domains = _unique_domains(rows)
    weights = [float(r["source_weight"] or 0.5) for r in rows]
    mean_w = sum(weights) / len(weights)
    official = sum(1 for r in rows if r["is_official"])
    score = min(
        1.0,
        0.25
        + min(domains, 5) * 0.12
        + mean_w * 0.35
        + (0.08 if official else 0)
        + min(n, 6) * 0.03,
    )
    return round(score, 3), n, domains


def aggregate_profile_claims(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT company_id, field_key, field_value, source_url, source_tier,
               source_weight, is_official, extraction_confidence
        FROM company_profile_claims
        """
    ).fetchall()
    by_co: dict[int, dict[str, list[sqlite3.Row]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_co[int(r["company_id"])][r["field_key"]].append(r)

    upserted = 0
    now = datetime.now().isoformat()
    for company_id, fields in by_co.items():
        merged: dict[str, Any] = {}
        provenance: dict[str, Any] = {}
        for field_key, claims in fields.items():
            best = max(
                claims,
                key=lambda c: (float(c["source_weight"]), float(c["extraction_confidence"] or 0)),
            )
            merged[field_key] = best["field_value"]
            provenance[field_key] = {
                "value": best["field_value"],
                "source_url": best["source_url"],
                "source_tier": best["source_tier"],
                "report_count": len(claims),
            }
        cur.execute(
            """
            INSERT INTO company_details (
                company_id, founded_year, headquarters, team_size, team_size_source,
                business_model, tech_stack, description_long, traction, moat,
                fields_provenance, last_enriched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id) DO UPDATE SET
                founded_year = COALESCE(excluded.founded_year, founded_year),
                headquarters = COALESCE(excluded.headquarters, headquarters),
                team_size = COALESCE(excluded.team_size, team_size),
                team_size_source = COALESCE(excluded.team_size_source, team_size_source),
                business_model = COALESCE(excluded.business_model, business_model),
                tech_stack = COALESCE(excluded.tech_stack, tech_stack),
                description_long = COALESCE(excluded.description_long, description_long),
                traction = COALESCE(excluded.traction, traction),
                moat = COALESCE(excluded.moat, moat),
                fields_provenance = excluded.fields_provenance,
                last_enriched_at = excluded.last_enriched_at
            """,
            (
                company_id,
                _int_field(merged.get("founded_year")),
                merged.get("headquarters"),
                _int_field(merged.get("team_size")),
                merged.get("team_size_source") or "aggregated",
                merged.get("business_model"),
                merged.get("tech_stack"),
                merged.get("description_long"),
                merged.get("traction"),
                merged.get("moat"),
                json.dumps(provenance),
                now,
            ),
        )
        industry = merged.get("industry")
        website = merged.get("website_url")
        entity_type = merged.get("entity_type")
        if industry or website or entity_type:
            notes_bits = []
            if entity_type:
                notes_bits.append(f"entity_type={entity_type}")
            if merged.get("legal_name"):
                notes_bits.append(f"legal_name={merged['legal_name']}")
            cur.execute(
                """
                UPDATE companies SET
                    industry = COALESCE(?, industry),
                    website = COALESCE(?, website),
                    last_updated_at = ?
                WHERE id = ?
                """,
                (industry, website, now, company_id),
            )
            if notes_bits:
                cur.execute(
                    """
                    UPDATE companies SET
                        notes = TRIM(COALESCE(notes, '') || ' ' || ?)
                    WHERE id = ? AND (notes IS NULL OR notes NOT LIKE '%' || ? || '%')
                    """,
                    (" ".join(notes_bits), company_id, notes_bits[0]),
                )
        upserted += 1
    return upserted


def _int_field(val: str | None) -> int | None:
    if val is None:
        return None
    try:
        return int(str(val).strip())
    except ValueError:
        return None


def aggregate_team_claims(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM team_member_claims").fetchall()
    groups: dict[tuple[int, str], list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        key = (int(r["company_id"]), r["name_normalized"] or r["name"].lower())
        groups[key].append(r)

    upserted = 0
    now = datetime.now().isoformat()
    for (company_id, _), claims in groups.items():
        score, report_count, _ = _corroboration_from_claims(claims)
        best = max(claims, key=lambda c: float(c["source_weight"]))
        role_votes: dict[str, int] = defaultdict(int)
        for c in claims:
            if c["role"]:
                role_votes[c["role"]] += 1
        role = max(role_votes, key=lambda k: role_votes[k]) if role_votes else best["role"]
        is_founder = any(c["is_founder"] for c in claims)
        prov = [
            {
                "source_url": c["source_url"],
                "role": c["role"],
                "source_tier": c["source_tier"],
            }
            for c in claims
        ]
        name_norm = best["name_normalized"] or best["name"].lower()
        cur.execute(
            """
            INSERT INTO team_members (
                company_id, name, name_normalized, role, is_founder, joined_date,
                linkedin_url, source, source_url, corroboration_score, report_count,
                fields_provenance, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, name_normalized) DO UPDATE SET
                role = COALESCE(excluded.role, role),
                is_founder = excluded.is_founder OR is_founder,
                joined_date = COALESCE(excluded.joined_date, joined_date),
                linkedin_url = COALESCE(excluded.linkedin_url, linkedin_url),
                source = excluded.source,
                source_url = excluded.source_url,
                corroboration_score = excluded.corroboration_score,
                report_count = excluded.report_count,
                fields_provenance = excluded.fields_provenance,
                extracted_at = excluded.extracted_at
            """,
            (
                company_id,
                best["name"],
                name_norm,
                role,
                1 if is_founder else 0,
                best["joined_date"],
                best["linkedin_url"],
                best["source"],
                best["source_url"],
                score,
                report_count,
                json.dumps(prov),
                now,
            ),
        )
        upserted += 1
    return upserted


def aggregate_product_claims(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM product_claims").fetchall()
    groups: dict[tuple[int, str], list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        key = (int(r["company_id"]), r["name_normalized"] or r["name"].lower())
        groups[key].append(r)

    upserted = 0
    now = datetime.now().isoformat()
    for (company_id, _), claims in groups.items():
        score, report_count, _ = _corroboration_from_claims(claims)
        best = max(claims, key=lambda c: float(c["source_weight"]))
        prov = [{"source_url": c["source_url"], "source_tier": c["source_tier"]} for c in claims]
        name_norm = best["name_normalized"] or best["name"].lower()
        cur.execute(
            """
            INSERT INTO products (
                company_id, name, name_normalized, description, category,
                pricing_json, launch_date, status, source, url,
                corroboration_score, report_count, fields_provenance, extracted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, name_normalized) DO UPDATE SET
                description = COALESCE(excluded.description, description),
                category = COALESCE(excluded.category, category),
                launch_date = COALESCE(excluded.launch_date, launch_date),
                url = COALESCE(excluded.url, url),
                corroboration_score = excluded.corroboration_score,
                report_count = excluded.report_count,
                fields_provenance = excluded.fields_provenance,
                extracted_at = excluded.extracted_at
            """,
            (
                company_id,
                best["name"],
                name_norm,
                best["description"],
                best["category"],
                best["pricing_json"],
                best["launch_date"],
                best["status"] or "active",
                best["source"],
                best["product_url"],
                score,
                report_count,
                json.dumps(prov),
                now,
            ),
        )
        upserted += 1
    return upserted


def aggregate_license_claims(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM license_claims").fetchall()
    groups: dict[tuple[int, str, str], list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        key = (int(r["company_id"]), r["jurisdiction"], r["license_type"])
        groups[key].append(r)

    upserted = 0
    now = datetime.now().isoformat()
    for (company_id, jurisdiction, license_type), claims in groups.items():
        score, report_count, _ = _corroboration_from_claims(claims)
        best = max(claims, key=lambda c: float(c["source_weight"]))
        prov = [{"source_url": c["source_url"]} for c in claims]
        cur.execute(
            """
            INSERT INTO regulatory_licenses (
                company_id, jurisdiction, license_type, status, regulator,
                license_number, effective_date, corroboration_score, report_count,
                fields_provenance, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, jurisdiction, license_type) DO UPDATE SET
                status = excluded.status,
                regulator = COALESCE(excluded.regulator, regulator),
                license_number = COALESCE(excluded.license_number, license_number),
                effective_date = COALESCE(excluded.effective_date, effective_date),
                corroboration_score = excluded.corroboration_score,
                report_count = excluded.report_count,
                fields_provenance = excluded.fields_provenance,
                updated_at = excluded.updated_at
            """,
            (
                company_id,
                jurisdiction,
                license_type,
                best["status"],
                best["regulator"],
                best["license_number"],
                best["effective_date"],
                score,
                report_count,
                json.dumps(prov),
                now,
            ),
        )
        upserted += 1
    return upserted


def run_all_aggregators(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "company_details": aggregate_profile_claims(conn),
        "team_members": aggregate_team_claims(conn),
        "products": aggregate_product_claims(conn),
        "regulatory_licenses": aggregate_license_claims(conn),
    }
