#!/usr/bin/env python3
"""
JSON semantic search for API and automation.

Usage:
  uv run python apps/cli/semantic_search.py "EU fintech Series B" --limit 10
  uv run python apps/cli/semantic_search.py "query" --json --limit 5
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from ci_paths import ensure_app_paths

ensure_app_paths()

from collectors.enrichment.reranker import unified_search  # noqa: E402

logger = logging.getLogger("semantic_search")


def run_search(query: str, limit: int) -> dict:
    """Return structured search payload for HTTP consumers."""
    if not query.strip():
        return {
            "ok": False,
            "error": "empty_query",
            "query": query,
            "companies": [],
            "funding": [],
            "events": [],
            "top_results": [],
        }

    try:
        results = unified_search(query.strip(), top_k=limit)
        return {
            "ok": True,
            "query": query.strip(),
            "mode": "semantic",
            "companies": results.get("companies", []),
            "funding": results.get("funding", []),
            "events": results.get("events", []),
            "top_results": results.get("top_results", []),
        }
    except Exception as exc:
        logger.exception("Semantic search failed")
        return {
            "ok": False,
            "error": str(exc),
            "query": query.strip(),
            "companies": [],
            "funding": [],
            "events": [],
            "top_results": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantic search (Ollama embeddings)")
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--limit", type=int, default=15, help="Max results per bucket")
    parser.add_argument("--json", action="store_true", help="Emit JSON only (for API bridge)")
    args = parser.parse_args()

    payload = run_search(args.query, args.limit)

    if args.json:
        print(json.dumps(payload, default=str))
    else:
        if not payload.get("ok"):
            logger.error("Search failed: %s", payload.get("error"))
            return 1
        for label, key in (
            ("Companies", "companies"),
            ("Funding", "funding"),
            ("Events", "events"),
        ):
            items = payload.get(key, [])
            if items:
                print(f"\n=== {label} ===")
                for i, row in enumerate(items, 1):
                    name = row.get("name") or row.get("company") or "?"
                    score = row.get("score", 0.0)
                    print(f"  {i}. {name} ({score:.3f})")

    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    raise SystemExit(main())
