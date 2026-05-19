#!/usr/bin/env python3
"""
Embedding Generator for Enriched Content
Generates embeddings for company profiles, funding rounds, and intelligence events
using Ollama HTTP API (no Python client dependency).
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger("embedding_generator")

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.connection import get_conn
from utils.http import post_json

OLLAMA_BASE = os.getenv("CI_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_EMBED_URL = f"{OLLAMA_BASE}/api/embed"
OLLAMA_EMBEDDINGS_URL = f"{OLLAMA_BASE}/api/embeddings"
EMBED_MODEL = "nomic-embed-text"


def get_embedding(text: str, model: str = EMBED_MODEL) -> Optional[List[float]]:
    """Generate embedding via Ollama HTTP API (/api/embed, fallback /api/embeddings)."""
    if not text or not text.strip():
        return None

    snippet = text.strip()[:2000]

    data = post_json(
        OLLAMA_EMBED_URL,
        {"model": model, "input": snippet},
        timeout=60.0,
    )
    if data:
        embeddings = data.get("embeddings")
        if embeddings and len(embeddings) > 0:
            return embeddings[0]

    data = post_json(
        OLLAMA_EMBEDDINGS_URL,
        {"model": model, "prompt": snippet},
        timeout=60.0,
    )
    if data:
        return data.get("embedding")

    logger.warning("Ollama embedding failed at %s", OLLAMA_BASE)
    return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two embeddings."""
    if not a or not b or len(a) != len(b):
        return 0.0
    arr_a = np.array(a)
    arr_b = np.array(b)
    norm = np.linalg.norm(arr_a) * np.linalg.norm(arr_b)
    if norm == 0:
        return 0.0
    return float(np.dot(arr_a, arr_b) / norm)


def embed_company_profiles(limit: int = 100) -> int:
    """Generate embeddings for company profiles."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT cd.id, c.name, cd.description_long, cd.business_model,
               cd.tech_stack, cd.headquarters, cd.team_size
        FROM company_details cd
        JOIN companies c ON c.id = cd.company_id
        WHERE cd.embedding IS NULL
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    embedded = 0

    for row in rows:
        text_parts = [row["name"]]
        if row["description_long"]:
            text_parts.append(row["description_long"])
        if row["business_model"]:
            text_parts.append(f"Business model: {row['business_model']}")
        if row["tech_stack"]:
            text_parts.append(f"Tech: {row['tech_stack']}")
        if row["headquarters"]:
            text_parts.append(f"HQ: {row['headquarters']}")
        if row["team_size"]:
            text_parts.append(f"Team: {row['team_size']} people")

        text = " ".join(text_parts)
        embedding = get_embedding(text)

        if embedding:
            cursor.execute("""
                UPDATE company_details SET embedding = ? WHERE id = ?
            """, (json.dumps(embedding), row["id"]))
            conn.commit()
            embedded += 1
            logger.info("Embedded company profile: %s", row["name"])
        else:
            logger.warning("Failed to embed: %s", row["name"])

    conn.close()
    logger.info("Company profile embeddings: %d/%d", embedded, len(rows))
    return embedded


def embed_funding_rounds(limit: int = 200) -> int:
    """Generate embeddings for funding rounds."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fr.id, c.name, fr.round_type, fr.amount_usd,
               fr.valuation_usd, fr.lead_investor
        FROM funding_rounds fr
        JOIN companies c ON c.id = fr.company_id
        WHERE fr.embedding IS NULL
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    embedded = 0

    for row in rows:
        text = f"{row['name']} {row['round_type']}"
        if row["amount_usd"]:
            text += f" ${row['amount_usd']:,}"
        if row["valuation_usd"]:
            text += f" at ${row['valuation_usd']:,} valuation"
        if row["lead_investor"]:
            text += f" led by {row['lead_investor']}"

        embedding = get_embedding(text)

        if embedding:
            cursor.execute("""
                UPDATE funding_rounds SET embedding = ? WHERE id = ?
            """, (json.dumps(embedding), row["id"]))
            conn.commit()
            embedded += 1

    conn.close()
    logger.info("Funding round embeddings: %d/%d", embedded, len(rows))
    return embedded


def embed_intelligence_events(limit: int = 300) -> int:
    """Generate embeddings for intelligence events."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ie.id, c.name, ie.event_type, ie.amount_usd, ie.source
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        WHERE ie.embedding IS NULL
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    embedded = 0

    for row in rows:
        text = f"{row['name'] or 'Unknown'} {row['event_type']}"
        if row["amount_usd"]:
            text += f" ${row['amount_usd']:,}"
        text += f" from {row['source']}"

        embedding = get_embedding(text)

        if embedding:
            cursor.execute("""
                UPDATE intelligence_events SET embedding = ? WHERE id = ?
            """, (json.dumps(embedding), row["id"]))
            conn.commit()
            embedded += 1

    conn.close()
    logger.info("Intelligence event embeddings: %d/%d", embedded, len(rows))
    return embedded


def run_embedding_generation() -> dict:
    """Generate embeddings for all enriched content."""
    logger.info("Starting embedding generation...")

    results = {
        "company_profiles": embed_company_profiles(),
        "funding_rounds": embed_funding_rounds(),
        "intelligence_events": embed_intelligence_events(),
    }

    total = sum(results.values())
    logger.info("Embedding generation complete: %d total embeddings", total)
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    run_embedding_generation()
