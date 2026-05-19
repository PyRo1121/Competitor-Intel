#!/usr/bin/env python3
"""
Hermes Intel — Manual Trigger CLI
On-demand execution of collectors, reports, and database queries.

Usage:
    python intel.py daily              Generate daily brief
    python intel.py collect            Run all collectors
    python intel.py collect --rss      Run only RSS collector
    python intel.py report             Generate all reports
    python intel.py report --discord   Generate Discord report only
    python intel.py status             Show database status
    python intel.py search <query>     Search intelligence database
    python intel.py companies          List tracked companies
    python intel.py signals            Show recent signals
    python intel.py export             Export to JSON/CSV
    python intel.py pipeline           Run full pipeline (collect + report)
    python intel.py youtube            Run YouTube collector
    python intel.py promote            Run auto-promotion
"""

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("intel_cli")

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import get_conn


from automation.collector_registry import INTEL_CLI_COLLECTORS

COLLECTORS = INTEL_CLI_COLLECTORS

REPORTS = {
    "daily": "daily_brief.py",
    "discord": "discord_report.py",
    "discord_rich": "discord_reporter.py",
    "obsidian": "generate_obsidian_notes.py",
    "obsidian_profile": "obsidian_profile_generator.py",
    "intel": "generate_intel_report.py",
    "tweet": "tweet_generator.py",
}


