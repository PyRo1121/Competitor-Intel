#!/usr/bin/env python3
"""Fetch X via Hermes x_search (OAuth) → grok_x_results.json."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.grok_x_fetcher import fetch_and_write, resolve_xai_credentials  # noqa: E402
from collectors.x_query_builder import load_queries_file  # noqa: E402

OUT = ROOT / "data" / "hermes_enrich" / "grok_x_results.json"
QUERIES_FILE = ROOT / "data" / "hermes_enrich" / "x_monitor_queries.json"


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Fetch X via Grok x_search (xAI API)")
    parser.add_argument(
        "--max-queries",
        type=int,
        default=int(__import__("os").environ.get("GROK_X_MAX_QUERIES", "10")),
        help="Limit global queries (default 10; use 1 for smoke)",
    )
    parser.add_argument("-o", "--output", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true", help="Only verify XAI_API_KEY")
    args = parser.parse_args()

    _key, _base, provider = resolve_xai_credentials()
    if args.check:
        print(f"xAI credentials OK ({provider})")
        return 0

    queries = load_queries_file(QUERIES_FILE)

    fetch_and_write(args.output, queries, max_queries=args.max_queries)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
