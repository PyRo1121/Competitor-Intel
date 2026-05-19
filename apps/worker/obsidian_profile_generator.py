#!/usr/bin/env python3
"""
Obsidian Profile Generator
Creates structured Markdown notes for tracked companies.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("obsidian_profiles")

BASE_DIR = Path(__file__).parent
OBSIDIAN_DIR = BASE_DIR / "obsidian" / "Companies"
from db.connection import get_conn, DB_PATH


def get_company_data(company_name: str) -> Optional[Dict]:
    """Fetch comprehensive data for a single company including funding and signals."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id, name, description, industry, github_stars, github_repos,
            last_github_update, website, score
        FROM companies
        WHERE name = ?
        """,
        (company_name,),
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    company_id = row["id"]
    name = row["name"]
    description = row["description"] or "No description available"
    industry = row["industry"] or "Unknown"

    cursor.execute(
        """
        SELECT
            round_type, amount_usd, valuation_usd, announced_date, source
        FROM funding_events
        WHERE company_id = ?
        ORDER BY announced_date DESC
        """,
        (company_id,),
    )
    funding = cursor.fetchall()

    cursor.execute(
        """
        SELECT source, signal_type, data_json, detected_at
        FROM raw_signals
        WHERE company_id = ?
        ORDER BY detected_at DESC
        LIMIT 25
        """,
        (company_id,),
    )
    signals = cursor.fetchall()
    conn.close()

    return {
        "id": company_id,
        "name": name,
        "description": description,
        "industry": industry,
        "github_stars": row["github_stars"] or 0,
        "github_repos": row["github_repos"] or 0,
        "last_github_update": row["last_github_update"],
        "website": row["website"],
        "score": row["score"],
        "funding": funding,
        "signals": signals,
    }


def generate_overview(data: Dict) -> str:
    """Generate the overview section for an Obsidian company note."""
    lines = [f"# {data['name']}\n"]
    lines.append(f"> {data['description']}\n")
    lines.append("## Company Overview\n")
    lines.append(f"- **Industry**: {data['industry']}")
    lines.append(f"- **Website**: {data['website'] or 'N/A'}")
    lines.append(f"- **GitHub Stars**: {data['github_stars']:,}")
    lines.append(f"- **Public Repos**: {data['github_repos']}")
    if data["last_github_update"]:
        lines.append(f"- **Last GitHub Activity**: {data['last_github_update']}")
    if data["score"] is not None:
        lines.append(f"- **Institutional Score**: {data['score']*100:.1f}%")
    lines.append("")
    return "\n".join(lines)


def generate_funding(data: Dict) -> str:
    """Generate the funding history section."""
    lines = ["## Funding History\n"]
    if not data["funding"]:
        lines.append("_No funding events recorded._\n")
    else:
        for f in data["funding"]:
            round_type, amount, valuation, date, source = f
            val_str = f"${valuation / 1_000_000:.1f}M" if valuation else "N/A"
            lines.append(f"- **{date}** — {round_type} ({val_str})")
            if source:
                lines.append(f"  - Source: {source}")
        lines.append("")
    return "\n".join(lines)


def generate_signals(data: Dict) -> str:
    """Generate the recent signals section."""
    lines = ["## Recent Signals & Activity\n"]
    if not data["signals"]:
        lines.append("_No recent signals captured._\n")
    else:
        for sig in data["signals"][:15]:
            source, signal_type, data_json, detected = sig
            try:
                parsed = json.loads(data_json)
                title = parsed.get("title", signal_type or "Update")
                lines.append(f"- **{detected[:10]}** — {source}: {title}")
            except json.JSONDecodeError:
                lines.append(f"- **{detected[:10]}** — {source}")
        lines.append("")
    return "\n".join(lines)


def generate_technical(data: Dict) -> str:
    """Generate the technical profile section."""
    lines = ["## Technical Profile\n"]
    lines.append(f"- **GitHub Stars**: {data['github_stars']:,}")
    lines.append(f"- **Public Repositories**: {data['github_repos']}")
    lines.append(f"- **Last Activity**: {data['last_github_update'] or 'Unknown'}")
    lines.append("\n### Key Repositories")
    lines.append("_(GitHub repo analysis will be added in future iteration)_")
    lines.append("")
    return "\n".join(lines)


def generate_competitive(data: Dict) -> str:
    """Generate the competitive positioning section."""
    lines = ["## Competitive Positioning\n"]
    lines.append("**Strengths**")
    lines.append("- Strong technical output (GitHub activity)")
    lines.append("- Active in high-growth AI/agent category\n")
    lines.append("**Risks / Gaps**")
    lines.append("- Limited public funding signals (early stage)")
    lines.append("- High competition in agent tooling space")
    lines.append("")
    return "\n".join(lines)


def generate_profile(company_name: str) -> Optional[Path]:
    """Generate a full multi-section Obsidian note for one company."""
    data = get_company_data(company_name)
    if not data:
        logger.warning("Not found: %s", company_name)
        return None

    company_dir = OBSIDIAN_DIR / company_name.replace(" ", "_")
    company_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "00_Overview.md": generate_overview(data),
        "01_Funding_History.md": generate_funding(data),
        "02_Recent_Signals.md": generate_signals(data),
        "03_Technical_Profile.md": generate_technical(data),
        "04_Competitive_Positioning.md": generate_competitive(data),
    }

    for filename, content in files.items():
        with open(company_dir / filename, "w") as f:
            f.write(content)

    logger.info("Generated profile for %s", company_name)
    return company_dir


def generate_all_profiles(limit: int = 40) -> int:
    """Generate Obsidian notes for the top N companies by GitHub stars."""
    logger.info("Generating Obsidian profiles...")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name FROM companies
        ORDER BY github_stars DESC, name
        LIMIT ?
        """,
        (limit,),
    )
    companies = [row[0] for row in cursor.fetchall()]
    conn.close()

    for name in companies:
        try:
            generate_profile(name)
        except Exception as e:
            logger.error("Failed to generate %s: %s", name, e)

    logger.info("Generated %s profiles in %s", len(companies), OBSIDIAN_DIR)
    return len(companies)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_all_profiles(30)
