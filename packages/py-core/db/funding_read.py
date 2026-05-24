"""Read funding history for display (Obsidian, Discord stats). Canonical: funding_rounds."""

from __future__ import annotations

import sqlite3


def fetch_company_funding_rows(
    cursor: sqlite3.Cursor,
    company_id: int,
    *,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    """Return funding rows newest-first from funding_rounds (canonical table)."""
    sql = """
        SELECT
            round_type,
            amount_usd,
            valuation_usd,
            lead_investor,
            announced_date,
            source
        FROM funding_rounds
        WHERE company_id = ?
        ORDER BY announced_date DESC, id DESC
    """
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    cursor.execute(sql, (company_id,))
    return cursor.fetchall()
