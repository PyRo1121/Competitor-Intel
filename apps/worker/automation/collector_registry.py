"""
Canonical collector lists for daily / continuous / CLI orchestration.

Raw-signal collectors must ingest via db.ingest.insert_raw_signal_dedup().
Extractors read raw_signals and write intelligence_events / funding_events.
"""

from __future__ import annotations

from pathlib import Path

# Monorepo root (apps/worker/automation → … → Competitor-Intel/)
BASE = Path(__file__).resolve().parents[3]

# Ingest → raw_signals (parallel-safe; all migrated to insert_raw_signal_dedup)
PARALLEL_COLLECTORS: tuple[str, ...] = (
    "collectors/multi_source_collector.py",
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

# raw_signals → intelligence_events / funding_events (sequential, after parallel ingest)
EXTRACTION_SCRIPTS: tuple[str, ...] = (
    "collectors/funding_collector.py",
    "collectors/big_deals_collector.py",
)

# Hourly / frequent ingest — RSS and open web; no Hermes Grok X quota
FREQUENT_PARALLEL_COLLECTORS: tuple[str, ...] = (
    "collectors/rss_collector.py",
    "collectors/multi_source_collector.py",
    "collectors/hackernews_collector.py",
    "collectors/yc_collector.py",
    "collectors/producthunt_collector.py",
    "collectors/github_signals.py",
    "collectors/techcrunch_edgar_collector.py",
)

# After frequent parallel: classify + URL fanout + Phase B funding rollup (no jobs/embeddings)
FREQUENT_SEQUENTIAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("collectors/website_monitor.py", ()),
    ("collectors/signal_url_fanout.py", ()),
    ("collectors/signal_processor.py", ()),
    ("collectors/candidate_discovery.py", ()),
    ("collectors/auto_promote.py", ()),
    ("collectors/company_ranker.py", ()),
    ("scripts/phase_b_populate_funding.py", ()),
)

# Hermes Grok x_search batch only (run on a separate cron, ~5×/day ET)
GROK_COLLECTORS: tuple[str, ...] = ("collectors/x_signal_collector.py",)

# Legacy single-script continuous wrapper (RSS + website; X moved to grok_refresh)
CONTINUOUS_COLLECTORS: tuple[str, ...] = (
    "collectors/rss_collector.py",
    "collectors/website_monitor.py",
)

# Post-parallel sequential pipeline (daily_intel.py).
# funding_collector + big_deals run inside run_intel.py after parallel ingest.
DAILY_SEQUENTIAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("collectors/website_monitor.py", ()),
    ("collectors/signal_url_fanout.py", ()),
    ("collectors/job_tracker.py", ()),
    ("collectors/tech_stack_detector.py", ()),
    ("collectors/investor_collector.py", ()),
    ("collectors/signal_processor.py", ()),
    ("collectors/candidate_discovery.py", ()),
    ("collectors/auto_promote.py", ()),
    ("collectors/company_ranker.py", ()),
    ("scripts/phase_b_populate_funding.py", ()),
    # phase_b_populate_company: opt-in via `make phase-b-company` (slow web enrichment)
    ("collectors/competitor_mapper.py", ()),
    ("collectors/momentum_detector.py", ()),
    ("collectors/enrichment/enrichment_runner.py", ()),
    ("collectors/enrichment/embedding_generator.py", ()),
    ("packages/py-core/alerts/alert_engine.py", ()),
    ("apps/worker/daily_brief.py", ("--export",)),
    ("apps/worker/tweet_generator.py", ()),
)

# intel.py CLI name → script path (superset for on-demand runs)
INTEL_CLI_COLLECTORS: dict[str, str] = {
    "rss": "collectors/rss_collector.py",
    "github": "collectors/github_signals.py",
    "website": "collectors/website_monitor.py",
    "funding": "collectors/funding_collector.py",
    "deals": "collectors/big_deals_collector.py",
    "edgar": "collectors/edgar_collector.py",
    "yc": "collectors/yc_collector.py",
    "esma_mica": "collectors/esma_mica_collector.py",
    "techcrunch": "collectors/techcrunch_edgar_collector.py",
    "multi": "collectors/multi_source_collector.py",
    "youtube": "collectors/youtube_collector.py",
    "investors": "collectors/investor_collector.py",
    "github_org": "collectors/github_collector.py",
    "producthunt": "collectors/producthunt_collector.py",
    "hackernews": "collectors/hackernews_collector.py",
    "jobs": "collectors/job_tracker.py",
    "techstack": "collectors/tech_stack_detector.py",
    "crunchbase": "collectors/crunchbase_collector.py",
    "angellist": "collectors/angellist_collector.py",
    "x": "collectors/x_signal_collector.py",
    "fanout": "collectors/signal_url_fanout.py",
    "discover": "collectors/candidate_discovery.py",
    "promote": "collectors/auto_promote.py",
    "rank": "collectors/company_ranker.py",
}
