#!/usr/bin/env python3
"""Dispatch X fetch to xurl or Grok based on CI_X_PROVIDER (default: grok)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ci_paths import MONOREPO_ROOT, ensure_app_paths

ensure_app_paths()

OUT = MONOREPO_ROOT / "data" / "hermes_enrich" / "grok_x_results.json"
QUERIES_FILE = MONOREPO_ROOT / "data" / "hermes_enrich" / "x_monitor_queries.json"


def _main_grok(argv: list[str] | None = None) -> int:
    from collectors.grok_x_fetcher import fetch_and_write, resolve_xai_credentials
    from collectors.x_query_builder import load_queries_file

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Fetch X via Grok x_search (xAI API)")
    parser.add_argument(
        "--max-queries",
        type=int,
        default=int(os.environ.get("GROK_X_MAX_QUERIES", "10")),
        help="Limit global queries (default 10; use 1 for smoke)",
    )
    parser.add_argument("-o", "--output", type=Path, default=OUT)
    parser.add_argument("--check", action="store_true", help="Only verify xAI credentials")
    args = parser.parse_args(argv)

    _key, _base, provider = resolve_xai_credentials()
    if args.check:
        print(f"xAI credentials OK ({provider})")
        return 0

    queries = load_queries_file(QUERIES_FILE)
    fetch_and_write(args.output, queries, max_queries=args.max_queries)
    return 0


def main(argv: list[str] | None = None) -> int:
    provider = os.environ.get("CI_X_PROVIDER", "grok").strip().lower()
    if provider not in ("xurl", "grok"):
        print(f"Invalid CI_X_PROVIDER={provider!r} (use xurl or grok)", file=sys.stderr)
        return 1

    print(f"CI_X_PROVIDER={provider}", file=sys.stderr)
    if provider == "xurl":
        from x_refresh.fetch_xurl import main as xurl_main

        return xurl_main()

    try:
        return _main_grok(argv)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
