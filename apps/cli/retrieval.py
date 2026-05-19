#!/usr/bin/env python3
"""
Semantic Retrieval for Competitor Intelligence
Embedding similarity + Tier 1/2 investor ranking boost.
"""

import json
import logging
import sqlite3
import sys

from embeddings import cosine_similarity, get_embedding
from investor_tiers import get_investor_tier
from ci_paths import db_path, ensure_app_paths

ensure_app_paths()

logger = logging.getLogger("retrieval")

DB_PATH = db_path()


def semantic_search(query: str, top_k: int = 10):
    """Perform semantic search over intelligence events with investor tier boosting."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    q_emb = get_embedding(query)

    cur.execute(
        """
        SELECT event_type, amount_usd, lead_investor, source,
               announced_date, embedding
        FROM intelligence_events
        WHERE embedding IS NOT NULL
        """
    )
    events = cur.fetchall()

    scored = []
    for row in events:
        try:
            emb = json.loads(row["embedding"])
            base = cosine_similarity(q_emb, emb)

            investor = row["lead_investor"] or ""
            tier = get_investor_tier(investor) if investor else 0
            boost = 0.08 if tier == 1 else (0.04 if tier == 2 else 0.0)

            final = min(1.0, base + boost)
            scored.append((final, dict(row), tier))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    results = scored[:top_k]
    conn.close()

    logger.info('Semantic Search: "%s"', query)
    logger.info("=" * 60)
    for i, (score, r, tier) in enumerate(results, 1):
        amt = f"${r['amount_usd']:,}" if r.get("amount_usd") else "Undisclosed"
        tag = " [TIER 1]" if tier == 1 else (" [Tier 2]" if tier == 2 else "")
        logger.info("%s. [%.3f] %s — %s%s", i, score, r.get('event_type'), amt, tag)
        logger.info("   %s • %s", r.get('source'), r.get('announced_date') or 'recent')

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "large AI funding rounds"
    semantic_search(q)
