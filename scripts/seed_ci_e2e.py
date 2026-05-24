#!/usr/bin/env python3
"""Idempotent minimal fixture for dashboard Playwright smoke (6-C02)."""

from __future__ import annotations

from db.connection import transaction

SLUG = "e2e-smoke-co"
NAME = "E2E Smoke Co"


def main() -> None:
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM companies WHERE slug = ?", (SLUG,))
        row = cur.fetchone()
        if row:
            print(f"e2e seed: {SLUG} already present (id={row[0]})")
            return
        cur.execute(
            """
            INSERT INTO companies (name, slug, status, industry, description)
            VALUES (?, ?, 'active', 'AI / Technology', 'Fixture company for CI dashboard smoke tests.')
            """,
            (NAME, SLUG),
        )
        company_id = int(cur.lastrowid)
        cur.execute(
            """
            INSERT INTO company_details (
                company_id, founded_year, headquarters, business_model, description_long
            ) VALUES (?, 2020, 'San Francisco, CA', 'SaaS', 'Synthetic profile for e2e smoke.')
            """,
            (company_id,),
        )
        now = "2026-05-19T00:00:00Z"
        cur.execute(
            """
            INSERT INTO company_profile_claims (
                company_id, field_key, field_value, source, source_url,
                source_tier, source_weight, extraction_confidence, extracted_at
            ) VALUES (?, 'legal_name', 'E2E Smoke Co LLC', 'ci_fixture', 'fixture://legal', 'manual', 1.0, 1.0, ?)
            """,
            (company_id, now),
        )
        cur.execute(
            """
            INSERT INTO company_profile_claims (
                company_id, field_key, field_value, source, source_url,
                source_tier, source_weight, extraction_confidence, extracted_at
            ) VALUES (?, 'yc_batch', 'W26', 'ci_fixture', 'fixture://yc', 'manual', 1.0, 0.9, ?)
            """,
            (company_id, now),
        )
        conn.commit()
        print(f"e2e seed: created {SLUG} (id={company_id})")


if __name__ == "__main__":
    main()
