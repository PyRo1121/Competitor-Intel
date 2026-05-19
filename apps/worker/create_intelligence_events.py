"""
Create clean Intelligence Events table for dashboard/product use.
This becomes the core structured data layer.
"""

import sqlite3
import logging

from ci_paths import db_path

logger = logging.getLogger(__name__)

DB_PATH = db_path()

def create_intelligence_events_table():
    """Create the intelligence_events table if it does not exist."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intelligence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            event_type TEXT NOT NULL,           -- Funding Round, Strategic Partnership, Valuation Update, Rumored Round, Commercial Deal
            round_type TEXT,
            amount_usd INTEGER,
            valuation_usd INTEGER,
            lead_investor TEXT,
            counterparty TEXT,                  -- For partnerships (e.g. SpaceX, OpenAI)
            is_rumor INTEGER DEFAULT 0,         -- 0 = false, 1 = true
            confidence REAL DEFAULT 0.7,
            announced_date TEXT,
            source TEXT,
            source_url TEXT UNIQUE,
            raw_signal_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Create indexes for dashboard queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intel_company ON intelligence_events(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intel_event_type ON intelligence_events(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intel_date ON intelligence_events(announced_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intel_rumor ON intelligence_events(is_rumor)")

    conn.commit()
    conn.close()
    logger.info("Operation complete.")

if __name__ == "__main__":
    create_intelligence_events_table()