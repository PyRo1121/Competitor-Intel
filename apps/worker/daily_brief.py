#!/usr/bin/env python3
"""
Daily Intelligence Brief Generator
Exportable brief with recent competitor events.

Outputs:
  - JSON: Machine-readable format
  - CSV: Spreadsheet-compatible (RFC 4180 compliant)
  - Discord embed: Rich formatting for webhooks
"""

import csv
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("daily_brief")

from db.connection import get_conn, DB_PATH
from ci_paths import EXPORTS_DIR

EXPORT_DIR = EXPORTS_DIR
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def generate_daily_brief(days: int = 7, event_limit: int = 15) -> Dict:
    """Generate a daily intelligence brief.
    
    Args:
        days: Lookback period for events
        event_limit: Max events to include
        
    Returns:
        Dict with brief data
    """
    logger.info("Generating brief for last %s days", days)
    conn = get_conn()
    cursor = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    try:
        # Get high-value recent events
        cursor.execute("""
            SELECT 
                ie.id,
                ie.event_type,
                c.name as company,
                ie.round_type,
                ie.amount_usd,
                ie.valuation_usd,
                ie.lead_investor,
                ie.counterparty,
                ie.is_rumor,
                ie.confidence,
                ie.source,
                ie.created_at
            FROM intelligence_events ie
            LEFT JOIN companies c ON c.id = ie.company_id
            WHERE ie.created_at >= datetime('now', ?)
            ORDER BY 
                ie.confidence DESC,
                CASE WHEN ie.amount_usd IS NULL THEN 0 ELSE ie.amount_usd END DESC
            LIMIT ?
        """, (f"-{days} days", event_limit))
        events = cursor.fetchall()

        # Top companies by score
        cursor.execute("""
            SELECT name, score, industry
            FROM companies 
            WHERE score IS NOT NULL 
            ORDER BY score DESC 
            LIMIT 10
        """)
        top_companies = cursor.fetchall()

        # Signal counts by source for context
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM raw_signals
            WHERE detected_at >= datetime('now', ?)
            GROUP BY source
            ORDER BY count DESC
        """, (f"-{days} days",))
        signal_counts = cursor.fetchall()

    except sqlite3.Error as e:
        logger.error("Database error generating brief: %s", e)
        conn.close()
        return {"error": str(e)}

    conn.close()

    brief = {
        "date": today,
        "title": "Competitor Intelligence Daily Brief",
        "summary": f"{len(events)} events, {len(top_companies)} ranked companies",
        "lookback_days": days,
        "events": [],
        "top_companies": [],
        "signal_counts": {},
        "generated_at": datetime.now().isoformat(),
        "version": "2.0",
    }

    for e in events:
        brief["events"].append({
            "id": e["id"],
            "type": e["event_type"],
            "company": e["company"] or "Unknown",
            "round": e["round_type"],
            "amount_usd": e["amount_usd"],
            "valuation_usd": e["valuation_usd"],
            "investor": e["lead_investor"] or e["counterparty"],
            "is_rumor": bool(e["is_rumor"]),
            "confidence": round(e["confidence"] or 0, 2),
            "source": e["source"],
            "created_at": e["created_at"],
        })

    for c in top_companies:
        brief["top_companies"].append({
            "name": c["name"],
            "score": round(c["score"] or 0, 2),
            "industry": c["industry"],
        })

    for s in signal_counts:
        brief["signal_counts"][s["source"]] = s["count"]

    logger.info("Brief generated: %s events, %s companies", len(brief['events']), len(brief['top_companies']))
    return brief


def export_brief(brief: Dict) -> Dict[str, Path]:
    """Export brief to JSON and CSV.
    
    Returns:
        Dict mapping format to file path
    """
    date_str = brief["date"].replace("-", "")
    paths = {}

    # JSON export
    json_path = EXPORT_DIR / f"daily_brief_{date_str}.json"
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(brief, f, indent=2, ensure_ascii=False, default=str)
        paths["json"] = json_path
        logger.info("JSON exported: %s", json_path)
    except Exception as e:
        logger.error("JSON export failed: %s", e)

    # CSV export (RFC 4180 compliant)
    csv_path = EXPORT_DIR / f"daily_brief_{date_str}.csv"
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([
                "id", "company", "event_type", "round", "amount_usd",
                "valuation_usd", "investor", "is_rumor", "confidence", "source", "created_at"
            ])
            for e in brief["events"]:
                writer.writerow([
                    e["id"],
                    e["company"],
                    e["type"],
                    e["round"] or "",
                    e["amount_usd"] or "",
                    e["valuation_usd"] or "",
                    e["investor"] or "",
                    "true" if e["is_rumor"] else "false",
                    e["confidence"],
                    e["source"] or "",
                    e["created_at"] or "",
                ])
        paths["csv"] = csv_path
        logger.info("CSV exported: %s", csv_path)
    except Exception as e:
        logger.error("CSV export failed: %s", e)

    return paths


def format_for_discord(brief: Dict) -> Dict:
    """Format brief as Discord embed."""
    embed = {
        "title": brief["title"],
        "description": f"**{brief['date']}** — {brief['summary']}",
        "color": 0x5865F2,
        "fields": [],
        "footer": {"text": "Hermes Intelligence"},
    }

    # Events section
    if brief["events"]:
        lines = []
        for e in brief["events"][:8]:
            rumor = " ⚠️ RUMOR" if e["is_rumor"] else ""
            amt = format_amount(e["amount_usd"]) if e["amount_usd"] else "Undisclosed"
            lines.append(f"**{e['company']}** — {e['type']} {amt}{rumor}\n"
                        f"Confidence: {e['confidence']:.0%}")
        embed["fields"].append({
            "name": f"🔥 High-Signal Events ({len(brief['events'])})",
            "value": "\n\n".join(lines),
            "inline": False,
        })

    # Top companies section
    if brief["top_companies"]:
        top = "\n".join([
            f"• **{c['name']}** — {c['score']:.2f}"
            for c in brief["top_companies"][:8]
        ])
        embed["fields"].append({
            "name": "🏆 Top Companies",
            "value": top,
            "inline": False,
        })

    # Signal sources
    if brief.get("signal_counts"):
        sources = "\n".join([
            f"• {source}: {count} signals"
            for source, count in list(brief["signal_counts"].items())[:6]
        ])
        embed["fields"].append({
            "name": "📊 Signal Sources",
            "value": sources,
            "inline": False,
        })

    return embed


def format_amount(amount: Optional[int]) -> str:
    """Format USD amount human-readably."""
    if not amount:
        return "Undisclosed"
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.0f}M"
    if amount >= 1_000:
        return f"${amount / 1_000:.0f}K"
    return f"${amount:,}"


def main():
    """CLI entry point for daily brief generation."""
    import argparse
    parser = argparse.ArgumentParser(description="Generate daily intelligence brief")
    parser.add_argument("--days", type=int, default=7, help="Lookback period")
    parser.add_argument("--export", action="store_true", help="Export to files")
    parser.add_argument("--discord", action="store_true", help="Print Discord embed JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    brief = generate_daily_brief(days=args.days)
    
    if "error" in brief:
        logger.error("Error: %s", brief['error'])
        return 1

    logger.info("=== %s ===", brief['title'])
    logger.info("Date: %s | Events: %s | Companies: %s", brief['date'], len(brief['events']), len(brief['top_companies']))
    
    if brief["events"]:
        logger.info("Top Events:")
        for e in brief["events"][:5]:
            rumor = " [RUMOR]" if e["is_rumor"] else ""
            amt = format_amount(e["amount_usd"])
            logger.info("  • %s: %s (%s)%s — %.0f%% confidence", e['company'], e['type'], amt, rumor, e['confidence']*100)
    
    if brief["top_companies"]:
        logger.info("Top Companies:")
        for c in brief["top_companies"][:5]:
            logger.info("  • %s: %.2f", c['name'], c['score'])

    if args.export:
        paths = export_brief(brief)
        for fmt, path in paths.items():
            logger.info("  Exported %s: %s", fmt, path)

    if args.discord:
        embed = format_for_discord(brief)
        logger.info("Discord Embed:")
        logger.info(json.dumps(embed, indent=2))

    return 0


if __name__ == "__main__":
    exit(main())
