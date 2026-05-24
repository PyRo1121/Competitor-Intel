"""
Auto-Promotion System
Moves high-scoring candidates from company_candidates into the main companies table.
"""

import logging
import re
import sqlite3
from datetime import UTC, datetime

from db.connection import get_conn

logger = logging.getLogger(__name__)
PROMOTION_THRESHOLD = 0.65  # 65%+ score gets promoted


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def auto_promote_candidates() -> int:
    """Auto-promote high-scoring companies to active status."""
    logger.info("Running auto-promotion...")

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, description, score, discovery_source
        FROM company_candidates
        WHERE status = 'pending' AND score >= ?
        ORDER BY score DESC
        """,
        (PROMOTION_THRESHOLD,),
    )

    candidates = cursor.fetchall()
    promoted = 0
    now = datetime.now(UTC).isoformat()

    for cand_id, name, description, score, source in candidates:
        slug = _slugify(name)
        if not slug:
            logger.warning("Skipping candidate with empty slug: %r", name)
            continue

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO companies (
                    name, slug, description, industry, status, first_seen, last_updated
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    name,
                    slug,
                    description or f"Auto-promoted from {source or 'discovery'}",
                    None,
                    now,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                cursor.execute("SELECT id FROM companies WHERE slug = ? OR name = ?", (slug, name))
                if not cursor.fetchone():
                    logger.warning("Failed to promote %s: company row missing after insert", name)
                    continue

            cursor.execute(
                """
                UPDATE company_candidates
                SET status = 'promoted', last_updated = ?
                WHERE id = ?
                """,
                (now, cand_id),
            )
            promoted += 1
            logger.info("Promoted: %s (score=%.1f%%)", name, score * 100)

        except sqlite3.Error as exc:
            logger.warning("Failed to promote candidate %s: %s", name, exc)

    conn.commit()
    conn.close()

    logger.info("Promoted %s candidates.", promoted)
    return promoted


def run() -> int:
    return int(auto_promote_candidates() or 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
