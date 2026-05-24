#!/usr/bin/env python3
"""Claims → canonical funding_rounds (runs after signal_processor in daily pipeline)."""

from __future__ import annotations

import logging

from db.connection import get_conn
from db.migrations import apply_runtime_migrations

from collectors.enrichment.funding_enricher import extract_from_signals

logger = logging.getLogger("funding_rollup")


def run() -> dict:
    conn = get_conn()
    apply_runtime_migrations(conn)
    conn.commit()
    conn.close()
    return extract_from_signals()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    conn = get_conn()
    cur = conn.cursor()
    rounds_before = cur.execute("SELECT COUNT(*) FROM funding_rounds").fetchone()[0]
    funding_events = cur.execute(
        """
        SELECT COUNT(*) FROM intelligence_events
        WHERE event_type LIKE '%Funding%' AND company_id IS NOT NULL
        """
    ).fetchone()[0]
    conn.close()

    result = run()

    conn = get_conn()
    cur = conn.cursor()
    rounds_after = cur.execute("SELECT COUNT(*) FROM funding_rounds").fetchone()[0]
    claims_n = cur.execute("SELECT COUNT(*) FROM funding_round_claims").fetchone()[0]
    conn.close()

    logger.info(
        "Funding rollup: events_eligible=%s rounds_before=%s claims=%s "
        "claims_created=%s rounds_after=%s rounds_upserted=%s",
        funding_events,
        rounds_before,
        claims_n,
        result.get("claims_created", result.get("created", 0)),
        rounds_after,
        result.get("rounds_upserted", 0),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
