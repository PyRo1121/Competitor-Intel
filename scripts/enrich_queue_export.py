#!/usr/bin/env python3
"""
Export events for Hermes/Grok review (label + company_id). No local LLM.

Write data/enrich_queue.jsonl + data/companies_catalog.json for the agent.
Apply results with scripts/enrich_queue_apply.py.
"""

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

logger = logging.getLogger("enrich_queue_export")

LABELS = (
    "Funding Round",
    "Product Launch",
    "Partnership",
    "Acquisition",
    "Hiring",
    "Research Publication",
    "General News",
)


def _company_catalog(cur) -> list[dict]:
    cur.execute(
        """
        SELECT id, name, slug, website, github_org, x_handle
        FROM companies
        ORDER BY name
        """
    )
    return [
        {
            "id": r[0],
            "name": r[1],
            "slug": r[2],
            "website": r[3],
            "github_org": r[4],
            "x_handle": r[5],
        }
        for r in cur.fetchall()
    ]


def fetch_queue(cur, *, limit: int, min_confidence: float) -> list[dict]:
    cur.execute("SELECT LOWER(name) FROM companies WHERE LENGTH(name) >= 4")
    names = [r[0] for r in cur.fetchall()]

    cur.execute(
        """
        SELECT ie.id, ie.event_type, ie.company_id, ie.confidence,
               ie.description, ie.source_url, rs.data_json
        FROM intelligence_events ie
        LEFT JOIN raw_signals rs ON rs.id = ie.raw_signal_id
        ORDER BY ie.created_at DESC
        LIMIT ?
        """,
        (limit * 5,),
    )
    out: list[dict] = []
    for row in cur.fetchall():
        eid, event_type, company_id, confidence, desc, source_url, data_json = row
        blob = (desc or "").lower() + " " + (data_json or "").lower()
        low_conf = confidence is not None and confidence < min_confidence
        actionable_null = company_id is None and any(n in blob for n in names)
        if not low_conf and not actionable_null:
            continue
        title = desc or ""
        if data_json:
            try:
                data = json.loads(data_json)
                if isinstance(data, dict):
                    title = data.get("title") or data.get("headline") or title
            except json.JSONDecodeError:
                pass
        out.append(
            {
                "event_id": eid,
                "headline": title[:500],
                "current_event_type": event_type,
                "current_company_id": company_id,
                "confidence": confidence,
                "source_url": source_url,
                "reason": "low_confidence" if low_conf else "actionable_null_company",
            }
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Hermes enrich queue")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-confidence", type=float, default=0.38)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "hermes_enrich",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    catalog = _company_catalog(cur)
    queue = fetch_queue(cur, limit=args.limit, min_confidence=args.min_confidence)
    conn.close()

    catalog_path = args.out_dir / "companies_catalog.json"
    queue_path = args.out_dir / "enrich_queue.jsonl"
    prompt_path = args.out_dir / "PROMPT.md"

    catalog_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    with queue_path.open("w", encoding="utf-8") as f:
        for item in queue:
            f.write(json.dumps(item) + "\n")

    prompt_path.write_text(
        f"""# Hermes enrich queue

For each line in `enrich_queue.jsonl`, return one JSON object (JSONL) with:

- `event_id` (required, unchanged)
- `event_type` one of: {", ".join(LABELS)}
- `company_id` (integer from companies_catalog.json, or null if not a tracked company)
- `notes` (optional, short reason)

Rules:
- Only set company_id if the company appears in companies_catalog.json
- Use web search only when the headline names a company not in the catalog
- Do not invent company ids

Write output to `enrich_results.jsonl` in this directory, then run:
`make enrich-queue-apply`
""",
        encoding="utf-8",
    )

    logger.info("Exported %d events → %s", len(queue), queue_path)
    logger.info("Catalog: %d companies → %s", len(catalog), catalog_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
