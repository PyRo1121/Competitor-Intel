#!/usr/bin/env python3
"""Export Grok X search queries for Hermes / fetch_x.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.x_monitor import get_x_query_prompt  # noqa: E402
from collectors.x_query_builder import build_query_payload  # noqa: E402
from db.connection import get_conn  # noqa: E402

OUT_DIR = ROOT / "data" / "hermes_enrich"
OUT_FILE = OUT_DIR / "x_monitor_queries.json"
PROMPT_FILE = OUT_DIR / "PROMPT_X.md"


def main() -> int:
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
    args = parser.parse_args()
    enriched = args.enriched or not args.baseline_only

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
uv run python scripts/grok_x_normalize.py path/to/hermes_raw.json \\
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


if __name__ == "__main__":
    raise SystemExit(main())
