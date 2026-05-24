#!/usr/bin/env python3
"""
Export funding claims that need structured investor/deal enrichment for Hermes/Grok.

Writes data/hermes_enrich/funding_enrich_queue.jsonl + PROMPT_FUNDING.md.
Apply with scripts/funding_enrich_apply.py.
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

logger = logging.getLogger("funding_enrich_export")

PROMPT = """# Funding enrich queue (granular)

For each line in `funding_enrich_queue.jsonl`, read the headline/snippet and source_url.
Return one JSON object per line (JSONL) with:

Required:
- `claim_id` (integer, unchanged)

Optional structured fields (omit if unknown):
- `lead_investor` (string)
- `co_investors` (array of strings)
- `amount_usd` (integer, USD)
- `valuation_usd` (integer, USD)
- `pre_money_valuation_usd` (integer)
- `post_money_valuation_usd` (integer)
- `round_type` (e.g. Seed, Series A, Series B, Debt)
- `instrument_type` one of: equity, safe, convertible_note, debt
- `announced_date` (YYYY-MM-DD if known)
- `notes` (short extraction notes)

Rules:
- Use the article at source_url when the snippet is thin; do not invent investors.
- Prefer exact firm names as reported (e.g. "Andreessen Horowitz" not "a16z"
  unless article uses a16z).
- `co_investors` must not include the lead_investor.

Write output to `funding_enrich_results.jsonl` in this directory, then run:
`make funding-enrich-apply`
"""


def fetch_thin_claims(cur, *, limit: int) -> list[dict]:
    cur.execute(
        """
        SELECT frc.id, frc.company_id, c.name AS company_name,
               frc.round_type, frc.amount_usd, frc.lead_investor, frc.co_investors,
               frc.headline, frc.snippet, frc.source_url, frc.source_tier,
               frc.instrument_type, frc.announced_date,
               (SELECT COUNT(*) FROM funding_claim_participants fcp
                WHERE fcp.funding_round_claim_id = frc.id) AS participant_rows
        FROM funding_round_claims frc
        JOIN companies c ON c.id = frc.company_id
        WHERE frc.lead_investor IS NULL
           OR frc.lead_investor = ''
           OR (SELECT COUNT(*) FROM funding_claim_participants fcp
               WHERE fcp.funding_round_claim_id = frc.id) < 1
        ORDER BY frc.source_weight DESC, frc.extracted_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    out: list[dict] = []
    for row in cur.fetchall():
        (
            claim_id,
            company_id,
            company_name,
            round_type,
            amount_usd,
            lead,
            co,
            headline,
            snippet,
            source_url,
            source_tier,
            instrument,
            announced,
            participant_rows,
        ) = row
        out.append(
            {
                "claim_id": claim_id,
                "company_id": company_id,
                "company_name": company_name,
                "round_type": round_type,
                "amount_usd": amount_usd,
                "current_lead_investor": lead,
                "current_co_investors": co,
                "headline": (headline or "")[:500],
                "snippet": (snippet or "")[:1200],
                "source_url": source_url,
                "source_tier": source_tier,
                "instrument_type": instrument,
                "announced_date": announced,
                "participant_rows": participant_rows,
                "reason": "missing_lead" if not lead else "missing_participants",
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Export funding claims for Hermes enrich")
    parser.add_argument("--limit", type=int, default=80)
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
    queue = fetch_thin_claims(cur, limit=args.limit)
    conn.close()

    queue_path = args.out_dir / "funding_enrich_queue.jsonl"
    prompt_path = args.out_dir / "PROMPT_FUNDING.md"
    with queue_path.open("w", encoding="utf-8") as f:
        for item in queue:
            f.write(json.dumps(item) + "\n")
    prompt_path.write_text(PROMPT, encoding="utf-8")

    logger.info("Exported %d funding claims → %s", len(queue), queue_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
