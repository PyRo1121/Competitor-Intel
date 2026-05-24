import logging

logger = logging.getLogger(__name__)
#!/usr/bin/env python3
"""
World-class Investor Tier System
Tier 1 = Top-tier (a16z, Sequoia, Benchmark, etc.)
Tier 2 = Strong institutional
Used for scoring boost + "Tier 1 Backing" report sections.
"""

TIER_1 = {
    "a16z",
    "andreessen horowitz",
    "sequoia",
    "benchmark",
    "greylock",
    "accel",
    "kleiner perkins",
    "kp",
    "bessemer",
    "lightspeed",
    "index ventures",
    "general catalyst",
    "gc",
    "thrive capital",
    "founders fund",
    "ff",
    "union square ventures",
    "usv",
    "first round",
    "y combinator",
    "yc",
    "openai",
    "anthropic fund",
}

TIER_2 = {
    "redpoint",
    "mayfield",
    "nea",
    "new enterprise associates",
    "insight partners",
    "insight",
    "battery ventures",
    "battery",
    "felicis",
    "founders circle",
    "cohesity",
    "menlo ventures",
    "khosla ventures",
    "khosla",
    "spark capital",
    "spark",
    "canvas",
    "canvas ventures",
    "costanoa",
    "costanoa ventures",
}


def get_investor_tier(name: str) -> int:
    """Return 1 for Tier 1, 2 for Tier 2, 0 for unknown."""
    n = name.lower().strip()
    if any(t in n for t in TIER_1):
        return 1
    if any(t in n for t in TIER_2):
        return 2
    return 0


def enrich_investors_from_events():
    """Scan intelligence_events and link investors with tier."""
    import sqlite3

    from ci_paths import db_path

    db = db_path()
    conn = sqlite3.connect(db)
    cur = conn.cursor()

    # Ensure investors table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS investors (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            tier INTEGER DEFAULT 0,
            description TEXT
        )
    """)

    cur.execute("""
        SELECT lead_investor, source FROM intelligence_events
        WHERE lead_investor IS NOT NULL
    """)
    rows = cur.fetchall()

    enriched = 0
    for lead, _source in rows:
        if not lead:
            continue
        tier = get_investor_tier(lead)
        cur.execute(
            """
            INSERT OR IGNORE INTO investors (name, tier)
            VALUES (?, ?)
        """,
            (lead, tier),
        )
        if tier > 0:
            enriched += 1

    conn.commit()
    conn.close()
    logger.info("Investor enrichment complete. Linked %d tiered investors.", enriched)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    enrich_investors_from_events()