def run_script(script_path: str, args: list = None) -> tuple[bool, str]:
    """Run a Python script and return (success, output)."""
    full_path = PROJECT_ROOT / script_path
    if not full_path.exists():
        return False, f"Script not found: {full_path}"
    
    cmd = [sys.executable, str(full_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            return True, result.stdout[-800:] if result.stdout else "Success"
        else:
            return False, result.stderr[-800:] if result.stderr else "Error (no output)"
    except subprocess.TimeoutExpired:
        return False, "Timeout after 180s"
    except Exception as e:
        return False, str(e)


def cmd_daily(args):
    """Generate daily brief."""
    logger.info("Generating daily brief...")
    success, output = run_script("daily_brief.py", ["--export"] if args.export else [])
    if success:
        logger.info("Daily brief generated successfully")
        logger.info("Output:\n%s", output)
    else:
        logger.error("Failed to generate daily brief:\n%s", output)
    return 0 if success else 1


def cmd_collect(args):
    """Run signal collectors."""
    if args.collector:
        # Run specific collector
        if args.collector not in COLLECTORS:
            logger.error("Unknown collector: %s", args.collector)
            logger.info("Available: %s", ", ".join(COLLECTORS.keys()))
            return 1
        
        logger.info("Running collector: %s", args.collector)
        success, output = run_script(COLLECTORS[args.collector])
        logger.info("Output:\n%s", output)
        return 0 if success else 1
    else:
        # Run all collectors
        logger.info("Running all collectors...")
        results = {}
        for name, path in COLLECTORS.items():
            logger.info("  → %s...", name)
            success, output = run_script(path)
            results[name] = "OK" if success else "FAIL"
            if not success:
                logger.error("    Failed: %s", output[:200])
        
        # Print summary
        logger.info("\nCollection Summary:")
        for name, status in results.items():
            icon = "✓" if status == "OK" else "✗"
            logger.info("  %s %s", icon, name)
        
        failed = sum(1 for s in results.values() if s == "FAIL")
        return 0 if failed == 0 else 1


def cmd_report(args):
    """Generate reports."""
    if args.report_type:
        if args.report_type not in REPORTS:
            logger.error("Unknown report: %s", args.report_type)
            logger.info("Available: %s", ", ".join(REPORTS.keys()))
            return 1
        
        logger.info("Generating report: %s", args.report_type)
        success, output = run_script(REPORTS[args.report_type])
        logger.info("Output:\n%s", output)
        return 0 if success else 1
    else:
        # Generate all reports
        logger.info("Generating all reports...")
        for name, path in REPORTS.items():
            logger.info("  → %s...", name)
            success, output = run_script(path)
            if not success:
                logger.error("    Failed: %s", output[:200])
        logger.info("Reports generated")
        return 0


def cmd_status(args):
    """Show database status."""
    conn = get_conn()
    cursor = conn.cursor()
    
    stats = {}
    cursor.execute("SELECT COUNT(*) FROM companies")
    stats["companies"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM intelligence_events")
    stats["events"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM raw_signals")
    stats["signals"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM funding_events")
    stats["funding"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM x_posts")
    stats["x_posts"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM raw_signals WHERE detected_at >= datetime('now', '-24 hours')")
    stats["signals_24h"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM intelligence_events WHERE created_at >= datetime('now', '-24 hours')")
    stats["events_24h"] = cursor.fetchone()[0]
    
    conn.close()
    
    logger.info("╔════════════════════════════════════╗")
    logger.info("║  Competitor Intelligence Status    ║")
    logger.info("╠════════════════════════════════════╣")
    logger.info("║ Companies:     %-20s ║", stats["companies"])
    logger.info("║ Events:        %-20s ║", stats["events"])
    logger.info("║ Funding:       %-20s ║", stats["funding"])
    logger.info("║ Raw Signals:    %-20s ║", stats["signals"])
    logger.info("║ X Posts:        %-20s ║", stats["x_posts"])
    logger.info("╠════════════════════════════════════╣")
    logger.info("║ Last 24h:                           ║")
    logger.info("║   Signals:     %-20s ║", stats["signals_24h"])
    logger.info("║   Events:      %-20s ║", stats["events_24h"])
    logger.info("╚════════════════════════════════════╝")
    
    return 0


def cmd_search(args):
    """Search the intelligence database."""
    query = args.query
    if not query:
        logger.error("No search query provided")
        return 1
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Search companies
    cursor.execute("""
        SELECT name, description, industry, github_stars, score
        FROM companies
        WHERE name LIKE ? OR description LIKE ?
        LIMIT 10
    """, (f"%{query}%", f"%{query}%"))
    companies = cursor.fetchall()
    
    # Search events
    cursor.execute("""
        SELECT c.name, ie.event_type, ie.amount_usd, ie.source, ie.created_at
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        WHERE ie.event_type LIKE ? OR c.name LIKE ?
        ORDER BY ie.created_at DESC
        LIMIT 10
    """, (f"%{query}%", f"%{query}%"))
    events = cursor.fetchall()
    
    conn.close()
    
    logger.info("Search results for '%s':", query)
    
    if companies:
        logger.info("\nCompanies:")
        for name, desc, industry, stars, score in companies:
            score_str = f" (score: {score:.1f})" if score else ""
            logger.info("  • %s%s — %s", name, score_str, desc[:60] if desc else "No description")
    
    if events:
        logger.info("\nEvents:")
        for company, event_type, amount, source, created in events:
            company = company or "Unknown"
            amt_str = f"${amount / 1_000_000:.1f}M" if amount else "Undisclosed"
            logger.info("  • %s: %s (%s)", company, event_type, amt_str)
    
    if not companies and not events:
        logger.info("No results found.")
    
    return 0


def cmd_companies(args):
    """List tracked companies."""
    conn = get_conn()
    cursor = conn.cursor()
    
    limit = args.limit if hasattr(args, 'limit') else 20
    cursor.execute("""
        SELECT name, industry, github_stars, score, status
        FROM companies
        ORDER BY score DESC NULLS LAST, github_stars DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    logger.info("Tracked Companies (top %d):", limit)
    for name, industry, stars, score, status in rows:
        score_str = f"{score:.1f}" if score else "N/A"
        stars_str = f"⭐{stars:,}" if stars else ""
        logger.info("  %-20s | Score: %-6s | %s | %s", name, score_str, industry or "Unknown", stars_str)
    
    return 0


def cmd_signals(args):
    """Show recent signals."""
    conn = get_conn()
    cursor = conn.cursor()
    
    limit = args.limit if hasattr(args, 'limit') else 10
    cursor.execute("""
        SELECT c.name, ie.event_type, ie.amount_usd, ie.source, ie.created_at
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        ORDER BY ie.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    logger.info("Recent Signals (last %d):", limit)
    for company, event_type, amount, source, created in rows:
        company = company or "Unknown"
        amt_str = f"${amount / 1_000_000:.1f}M" if amount else "Undisclosed"
        date_str = created[:10] if created else ""
        logger.info("  %s | %s | %s | %s", date_str, company, event_type, amt_str)
    
    return 0


def cmd_export(args):
    """Export data to JSON/CSV."""
    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Export intelligence events
    cursor.execute("""
        SELECT c.name, ie.event_type, ie.amount_usd, ie.valuation_usd, 
               ie.lead_investor, ie.source, ie.created_at
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        ORDER BY ie.created_at DESC
    """)
    events = [dict(row) for row in cursor.fetchall()]
    
    export_dir = PROJECT_ROOT / "exports"
    export_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON export
    json_path = export_dir / f"intelligence_export_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump(events, f, indent=2, default=str)
    logger.info("JSON export: %s (%d events)", json_path, len(events))
    
    # CSV export
    csv_path = export_dir / f"intelligence_export_{timestamp}.csv"
    import csv
    with open(csv_path, "w", newline="") as f:
        if events:
            writer = csv.DictWriter(f, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
    logger.info("CSV export: %s", csv_path)
    
    conn.close()
    return 0


def cmd_pipeline(args):
    """Run full pipeline: collect + report."""
    logger.info("=== Running Full Pipeline ===")
    
    # Step 1: Collect
    collect_args = argparse.Namespace(collector=None)
    collect_result = cmd_collect(collect_args)
    
    # Step 2: Report
    report_args = argparse.Namespace(report_type=None)
    report_result = cmd_report(report_args)
    
    if collect_result == 0 and report_result == 0:
        logger.info("Pipeline completed successfully")
    else:
        logger.warning("Pipeline completed with issues")
    
    return 0


def cmd_youtube(args):
    """Run YouTube collector."""
    logger.info("Running YouTube collector...")
    success, output = run_script("collectors/youtube_collector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_process(args):
    """Process unprocessed raw signals into intelligence events."""
    logger.info("Processing unprocessed signals...")
    success, output = run_script("collectors/signal_processor_v2.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_enrich(args):
    """Run deep enrichment pipeline."""
    logger.info("Running deep enrichment pipeline...")
    script_path = "collectors/enrichment/enrichment_runner.py"
    script_args = []
    if hasattr(args, 'limit') and args.limit:
        script_args.extend(["--limit", str(args.limit)])
    if hasattr(args, 'profiles') and args.profiles:
        script_args.append("--profiles")
    
    success, output = run_script(script_path, script_args)
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_embed(args):
    """Generate embeddings for all enriched content."""
    logger.info("Generating embeddings...")
    success, output = run_script("collectors/enrichment/embedding_generator.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_rerank(args):
    """Run semantic search with reranking."""
    query = args.query if hasattr(args, 'query') else ""
    logger.info("Reranked search: %s", query)
    success, output = run_script("collectors/enrichment/reranker.py", [query])
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_enhanced_funding(args):
    """Run enhanced funding/deal detection."""
    logger.info("Running enhanced funding detection...")
    success, output = run_script("collectors/enhanced_funding_detector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_sources(args):
    """Show all configured RSS sources."""
    from sources import print_source_summary
    print_source_summary()
    return 0


def cmd_promote(args):
    logger.info("Running auto-promotion...")
    success, output = run_script("collectors/auto_promote.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_producthunt(args):
    logger.info("Running Product Hunt collector...")
    success, output = run_script("collectors/producthunt_collector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_hackernews(args):
    logger.info("Running Hacker News collector...")
    success, output = run_script("collectors/hackernews_collector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_jobs(args):
    logger.info("Running job tracker...")
    success, output = run_script("collectors/job_tracker.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_techstack(args):
    logger.info("Running tech stack detector...")
    success, output = run_script("collectors/tech_stack_detector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_crunchbase(args):
    logger.info("Running Crunchbase collector...")
    success, output = run_script("collectors/crunchbase_collector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def cmd_angellist(args):
    logger.info("Running AngelList collector...")
    success, output = run_script("collectors/angellist_collector.py")
    logger.info("Output:\n%s", output)
    return 0 if success else 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Hermes Competitor Intelligence CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python intel.py daily                    Generate daily brief
  python intel.py collect                  Run all collectors
  python intel.py collect --rss            Run only RSS collector
  python intel.py report --discord         Generate Discord report
  python intel.py status                   Show database status
  python intel.py search "OpenAI"          Search for OpenAI
  python intel.py companies --limit 10     List top 10 companies
  python intel.py pipeline               Full pipeline (collect + report)
  python intel.py youtube                Run YouTube collector
  python intel.py enrich                 Run deep enrichment
  python intel.py embed                  Generate embeddings
  python intel.py rerank "AI funding"     Semantic search with reranking
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # daily
    daily_parser = subparsers.add_parser("daily", help="Generate daily brief")
    daily_parser.add_argument("--export", action="store_true", help="Export to file")
    
    # collect
    collect_parser = subparsers.add_parser("collect", help="Run collectors")
    collect_parser.add_argument("--collector", choices=list(COLLECTORS.keys()),
                                help="Run specific collector")
    
    # report
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_parser.add_argument("--type", dest="report_type", choices=list(REPORTS.keys()),
                                 help="Generate specific report")
    
    # status
    subparsers.add_parser("status", help="Show database status")
    
    # search
    search_parser = subparsers.add_parser("search", help="Search database")
    search_parser.add_argument("query", help="Search query")
    
    # companies
    companies_parser = subparsers.add_parser("companies", help="List companies")
    companies_parser.add_argument("--limit", type=int, default=20, help="Number to show")
    
    # signals
    signals_parser = subparsers.add_parser("signals", help="Show recent signals")
    signals_parser.add_argument("--limit", type=int, default=10, help="Number to show")
    
    # export
    subparsers.add_parser("export", help="Export data to JSON/CSV")
    
    # pipeline
    subparsers.add_parser("pipeline", help="Run full pipeline")
    
    # youtube
    subparsers.add_parser("youtube", help="Run YouTube collector")
    
    # process
    subparsers.add_parser("process", help="Process raw signals into intelligence events")
    
    # enrich
    enrich_parser = subparsers.add_parser("enrich", help="Run deep enrichment pipeline")
    enrich_parser.add_argument("--limit", type=int, default=50, help="Max companies")
    enrich_parser.add_argument("--profiles", action="store_true", help="Show profiles")
    
    # embed
    subparsers.add_parser("embed", help="Generate embeddings for enriched content")
    
    # rerank
    rerank_parser = subparsers.add_parser("rerank", help="Semantic search with reranking")
    rerank_parser.add_argument("query", help="Search query")
    
    # enhanced-funding
    subparsers.add_parser("enhanced-funding", help="Run enhanced funding/deal detection")
    
    # sources
    subparsers.add_parser("sources", help="Show all configured RSS sources")
    
    subparsers.add_parser("promote", help="Run auto-promotion")
    subparsers.add_parser("producthunt", help="Run Product Hunt collector")
    subparsers.add_parser("hackernews", help="Run Hacker News collector")
    subparsers.add_parser("jobs", help="Run job posting tracker")
    subparsers.add_parser("techstack", help="Run tech stack detector")
    subparsers.add_parser("crunchbase", help="Run Crunchbase collector")
    subparsers.add_parser("angellist", help="Run AngelList collector")

    args = parser.parse_args()

    commands = {
        "daily": cmd_daily,
        "collect": cmd_collect,
        "report": cmd_report,
        "status": cmd_status,
        "search": cmd_search,
        "companies": cmd_companies,
        "signals": cmd_signals,
        "export": cmd_export,
        "pipeline": cmd_pipeline,
        "youtube": cmd_youtube,
        "process": cmd_process,
        "enrich": cmd_enrich,
        "embed": cmd_embed,
        "rerank": cmd_rerank,
        "enhanced-funding": cmd_enhanced_funding,
        "sources": cmd_sources,
        "promote": cmd_promote,
        "producthunt": cmd_producthunt,
        "hackernews": cmd_hackernews,
        "jobs": cmd_jobs,
        "techstack": cmd_techstack,
        "crunchbase": cmd_crunchbase,
        "angellist": cmd_angellist,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    sys.exit(main())
