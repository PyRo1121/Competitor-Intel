"""
Investor Intelligence Collector v3
Expanded Tier 1 + Tier 2 list with strong detection logic.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

from db.connection import get_conn, DB_PATH
import logging
logger = logging.getLogger(__name__)

TIER_1_INVESTORS = [
    "Andreessen Horowitz", "a16z", "Sequoia Capital", "Benchmark", "General Catalyst",
    "Thrive Capital", "Lightspeed Venture Partners", "Khosla Ventures", "Founders Fund",
    "Coatue", "Index Ventures", "Accel", "Bessemer Venture Partners", "Greylock",
    "Kleiner Perkins", "Redpoint Ventures", "Union Square Ventures", "First Round Capital",
    "True Ventures", "Shasta Ventures", "Felicis Ventures", "BoxGroup", "SV Angel",
    "Y Combinator", "Pioneer Fund", "Craft Ventures", "Homebrew", "Fuel Ventures",
    "Eniac Ventures", "Ludlow Ventures", "Lerer Hippeau", "RRE Ventures"
]

TIER_2_INVESTORS = [
    "Tiger Global", "SoftBank Vision Fund", "DST Global", "Dragoneer Investment Group",
    "D1 Capital Partners", "Coatue", "Baillie Gifford", "Fidelity", "T. Rowe Price",
    "BlackRock", "Wellington Management", "Paradigm", "Crypto.com Capital", "Blockchain Capital",
    "Pantera Capital", "Polychain", "Multicoin Capital", "Framework Ventures",
    "Ribbit Capital", "QED Investors", "Point72 Ventures", "8VC", "Lux Capital",
    "Data Collective", "DCVC", "Gradient Ventures", "Two Sigma Ventures",
    "Menlo Ventures", "Norwest Venture Partners", "Insight Partners", "Salesforce Ventures"
]

def seed_high_quality_investors():
    """Seed Tier 1 and Tier 2 investors into the database."""
    logger.info("Seeding expanded Tier 1 + Tier 2 investors...")
    conn = get_conn()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    seeded = 0

    for name in TIER_1_INVESTORS:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO investors (name, type, tier, first_seen)
                VALUES (?, 'VC', 1, ?)
            """, (name, now))
            if cursor.rowcount > 0:
                seeded += 1
        except sqlite3.Error as e:
            logger.error("Error seeding investor %s: %s", name, e)

    for name in TIER_2_INVESTORS:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO investors (name, type, tier, first_seen)
                VALUES (?, 'VC', 2, ?)
            """, (name, now))
            if cursor.rowcount > 0:
                seeded += 1
        except sqlite3.Error as e:
            logger.error("Error seeding investor %s: %s", name, e)

    conn.commit()
    conn.close()
    logger.info("Seeded/updated %s high-quality investors", seeded)

def run_investor_collector() -> int:
    seeded = seed_high_quality_investors()
    logger.info("Investor enrichment complete. Seeded %d investors.", seeded)
    return seeded


def run() -> int:
    return run_investor_collector()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()