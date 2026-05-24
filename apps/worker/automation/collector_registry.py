"""
Canonical collector lists for daily / continuous / CLI orchestration.

Raw-signal collectors must ingest via db.ingest.insert_raw_signal_dedup().
Extractors read raw_signals and write intelligence_events / funding_events.
"""

from __future__ import annotations

import os
from pathlib import Path

# Monorepo root (apps/worker/automation → … → Competitor-Intel/)
BASE = Path(__file__).resolve().parents[3]

# Ingest → raw_signals (parallel-safe; all migrated to insert_raw_signal_dedup)
PARALLEL_COLLECTORS: tuple[str, ...] = (
    "collectors/rss_collector.py",
    "collectors/techcrunch_edgar_collector.py",
    "collectors/edgar_collector.py",
    "collectors/yc_collector.py",
    "collectors/esma_mica_collector.py",
    "collectors/producthunt_collector.py",
    "collectors/hackernews_collector.py",
    "collectors/crunchbase_collector.py",
    "collectors/angellist_collector.py",
    "collectors/github_signals.py",
    "collectors/youtube_collector.py",
    "collectors/x_signal_collector.py",
)

# Full daily parallel batch without Hermes X (use with grok_refresh.py on another cron)
DAILY_NO_X_PARALLEL_COLLECTORS: tuple[str, ...] = tuple(
    s for s in PARALLEL_COLLECTORS if s != "collectors/x_signal_collector.py"
)

# Legacy direct extractors removed (P0-3): funding/big_deals → signal_processor + funding_rollup.
EXTRACTION_SCRIPTS: tuple[str, ...] = ()

# Hourly / frequent ingest — RSS and open web; no Hermes Grok X quota
FREQUENT_PARALLEL_COLLECTORS: tuple[str, ...] = (
    "collectors/rss_collector.py",
    "collectors/hackernews_collector.py",
    "collectors/yc_collector.py",
    "collectors/producthunt_collector.py",
    "collectors/github_signals.py",
    "collectors/techcrunch_edgar_collector.py",
)

# After frequent parallel: classify + URL fanout + funding rollup (no jobs/embeddings)
FREQUENT_SEQUENTIAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("collectors/website_monitor.py", ()),
    ("collectors/signal_url_fanout.py", ()),
    ("collectors/signal_processor.py", ()),
    ("collectors/candidate_discovery.py", ()),
    ("collectors/auto_promote.py", ()),
    ("collectors/company_ranker.py", ()),
    ("collectors/funding_rollup.py", ()),
)

# Hermes Grok x_search batch only (run on a separate cron, ~5×/day ET)
GROK_COLLECTORS: tuple[str, ...] = ("collectors/x_signal_collector.py",)

# Legacy single-script continuous wrapper (RSS + website; X moved to grok_refresh)
CONTINUOUS_COLLECTORS: tuple[str, ...] = (
    "collectors/rss_collector.py",
    "collectors/website_monitor.py",
)

# Post-parallel sequential pipeline (daily_intel.py).
# Intelligence extraction: signal_processor + funding_rollup (not funding_collector).
_DAILY_SEQUENTIAL_BASE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("collectors/website_monitor.py", ()),
    ("collectors/signal_url_fanout.py", ()),
    ("collectors/job_tracker.py", ()),
    ("collectors/tech_stack_detector.py", ()),
    ("collectors/investor_collector.py", ()),
    ("collectors/signal_processor.py", ()),
    ("collectors/signal_repair.py", ()),
    ("collectors/intel_quality_gate.py", ()),
    ("collectors/candidate_discovery.py", ()),
    ("collectors/auto_promote.py", ()),
    ("collectors/company_ranker.py", ()),
    ("collectors/funding_rollup.py", ()),
    ("collectors/competitor_mapper.py", ()),
    ("collectors/momentum_detector.py", ()),
    ("collectors/enrichment/enrichment_runner.py", ()),
    ("collectors/enrichment/embedding_generator.py", ()),
    ("packages/py-core/alerts/alert_engine.py", ()),
    ("apps/worker/daily_brief.py", ("--export",)),
    ("apps/worker/tweet_generator.py", ()),
)

# Back-compat import name (without CI_COMPANY_DATA_ROLLUP gate).
DAILY_SEQUENTIAL = _DAILY_SEQUENTIAL_BASE


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _env_default_on(name: str) -> bool:
    """Rollups default on; opt out with 0/false/no/off."""
    if _env_truthy(name):
        return True
    return os.environ.get(name, "").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _company_data_rollup_enabled() -> bool:
    return _env_default_on("CI_COMPANY_DATA_ROLLUP") or _env_truthy("CI_PHASE_B_COMPANY")


def _regulatory_license_rollup_enabled() -> bool:
    return _env_default_on("CI_REGULATORY_LICENSE_ROLLUP")


def _cap_table_rollup_enabled() -> bool:
    return _env_default_on("CI_CAP_TABLE_ROLLUP")


