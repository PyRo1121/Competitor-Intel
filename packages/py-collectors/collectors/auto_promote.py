"""
Auto-Promotion System
Moves high-scoring candidates from company_candidates into the main companies table.
"""

import logging
import re
import sqlite3
from datetime import datetime, timezone

from db.connection import get_conn

logger = logging.getLogger(__name__)
PROMOTION_THRESHOLD = 0.65  # 65%+ score gets promoted



def auto_promote_candidates():
    """Auto-promote high-scoring companies to active status."""
    logger.info("Running auto-promotion...")
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, description, score, discovery_source
        FROM company_candidates
        WHERE status = 'pending' AND score >= ?
        ORDER BY score DESC
    """, (PROMOTION_THRESHOLD,))
    
    candidates = cursor.fetchall()
    
    promoted = 0
    for cand_id, name, description, score, source in candidates:
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        
        try:
            cursor.execute("""
                INSERT INTO companies (name, slug, description, industry, status, first_seen, last_updated)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
            """, (name, slug, description or f"Auto-promoted from {source}", 
                  None,
                  datetime.now(timezone.utc).isoformat(),
                  datetime.now(timezone.utc).isoformat(),
              ))
            
            # Mark as promoted
            cursor.execute("""
                UPDATE company_candidates 
                SET status = 'promoted' 
                WHERE id = ?
            """, (cand_id,))
            
            promoted += 1
            logger.info("Promoted: %s (score=%.1f%%)", name, score * 100)
            
        except sqlite3.Error as e:
            logger.warning("Failed to promote candidate %s: %s", name, e)
    
    conn.commit()
    conn.close()
    
    logger.info("Operation complete.")
    return promoted

def run() -> int:
    return int(auto_promote_candidates() or 0)


if __name__ == "__main__":
    auto_promote_candidates()