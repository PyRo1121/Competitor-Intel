"""
Reactive Enrichment System (Fixed)
When new companies are added, this automatically pulls deeper data without looping.
"""

import sqlite3
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from db.connection import get_conn, DB_PATH
import logging
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent



def enrich_new_companies():
    """Enrich newly discovered companies with additional signals."""
    conn = get_conn()
    cursor = conn.cursor()
    
    # Find companies added in the last 24 hours that haven't been enriched
    cursor.execute("""
        SELECT id, name 
        FROM companies 
        WHERE first_seen >= datetime('now', '-24 hours')
          AND (github_stars IS NULL OR github_stars = 0)
        LIMIT 10
    """)
    
    new_companies = cursor.fetchall()
    conn.close()
    
    if not new_companies:
        logger.info("No new companies requiring enrichment.")
        return 0
    
    logger.info("Enriching companies...")
    
    # Run collectors once (they will pick up the new companies)
    collectors = [
        ("github_collector.py", 90),
        ("website_monitor.py", 60),
    ]
    
    for script, timeout in collectors:
        try:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "collectors" / script)],
                cwd=str(BASE_DIR),
                timeout=timeout,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                logger.error("%s failed (exit %d): %s", script, result.returncode, result.stderr[:200])
            else:
                logger.info("%s completed successfully", script)
        except Exception as e:
            logger.error("Failed to run %s: %s", script, e)
    
    logger.info("Reactive enrichment complete for %d companies.", len(new_companies))
    return len(new_companies)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    enrich_new_companies()