"""Export X monitor queries and normalize Hermes/Grok JSON for x_signal_collector."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ci_paths import MONOREPO_ROOT
from db.connection import get_conn

from collectors.x_monitor import get_x_query_prompt
from collectors.x_query_builder import build_query_payload

OUT_DIR = MONOREPO_ROOT / "data" / "hermes_enrich"
OUT_FILE = OUT_DIR / "x_monitor_queries.json"
PROMPT_FILE = OUT_DIR / "PROMPT_X.md"
DEFAULT_RESULTS_OUT = OUT_DIR / "grok_x_results.json"


def export_monitor_queries(*, enriched: bool = True) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, x_handle FROM companies
        WHERE x_handle IS NOT NULL AND trim(x_handle) != ''
        ORDER BY name
        """
    )
    companies = [{"name": r[0], "handle": r[1]} for r in cur.fetchall()]
    conn.close()

    payload = build_query_payload(enriched=enriched)
    company_prompts = [
        {
            "company": c["name"],
            "handle": c["handle"],
            "prompt": get_x_query_prompt(c["handle"], days=3),
        }
        for c in companies
    ]
    payload["company_prompts"] = company_prompts
    OUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    global_queries = payload.get("global_queries") or []
    derived = payload.get("derived_queries") or []
    ai_q = payload.get("ai_queries") or []
    global_block = "\n".join(f"- `{q}`" for q in global_queries)
    derived_block = "\n".join(f"- `{q}`" for q in derived) if derived else "_none_"
    ai_block = (
        "\n".join(f"- `{q}`" for q in ai_q) if ai_q else "_none (set CI_X_QUERY_AI_EXPAND=1)_"
    )

    mode = (
        "enriched (baseline + pipeline-derived" + (" + AI)" if ai_q else ")")
        if enriched
        else "baseline only"
    )
    PROMPT_FILE.write_text(
        f"""# Hermes / Grok — X search ingest

Mode: **{mode}**. Run native X search for **global_queries** in `x_monitor_queries.json`.
Company prompts are for optional per-handle Hermes runs.

## Output file (required)

Save to: `data/hermes_enrich/grok_x_results.json`

```json
[
  {{
    "query": "<exact search string used>",
    "results": [
      {{
        "post_id": "string",
        "text": "full post text",
        "posted_at": "ISO-8601",
        "likes": 0,
        "retweets": 0,
        "replies": 0,
        "url": "https://x.com/user/status/123",
        "urls": ["https://techcrunch.com/article", "https://company.com/blog"],
        "companies_detected": ["CompanyName"],
        "is_founder_post": false,
        "sentiment": 0.0
      }}
    ]
  }}
]
```

## Global queries ({len(global_queries)})

{global_block}

## Derived from pipeline ({len(derived)})

{derived_block}

## AI-expanded ({len(ai_q)})

{ai_block}

## After Grok returns

```bash
uv run python -m collectors.grok_x_export normalize path/to/hermes_raw.json \\
  -o data/hermes_enrich/grok_x_results.json
make grok-x-ingest
```
""",
        encoding="utf-8",
    )

    stats = payload.get("build_stats") or {}
    print(
        f"Wrote {OUT_FILE} ({len(global_queries)} global: "
        f"{len(payload.get('baseline_queries') or [])} baseline, "
        f"{len(derived)} derived, {len(ai_q)} ai; "
        f"{len(company_prompts)} company prompts; enriched={enriched})"
    )
    if stats:
        print(f"  build_stats: {stats}")
    print(f"Wrote {PROMPT_FILE}")
    return 0


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


def parse_text(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []

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


def normalize_hermes_input(
    text: str,
    *,
    output: Path = DEFAULT_RESULTS_OUT,
) -> tuple[Path, int, int]:
    batches = parse_text(text)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(batches, indent=2), encoding="utf-8")
    post_count = sum(len(b.get("results") or []) for b in batches)
    return output, len(batches), post_count


def main_export(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export X monitor queries JSON + PROMPT_X.md")
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Static registry queries only (for grok cron before daily)",
    )
    parser.add_argument(
        "--enriched",
        action="store_true",
        help="Add DB-derived + optional AI queries (default unless --baseline-only)",
    )
    args = parser.parse_args(argv)
    enriched = args.enriched or not args.baseline_only
    return export_monitor_queries(enriched=enriched)


def main_normalize(argv: list[str] | None = None) -> int:
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
        default=DEFAULT_RESULTS_OUT,
        help=f"Output path (default: {DEFAULT_RESULTS_OUT})",
    )
    args = parser.parse_args(argv)
    text = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    out, n_batches, n_posts = normalize_hermes_input(text, output=args.output)
    print(f"Wrote {out} — {n_batches} batches, {n_posts} posts")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if argv and argv[0] == "normalize":
        return main_normalize(argv[1:])
    if argv and argv[0] == "export":
        return main_export(argv[1:])
    return main_export(argv)


if __name__ == "__main__":
    raise SystemExit(main())