def get_daily_sequential() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Daily steps; company/regulatory/cap rollups default on (opt out via CI_*_ROLLUP=0)."""
    steps = list(_DAILY_SEQUENTIAL_BASE)
    if not _company_data_rollup_enabled():
        return tuple(steps)
    out: list[tuple[str, tuple[str, ...]]] = []
    for script, args in steps:
        out.append((script, args))
        if script == "collectors/funding_rollup.py":
            if _regulatory_license_rollup_enabled():
                out.append(("collectors/regulatory_license_rollup.py", ()))
            if _cap_table_rollup_enabled():
                out.append(("collectors/cap_table_rollup.py", ()))
            if _company_data_rollup_enabled():
                out.append(("collectors/company_data_rollup.py", ()))
    return tuple(out)


# intel.py CLI name → script path (on-demand; not all run on daily schedule)
INTEL_CLI_COLLECTORS: dict[str, str] = {
    # Ingest (parallel / frequent)
    "rss": "collectors/rss_collector.py",
    "github": "collectors/github_signals.py",
    "website": "collectors/website_monitor.py",
    "edgar": "collectors/edgar_collector.py",
    "yc": "collectors/yc_collector.py",
    "esma_mica": "collectors/esma_mica_collector.py",
    "techcrunch": "collectors/techcrunch_edgar_collector.py",
    "multi": "collectors/multi_source_collector.py",
    "enhanced_signals": "collectors/enhanced_signal_collector.py",
    "youtube": "collectors/youtube_collector.py",
    "producthunt": "collectors/producthunt_collector.py",
    "hackernews": "collectors/hackernews_collector.py",
    "crunchbase": "collectors/crunchbase_collector.py",
    "angellist": "collectors/angellist_collector.py",
    "x": "collectors/x_signal_collector.py",
    "continuous": "collectors/continuous_ingest.py",
    # Legacy extractors (P0-3: daily uses signal_processor + funding_rollup)
    "funding": "collectors/funding_collector.py",
    "deals": "collectors/big_deals_collector.py",
    "funding_enhanced": "collectors/enhanced_funding_detector.py",
    "funding_rumor": "collectors/funding_rumor_detector.py",
    # Pipeline / quality
    "fanout": "collectors/signal_url_fanout.py",
    "process": "collectors/signal_processor.py",
    "repair": "collectors/signal_repair.py",
    "gate": "collectors/intel_quality_gate.py",
    "rollup": "collectors/funding_rollup.py",
    "company_data": "collectors/company_data_rollup.py",
    "regulatory_licenses": "collectors/regulatory_license_rollup.py",
    "cap_table": "collectors/cap_table_rollup.py",
    "job_rollup": "collectors/job_rollup.py",
    # Discovery / rank
    "discover": "collectors/candidate_discovery.py",
    "company_discovery": "collectors/company_discovery.py",
    "promote": "collectors/auto_promote.py",
    "rank": "collectors/company_ranker.py",
    "competitor": "collectors/competitor_mapper.py",
    "momentum": "collectors/momentum_detector.py",
    "reactive": "collectors/reactive_enrichment.py",
    # Jobs / stack / investors
    "jobs": "collectors/job_tracker.py",
    "techstack": "collectors/tech_stack_detector.py",
    "investors": "collectors/investor_collector.py",
    "github_org": "collectors/github_collector.py",
    # Enrichment (also in daily sequential when enabled)
    "enrich": "collectors/enrichment/enrichment_runner.py",
    "embed": "collectors/enrichment/embedding_generator.py",
    "rerank": "collectors/enrichment/reranker.py",
    "github_deep": "collectors/enrichment/github_deep.py",
    "company_enrich": "collectors/enrichment/company_enricher.py",
    "funding_enrich": "collectors/enrichment/funding_enricher.py",
}


def _scripts_from_steps(
    steps: tuple[tuple[str, tuple[str, ...]], ...],
) -> set[str]:
    return {script for script, _args in steps}


def registered_collector_script_paths(*, include_gated_daily: bool = True) -> frozenset[str]:
    """Every collector script path referenced by worker schedules or intel CLI."""
    paths: set[str] = set()
    paths.update(PARALLEL_COLLECTORS)
    paths.update(DAILY_NO_X_PARALLEL_COLLECTORS)
    paths.update(FREQUENT_PARALLEL_COLLECTORS)
    paths.update(GROK_COLLECTORS)
    paths.update(CONTINUOUS_COLLECTORS)
    paths.update(EXTRACTION_SCRIPTS)
    paths.update(_scripts_from_steps(FREQUENT_SEQUENTIAL))
    paths.update(
        _scripts_from_steps(
            get_daily_sequential() if include_gated_daily else _DAILY_SEQUENTIAL_BASE
        )
    )
    paths.update(INTEL_CLI_COLLECTORS.values())
    return frozenset(paths)
