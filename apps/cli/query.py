"""
Simple Query Interface for Competitor Intelligence RAG
Usage:
    python query.py "companies like Cursor"
    python query.py "recent large AI funding rounds"
"""

import logging
import sys
from retrieval import search_companies, search_funding_events, search_all

logger = logging.getLogger("query")

def main():
    """Main entry point for querying the competitor intelligence database."""
    if len(sys.argv) < 2:
        logger.info("Usage: python query.py \"your search query\"")
        logger.info("Example: python query.py \"companies like Cursor that raised funding\"")
        return

    query = " ".join(sys.argv[1:])
    logger.info("\nQuery: %s\n", query)

    results = search_all(query, top_k=8)

    logger.info("=== Top Companies ===")
    for i, c in enumerate(results["companies"], 1):
        logger.info("%s. %s (score: %.3f)", i, c['name'], c['score'])

    logger.info("\n=== Relevant Funding Events ===")
    if results["funding_events"]:
        for i, f in enumerate(results["funding_events"], 1):
            lead = f" (led by {f['lead']})" if f['lead'] else ""
            logger.info("%s. %s — %s $%s%s", i, f['company'], f['round'], f['amount'], lead)
    else:
        logger.info("No relevant funding events found.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()