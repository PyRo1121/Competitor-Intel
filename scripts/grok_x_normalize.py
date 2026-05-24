#!/usr/bin/env python3
"""
Normalize Hermes/Grok X output into grok_x_results.json for x_signal_collector.

Accepts:
  - Full batch array: [{"query": "...", "results": [...]}, ...]
  - Wrapper: {"batches": [...]}
  - JSONL: one batch object or one post object per line
  - Single post object (wrapped as one batch)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "hermes_enrich" / "grok_x_results.json"


def _is_post(obj: dict[str, Any]) -> bool:
    return bool(obj.get("post_id") or obj.get("text") or obj.get("url"))


def _normalize_post(raw: dict[str, Any]) -> dict[str, Any]:
    text = raw.get("text") or raw.get("content") or ""
    url = raw.get("url") or raw.get("post_url") or ""
    urls = raw.get("urls")
    if not isinstance(urls, list):
        urls = []
    post_id = str(raw.get("post_id") or raw.get("id") or "")
    return {
        "post_id": post_id,
        "text": text,
        "posted_at": raw.get("posted_at") or raw.get("created_at"),
        "likes": raw.get("likes", raw.get("favorite_count", 0)),
        "retweets": raw.get("retweets", raw.get("retweet_count", 0)),
        "replies": raw.get("replies", raw.get("reply_count", 0)),
        "url": url,
        "urls": [u for u in urls if isinstance(u, str) and u.startswith("http")],
        "companies_detected": raw.get("companies_detected") or raw.get("companies") or [],
        "is_founder_post": bool(raw.get("is_founder_post", False)),
        "sentiment": raw.get("sentiment"),
    }


def _normalize_batch(raw: dict[str, Any]) -> dict[str, Any]:
    query = raw.get("query") or raw.get("search") or "grok_query"
    company = raw.get("company") or raw.get("company_name")
    results_in = raw.get("results") or raw.get("posts") or []
    posts: list[dict[str, Any]] = []
    if isinstance(results_in, list):
        for item in results_in:
            if isinstance(item, dict) and _is_post(item):
                posts.append(_normalize_post(item))
    batch: dict[str, Any] = {"query": query, "results": posts}
    if company:
        batch["company"] = company
    return batch


def parse_text(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []

    # JSONL: try line-by-line first if multiple lines without wrapping [
    if "\n" in text and not text.lstrip().startswith("["):
        batches: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            batches.extend(_expand_object(obj))
        return batches

    data = json.loads(text)
    return _expand_object(data)


def _expand_object(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        out: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                out.extend(_expand_object(item))
        return out
    if not isinstance(data, dict):
        return []
    if "batches" in data and isinstance(data["batches"], list):
        return _expand_object(data["batches"])
    if "results" in data or "posts" in data:
        return [_normalize_batch(data)]
    if _is_post(data):
        return [_normalize_batch({"query": "inline_post", "results": [data]})]
    return []


def parse_input(path: Path) -> list[dict[str, Any]]:
    return parse_text(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build grok_x_results.json from Grok/Hermes output"
    )
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Grok JSON or JSONL (default: stdin)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output path (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    batches = parse_input(args.input) if args.input else parse_text(sys.stdin.read())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(batches, indent=2), encoding="utf-8")
    post_count = sum(len(b.get("results") or []) for b in batches)
    print(f"Wrote {args.output} — {len(batches)} batches, {post_count} posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
