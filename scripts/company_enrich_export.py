#!/usr/bin/env python3
"""Export thin company profile claims for Hermes/Grok enrich (mirrors funding_enrich_export)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from ci_paths import ensure_app_paths

ensure_app_paths()

from db.connection import get_conn  # noqa: E402

logger = logging.getLogger("company_enrich_export")

PROMPT = """# Company profile enrich queue

For each JSONL line, read headline/snippet and source_url. Return one JSON object per line with:
- `claim_id` (unchanged integer)
- optional: `field_key`, `field_value`, `headline`, `snippet`, `notes`

Do not invent facts. Prefer official site and filings.

Output: `company_enrich_results.jsonl` then `make company-enrich-apply`
"""


def fetch_thin_profile_claims(cur, *, limit: int) -> list[dict]:
    cur.execute(
        """
        SELECT id, company_id, field_key, field_value, source, source_url,
               source_tier, headline, snippet
        FROM company_profile_claims
        WHERE (field_value IS NULL OR field_value = '' OR LENGTH(field_value) < 3)
           OR extraction_confidence IS NULL
        ORDER BY source_weight DESC, extracted_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    out: list[dict] = []
    for row in cur.fetchall():
        (
            claim_id,
            company_id,
            field_key,
            field_value,
            source,
            source_url,
            source_tier,
            headline,
            snippet,
        ) = row
        out.append(
            {
                "claim_id": claim_id,
                "company_id": company_id,
                "field_key": field_key,
                "current_value": field_value,
                "source": source,
                "source_url": source_url,
                "source_tier": source_tier,
                "headline": (headline or "")[:500],
                "snippet": (snippet or "")[:1200],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Export company profile claims for Hermes enrich")
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data" / "hermes_enrich")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    queue = fetch_thin_profile_claims(cur, limit=args.limit)
    conn.close()

    queue_path = args.out_dir / "company_enrich_queue.jsonl"
    prompt_path = args.out_dir / "PROMPT_COMPANY.md"
    with queue_path.open("w", encoding="utf-8") as f:
        for item in queue:
            f.write(json.dumps(item) + "\n")
    prompt_path.write_text(PROMPT, encoding="utf-8")

    logger.info("Exported %d company profile claims → %s", len(queue), queue_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
