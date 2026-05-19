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
    "collectors/producthunt_collector.py",
    "collectors/hackernews_collector.py",
    "collectors/crunchbase_collector.py",
    "collectors/angellist_collector.py",
    "collectors/github_signals.py",
    "collectors/youtube_collector.py",
    "collectors/x_signal_collector.py",
)

# raw_signals → intelligence_events / funding_events (sequential, after parallel ingest)
EXTRACTION_SCRIPTS: tuple[str, ...] = (
    "collectors/funding_collector.py",
    "collectors/big_deals_collector.py",
)

# High-frequency cycle (RSS + X batch + website snapshots)
CONTINUOUS_COLLECTORS: tuple[str, ...] = (
    "collectors/rss_collector.py",
    "collectors/x_signal_collector.py",
    "collectors/website_monitor.py",
)

# Post-parallel sequential pipeline (daily_intel.py).
# funding_collector + big_deals run inside run_intel.py after parallel ingest.
DAILY_SEQUENTIAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("collectors/website_monitor.py", ()),
    ("collectors/job_tracker.py", ()),
    ("collectors/tech_stack_detector.py", ()),
    ("collectors/investor_collector.py", ()),
    ("collectors/signal_processor_v2.py", ()),
    ("collectors/competitor_mapper.py", ()),
    ("collectors/momentum_detector.py", ()),
    ("collectors/enrichment/enrichment_runner.py", ()),
    ("collectors/enrichment/embedding_generator.py", ()),
    ("alerts/alert_engine.py", ()),
    ("daily_brief.py", ("--export",)),
    ("tweet_generator.py", ()),
)

# intel.py CLI name → script path (superset for on-demand runs)
INTEL_CLI_COLLECTORS: dict[str, str] = {
    "rss": "collectors/rss_collector.py",
    "github": "collectors/github_signals.py",
    "website": "collectors/website_monitor.py",
    "funding": "collectors/funding_collector.py",
    "deals": "collectors/big_deals_collector.py",
    "edgar": "collectors/edgar_collector.py",
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
}
