"""Orchestrate company-data extraction + aggregation."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from db.connection import get_conn
from db.migrations import apply_runtime_migrations

from .aggregate import run_all_aggregators
from .extract_raw_signals import extract_from_raw_signals
from .extract_signals import extract_from_events
from .extract_website import run_website_extraction

logger = logging.getLogger("company_data.pipeline")


def run_company_data_pipeline(
    conn: sqlite3.Connection | None = None,
    *,
    website_batch_size: int | None = None,
) -> dict[str, Any]:
    own = conn is None
    conn = conn or get_conn()
    apply_runtime_migrations(conn)
    conn.commit()

    extract_stats: dict[str, object] = {}
    extract_stats["events"] = extract_from_events(conn)
    extract_stats["raw_signals"] = extract_from_raw_signals(conn)
    extract_stats["apis"] = run_website_extraction(conn, batch_size=website_batch_size)
    aggregate_stats = run_all_aggregators(conn)
    conn.commit()

    if own:
        conn.close()

    result = {"extract": extract_stats, "aggregate": aggregate_stats}
    logger.info("Company data pipeline: %s", result)
    return result
