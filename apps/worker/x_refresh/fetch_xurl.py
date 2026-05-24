#!/usr/bin/env python3
"""Fetch X via official xurl CLI (X API v2) → grok_x_results.json."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

from collectors.x_query_builder import load_queries_file  # noqa: E402
from collectors.xurl_fetcher import check_xurl_ready, fetch_and_write  # noqa: E402

OUT = MONOREPO_ROOT / "data" / "hermes_enrich" / "grok_x_results.json"
QUERIES_FILE = MONOREPO_ROOT / "data" / "hermes_enrich" / "x_monitor_queries.json"


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Fetch X via xurl (official X API CLI)")
    parser.add_argument(
        "--max-queries",
        type=int,
        default=int(os.environ.get("XURL_MAX_QUERIES", "10")),
        help="Limit global queries (default 10; use 1 for smoke)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=int(os.environ.get("XURL_SEARCH_N", "10")),
        help="Posts per query (default 10)",
    )
    parser.add_argument("-o", "--output", type=Path, default=OUT)
    parser.add_argument(
        "--check", action="store_true", help="Only verify xurl is installed and authed"
    )
    args = parser.parse_args()

    ready, msg = check_xurl_ready()
    if args.check:
        if ready:
            print(msg)
            return 0
        print(msg, file=sys.stderr)
        return 1

    if not ready:
        print(msg, file=sys.stderr)
        return 1

    queries = load_queries_file(QUERIES_FILE)

    fetch_and_write(
        args.output,
        queries,
        max_queries=args.max_queries,
        max_results=args.max_results,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        logging.error("%s", exc)
        raise SystemExit(1) from exc
