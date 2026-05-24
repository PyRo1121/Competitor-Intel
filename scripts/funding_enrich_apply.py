#!/usr/bin/env python3
"""Apply Hermes funding_enrich_results.jsonl to funding_round_claims + re-aggregate."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from ci_paths import ensure_app_paths

ensure_app_paths()

from collectors.enrichment.funding_aggregator import aggregate_funding_rounds  # noqa: E402
from collectors.enrichment.funding_enricher import apply_structured_funding_enrichment  # noqa: E402

logger = logging.getLogger("funding_enrich_apply")

INSTRUMENTS = frozenset({"equity", "safe", "convertible_note", "debt"})


def _normalize_row(raw: dict) -> dict | None:
    claim_id = raw.get("claim_id")
    if not isinstance(claim_id, int):
        return None
    out: dict = {"claim_id": claim_id}
    if raw.get("source_url"):
        out["source_url"] = str(raw["source_url"]).strip()
    for key in (
        "lead_investor",
        "round_type",
        "announced_date",
        "instrument_type",
    ):
        if raw.get(key):
            out[key] = raw[key]
    for key in (
        "amount_usd",
        "valuation_usd",
        "pre_money_valuation_usd",
        "post_money_valuation_usd",
    ):
        val = raw.get(key)
        if isinstance(val, (int, float)) and val > 0:
            out[key] = int(val)
    co = raw.get("co_investors")
    if isinstance(co, list) and co:
        out["co_investors"] = [str(x).strip() for x in co if x]
    inst = out.get("instrument_type")
    if inst and inst not in INSTRUMENTS:
        del out["instrument_type"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--in-dir",
        type=Path,
        default=ROOT / "data" / "hermes_enrich",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    results_path = args.in_dir / "funding_enrich_results.jsonl"
    if not results_path.is_file():
        logger.error("Missing %s — run Hermes on funding_enrich_queue.jsonl first", results_path)
        return 1

    applied = 0
    skipped = 0
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        row = _normalize_row(raw)
        if not row:
            skipped += 1
            continue
        if args.dry_run:
            applied += 1
            continue
        if apply_structured_funding_enrichment(row):
            applied += 1
        else:
            skipped += 1

    if not args.dry_run and applied:
        agg = aggregate_funding_rounds()
        logger.info("Re-aggregated funding rounds: %s", agg)

    logger.info("Applied %d, skipped %d (dry_run=%s)", applied, skipped, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
