#!/usr/bin/env python3
"""
Hermes-compatible Grok X ingest (restores pre-split workflow).

Before the monorepo split, Hermes ran Python in ~/.hermes/agents/competitor_intel/
and called process_grok_x_results() / store_grok_batch() directly against the DB.

Use this script from Hermes execute_code or shell — same outcome, monorepo DB via CI_DB_PATH.

Examples:
  # Per-company (stdin JSON array of posts)
  echo '[{"post_id":"1","text":"...","url":"https://x.com/..."}]' | \\
    python integrations/hermes/ingest_grok_x.py company Anthropic

  # Global query batch
  python integrations/hermes/ingest_grok_x.py query \\
    '("raised" OR "Series A") min_faves:5' --file /tmp/posts.json

  # Full grok_x_results.json (same as make grok-x-ingest without fanout/funding)
  python integrations/hermes/ingest_grok_x.py batch \\
    --file data/hermes_enrich/grok_x_results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

MONOREPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MONOREPO / "packages" / "py-core"))
sys.path.insert(0, str(MONOREPO / "packages" / "py-collectors"))
sys.path.insert(0, str(MONOREPO / "apps" / "worker"))

os.environ.setdefault("CI_DB_PATH", str(MONOREPO / "data" / "competitor_intel.db"))

from ci_paths import ensure_app_paths  # noqa: E402

ensure_app_paths()

from collectors.x_monitor import (  # noqa: E402
    process_grok_query_results,
    process_grok_x_results,
)
from collectors.x_signal_collector import store_grok_batch  # noqa: E402


def _load_posts(path: Path | None) -> List[Dict[str, Any]]:
    if path:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = json.loads(sys.stdin.read())
    if isinstance(data, dict) and "results" in data:
        inner = data["results"]
        return inner if isinstance(inner, list) else []
    if isinstance(data, list):
        return data
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Grok X JSON into Competitor Intel DB")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_company = sub.add_parser("company", help="Posts for one tracked company")
    p_company.add_argument("name", help="Company name or @handle")
    p_company.add_argument("--file", type=Path, help="JSON file (default: stdin)")

    p_query = sub.add_parser("query", help="Posts from a global search query")
    p_query.add_argument("query", help="Search string used in Grok")
    p_query.add_argument("--file", type=Path, help="JSON file (default: stdin)")

    p_batch = sub.add_parser("batch", help="Full grok_x_results.json batches file")
    p_batch.add_argument(
        "--file",
        type=Path,
        default=MONOREPO / "data" / "hermes_enrich" / "grok_x_results.json",
    )

    args = parser.parse_args()
    db = os.environ.get("CI_DB_PATH", "")
    print(f"CI_DB_PATH={db}")

    if args.mode == "company":
        posts = _load_posts(args.file)
        n = process_grok_x_results(args.name, posts)
        print(f"ingested_signals={n} company={args.name} posts={len(posts)}")
        return 0

    if args.mode == "query":
        posts = _load_posts(args.file)
        n = process_grok_query_results(args.query, posts)
        print(f"ingested_signals={n} query={args.query[:60]!r} posts={len(posts)}")
        return 0

    if args.mode == "batch":
        if not args.file.is_file():
            print(f"ERROR: batch file not found: {args.file}", file=sys.stderr)
            return 1
        batches = json.loads(args.file.read_text(encoding="utf-8"))
        if isinstance(batches, dict) and "batches" in batches:
            batches = batches["batches"]
        total = 0
        for batch in batches:
            if not isinstance(batch, dict):
                continue
            query = batch.get("query") or "grok_batch"
            results = batch.get("results") or batch.get("posts") or []
            company = batch.get("company") or batch.get("company_name")
            if isinstance(results, list):
                total += store_grok_batch(query, results, company_name=company)
        print(f"ingested_signals={total} batches={len(batches)}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
