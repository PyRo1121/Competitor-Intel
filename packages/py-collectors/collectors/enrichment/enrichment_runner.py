#!/usr/bin/env python3
"""
Enrichment Orchestrator
Runs all deep enrichment modules in sequence to build comprehensive
company intelligence. Coordinates company, funding, GitHub, and X enrichment.
"""

import logging
from pathlib import Path

logger = logging.getLogger("enrichment_runner")

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.connection import get_conn

# Import enrichment modules
sys.path.insert(0, str(Path(__file__).parent))
from company_enricher import run_company_enrichment
from funding_enricher import extract_from_signals
from github_deep import run_github_deep_analysis


def enrich_all(limit: int = 50) -> dict:
    """Run complete enrichment pipeline for all tracked companies."""
    logger.info("=" * 60)
    logger.info("COMPETITOR INTELLIGENCE DEEP ENRICHMENT")
    logger.info("=" * 60)

    results = {}

    # Step 1: Company profiles
    logger.info("\n[1/4] Enriching company profiles...")
    company_results = run_company_enrichment(limit=limit)
    results["companies"] = company_results

    # Step 2: GitHub deep analysis
    logger.info("\n[2/4] Analyzing GitHub metrics...")
    github_results = run_github_deep_analysis(limit=limit)
    results["github"] = github_results

    # Step 3: Structured funding extraction
    logger.info("\n[3/6] Extracting structured funding data...")
    funding_results = extract_from_signals()
    results["funding"] = funding_results

    logger.info("\n[4/6] Detecting technology stacks...")
    try:
        from collectors.tech_stack_detector import run as run_techstack

        tech_results = run_techstack()
        results["tech_stack"] = {"detections": tech_results}
    except Exception as e:
        logger.error("Tech stack detection failed: %s", e)
        results["tech_stack"] = {"error": str(e)}

    logger.info("\n[5/6] Monitoring website changes...")
    try:
        from collectors.website_monitor import run as run_website

        website_results = run_website()
        results["website_changes"] = {"changes": website_results}
    except Exception as e:
        logger.error("Website monitoring failed: %s", e)
        results["website_changes"] = {"error": str(e)}

    logger.info("\n[6/6] Generating summary...")
    stats = generate_stats()
    results["stats"] = stats

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("ENRICHMENT COMPLETE")
    logger.info("=" * 60)
    logger.info("Companies enriched: %d", company_results.get("enriched", 0))
    logger.info("GitHub repos analyzed: %d", github_results.get("analyzed", 0))
    logger.info("Funding rounds extracted: %d", funding_results.get("created", 0))
    logger.info("Total companies tracked: %d", stats.get("companies", 0))
    logger.info("Total funding rounds: %d", stats.get("funding_rounds", 0))
    logger.info("Total intelligence events: %d", stats.get("intelligence_events", 0))
    logger.info("Companies with profiles: %d", stats.get("company_details", 0))
    logger.info("Companies with GitHub metrics: %d", stats.get("github_metrics", 0))

    return results


def generate_stats() -> dict:
    """Generate database statistics after enrichment."""
    conn = get_conn()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM companies")
    stats["companies"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM intelligence_events")
    stats["intelligence_events"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM funding_rounds")
    stats["funding_rounds"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM company_details")
    stats["company_details"] = (
        conn.cursor().execute("SELECT COUNT(*) FROM company_details").fetchone()[0]
    )

    cursor.execute("SELECT COUNT(*) FROM github_metrics")
    stats["github_metrics"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM team_members")
    stats["team_members"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products")
    stats["products"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM technology_stack")
    stats["technology_stack"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM website_snapshots")
    stats["website_snapshots"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM job_postings")
    stats["job_postings"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM competitor_relationships")
    stats["competitor_relationships"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM customer_signals")
    stats["customer_signals"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ip_assets")
    stats["ip_assets"] = cursor.fetchone()[0]

    conn.close()
    return stats


def print_company_profiles(limit: int = 10):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            c.name, c.industry, c.github_stars, c.score,
            cd.founded_year, cd.headquarters, cd.team_size, cd.business_model,
            cd.tech_stack, cd.description_long
        FROM companies c
        LEFT JOIN company_details cd ON cd.company_id = c.id
        WHERE cd.company_id IS NOT NULL
        ORDER BY c.score DESC NULLS LAST
        LIMIT ?
    """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.info("No enriched company profiles found yet. Run enrichment first.")
        return

    logger.info("\nEnriched Company Profiles (top %d):", limit)
    logger.info("-" * 80)

    for row in rows:
        name = row["name"]
        desc = (row["description_long"] or "No description")[:80]
        founded = row["founded_year"] or "N/A"
        hq = row["headquarters"] or "N/A"
        team = row["team_size"] or "N/A"
        model = row["business_model"] or "N/A"
        tech = row["tech_stack"] or "N/A"

        logger.info("\n%s:", name)
        logger.info("  Founded: %s | HQ: %s | Team: %s | Model: %s", founded, hq, team, model)
        logger.info("  Tech: %s", tech[:60])
        logger.info("  Desc: %s", desc)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    import argparse

    parser = argparse.ArgumentParser(description="Deep enrichment pipeline")
    parser.add_argument("--limit", type=int, default=50, help="Max companies to enrich")
    parser.add_argument("--profiles", action="store_true", help="Print enriched profiles after")
    args = parser.parse_args()

    results = enrich_all(limit=args.limit)

    if args.profiles:
        print_company_profiles(limit=10)
