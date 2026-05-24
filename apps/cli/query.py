"""
Semantic query CLI — uses enrichment reranker (Ollama embeddings).

Usage:
    uv run python apps/cli/query.py "EU neobank funding"
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from collectors.enrichment.reranker import unified_search  # noqa: E402

logger = logging.getLogger("query")


def main() -> None:
    if len(sys.argv) < 2:
        logger.info('Usage: uv run python apps/cli/query.py "your search query"')
        return

    query = " ".join(sys.argv[1:])
    logger.info("\nQuery: %s\n", query)

    results = unified_search(query, top_k=8)

    logger.info("=== Top Companies ===")
    for i, c in enumerate(results.get("companies", []), 1):
        logger.info("%s. %s (score: %.3f)", i, c["name"], c["score"])

    logger.info("\n=== Funding Rounds ===")
    for i, f in enumerate(results.get("funding", []), 1):
        lead = f" (led by {f.get('lead')})" if f.get("lead") else ""
        logger.info(
            "%s. %s — %s $%s%s",
            i,
            f.get("company", "?"),
            f.get("round", "?"),
            f.get("amount", "?"),
            lead,
        )

    logger.info("\n=== Intelligence Events ===")
    for i, e in enumerate(results.get("events", []), 1):
        logger.info(
            "%s. %s | %s (score: %.3f)",
            i,
            e.get("company", "?"),
            e.get("event_type", "?"),
            e.get("score", 0.0),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
