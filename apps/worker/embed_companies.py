"""
Embed all companies using qwen3-embedding:4b and store in the database.
"""

import json
import logging
import sqlite3
from pathlib import Path

from embeddings import get_embedding

logger = logging.getLogger("embed_companies")

DB_PATH = Path.home() / ".hermes" / "agents" / "competitor_intel" / "competitor_intel.db"


def embed_companies():
    """Embed all companies using the configured embedding model."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Add embedding column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE companies ADD COLUMN embedding BLOB")
    except sqlite3.OperationalError:
        pass  # column already exists

    cursor.execute(
        "SELECT id, name, description FROM companies WHERE embedding IS NULL OR embedding = ''"
    )
    rows = cursor.fetchall()

    logger.info("Embedding %s companies...", len(rows))

    for company_id, name, description in rows:
        text = f"{name}. {description or ''}"
        try:
            embedding = get_embedding(text)
            cursor.execute(
                "UPDATE companies SET embedding = ? WHERE id = ?",
                (json.dumps(embedding), company_id),
            )
            logger.info("  Embedded: %s", name)
        except Exception as e:
            logger.error("Failed to embed %s: %s", name, e)

    conn.commit()
    conn.close()
    logger.info("Company embeddings complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    embed_companies()
