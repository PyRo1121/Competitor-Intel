"""
Embed all funding events using qwen3-embedding:4b.
"""

import json
import logging
import sqlite3
from contextlib import suppress

from ci_paths import db_path

from embeddings import get_embedding

logger = logging.getLogger("embed_funding_events")

DB_PATH = db_path()


def embed_funding_events():
    """Embed all funding events using the configured embedding model."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Add embedding column
    with suppress(sqlite3.OperationalError):
        cursor.execute("ALTER TABLE funding_events ADD COLUMN embedding BLOB")

    cursor.execute(
        """
        SELECT id, round_type, amount_usd, lead_investor, announced_date
        FROM funding_events
        WHERE embedding IS NULL OR embedding = ''
        """
    )
    rows = cursor.fetchall()

    logger.info("Embedding %s funding events...", len(rows))

    for event_id, round_type, amount, lead, date in rows:
        text = (
            f"{round_type or ''} round of ${amount or 0:,} "
            f"led by {lead or 'Unknown'} on {date or ''}"
        )
        try:
            embedding = get_embedding(text)
            cursor.execute(
                "UPDATE funding_events SET embedding = ? WHERE id = ?",
                (json.dumps(embedding), event_id),
            )
            logger.info("  Embedded funding event #%s", event_id)
        except Exception as e:
            logger.error("Failed to embed event %s: %s", event_id, e)

    conn.commit()
    conn.close()
    logger.info("Funding event embeddings complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    embed_funding_events()
