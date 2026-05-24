#!/usr/bin/env python3
"""Funding round investors → cap_table_holdings (Track 5 P5-1)."""

from __future__ import annotations

import logging

from db.connection import transaction

from collectors.enrichment.funding_investors import normalize_investor_name
from collectors.entity_resolution import normalize_alias

logger = logging.getLogger("cap_table_rollup")


def _holder_normalized(name: str) -> str:
    return normalize_alias(normalize_investor_name(name))


def sync_cap_table_from_rounds(conn) -> dict[str, int]:
    """Upsert cap rows from round_participants (no ownership % until filings provide it)."""
    rows = conn.execute(
        """
        SELECT
            fr.company_id,
            fr.id AS round_id,
            fr.announced_date,
            rp.investor_id,
            rp.role,
            rp.is_lead,
            rp.corroboration_score,
            i.name AS holder_name
        FROM round_participants rp
        JOIN funding_rounds fr ON fr.id = rp.funding_round_id
        JOIN investor_firms i ON i.id = rp.investor_id
        WHERE fr.company_id IS NOT NULL
        """
    ).fetchall()

    upserted = 0
    for row in rows:
        holder = (row["holder_name"] or "").strip()
        if len(holder) < 2:
            continue
        norm = _holder_normalized(holder)
        if len(norm) < 2:
            continue
        round_id = int(row["round_id"])
        investor_id = int(row["investor_id"])
        company_id = int(row["company_id"])
        is_lead = int(row["is_lead"] or 0)
        role = (row["role"] or "").strip()
        share_class = "lead" if is_lead else (role or "investor")
        source_url = f"funding_round:{round_id}:investor:{investor_id}"
        confidence = float(row["corroboration_score"] or 0.5)

        cur = conn.execute(
            """
            INSERT INTO cap_table_holdings (
                company_id, holder_name, holder_normalized, ownership_pct,
                share_class, as_of_date, source, source_url, confidence
            ) VALUES (?, ?, ?, NULL, ?, ?, 'funding_round', ?, ?)
            ON CONFLICT(company_id, holder_normalized, source_url) DO UPDATE SET
                holder_name = excluded.holder_name,
                share_class = excluded.share_class,
                as_of_date = excluded.as_of_date,
                confidence = excluded.confidence
            """,
            (
                company_id,
                holder[:200],
                norm,
                share_class[:64],
                row["announced_date"],
                source_url,
                confidence,
            ),
        )
        if cur.rowcount:
            upserted += 1

    stats = {"participants_scanned": len(rows), "holdings_upserted": upserted}
    logger.info("Cap table rollup: %s", stats)
    return stats


def run() -> dict:
    with transaction() as conn:
        return sync_cap_table_from_rounds(conn)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
