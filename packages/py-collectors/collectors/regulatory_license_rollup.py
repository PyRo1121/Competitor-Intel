#!/usr/bin/env python3
"""License claims from SEC/ESMA/RSS → regulatory_licenses (daily step)."""

from __future__ import annotations

import logging

from db.connection import transaction

from collectors.enrichment.company_data.aggregate import aggregate_license_claims
from collectors.enrichment.company_data.regulatory_extract import (
    extract_regulatory_license_claims,
)

logger = logging.getLogger("regulatory_license_rollup")


def run() -> dict:
    with transaction() as conn:
        extract_stats = extract_regulatory_license_claims(conn)
        aggregated = aggregate_license_claims(conn)
    result = {"extract": extract_stats, "regulatory_licenses_upserted": aggregated}
    logger.info("Regulatory license rollup: %s", result)
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
