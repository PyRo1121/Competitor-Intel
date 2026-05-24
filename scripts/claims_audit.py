#!/usr/bin/env python3
"""Claim/canonical table counts; optional strict invariants for CI."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from ci_paths import db_path  # noqa: E402

CLAIM_TABLES = (
    "funding_round_claims",
    "funding_rounds",
    "team_member_claims",
    "team_members",
    "product_claims",
    "products",
    "license_claims",
    "regulatory_licenses",
    "company_profile_claims",
    "job_posting_claims",
    "job_postings",
)

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "funding_round_claims": ("company_id", "round_type", "source", "source_tier"),
    "job_posting_claims": ("company_id", "title", "source"),
}


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    return {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}


def _actionable_missed_count(cur: sqlite3.Cursor) -> int:
    from collectors.intel_quality_gate import actionable_null_stats  # noqa: E402

    _actionable, missed = actionable_null_stats(cur)
    return missed


def main() -> int:
    db = str(db_path())
    if not os.path.isfile(db):
        print(f"WARN: database not found: {db} (counts skipped)")
        return 0

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    strict = _env_truthy("CI_CLAIMS_AUDIT_STRICT")
    failed: list[str] = []

    for table in CLAIM_TABLES:
        if not _table_exists(cur, table):
            print(f"{table}: MISSING TABLE")
            if strict:
                failed.append(f"missing_table={table}")
            continue
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")

    for table, cols in REQUIRED_COLUMNS.items():
        if not _table_exists(cur, table):
            continue
        present = _table_columns(cur, table)
        missing = [c for c in cols if c not in present]
        if missing and strict:
            failed.append(f"missing_columns={table}:{','.join(missing)}")

    missed_max = _env_int("CI_CLAIMS_ACTIONABLE_MISSED_MAX", 0)
    missed = _actionable_missed_count(cur)
    print(f"actionable_missed_company_link: {missed}")
    if strict and missed > missed_max:
        failed.append(f"actionable_missed={missed}>{missed_max}")

    conn.close()

    if failed:
        print("FAIL:", ", ".join(failed))
        return 1
    if strict:
        print("PASS: claims audit (strict)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
