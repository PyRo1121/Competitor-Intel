#!/usr/bin/env python3
"""Profile / team / product / license claims → canonical company tables."""

from __future__ import annotations

import logging

from db.connection import get_conn
from db.migrations import apply_runtime_migrations

from collectors.enrichment.company_data import run_company_data_pipeline

logger = logging.getLogger("company_data_rollup")


def _counts(conn) -> dict:
    cur = conn.cursor()
    return {
        "profile_claims": cur.execute("SELECT COUNT(*) FROM company_profile_claims").fetchone()[0],
        "team_claims": cur.execute("SELECT COUNT(*) FROM team_member_claims").fetchone()[0],
        "product_claims": cur.execute("SELECT COUNT(*) FROM product_claims").fetchone()[0],
        "license_claims": cur.execute("SELECT COUNT(*) FROM license_claims").fetchone()[0],
        "company_details": cur.execute("SELECT COUNT(*) FROM company_details").fetchone()[0],
        "team_members": cur.execute("SELECT COUNT(*) FROM team_members").fetchone()[0],
        "products": cur.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "regulatory_licenses": cur.execute("SELECT COUNT(*) FROM regulatory_licenses").fetchone()[
            0
        ],
    }


def run() -> dict:
    conn = get_conn()
    apply_runtime_migrations(conn)
    conn.commit()
    conn.close()
    return run_company_data_pipeline()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    conn = get_conn()
    apply_runtime_migrations(conn)
    conn.commit()
    before = _counts(conn)
    conn.close()

    result = run()

    conn = get_conn()
    after = _counts(conn)
    conn.close()

    logger.info("Company data rollup before=%s", before)
    logger.info("Company data rollup result=%s", result)
    logger.info("Company data rollup after=%s", after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
