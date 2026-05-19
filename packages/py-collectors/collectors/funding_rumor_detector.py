"""
Funding Rumor Detector
Extracts potential funding signals from raw text using regex patterns.
Creates structured funding_events when confidence threshold is met.
"""

import json
import logging
import re
import sqlite3
from typing import Dict, Optional, Tuple

from db.connection import get_conn
from db.ingest import get_company_id

logger = logging.getLogger(__name__)


def parse_valuation(text: str) -> Optional[Tuple[float, str]]:
    """Extract valuation from text (e.g. $3B+, $40B, 2.5 billion)."""
    patterns = [
        r'\$?([\d.]+)\s*(B|billion)',
        r'\$?([\d.]+)\s*(M|million)',
        r'\$([\d.]+)(B|b)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            if 'b' in unit:
                return value * 1000, f"${value}B"
            elif 'm' in unit:
                return value, f"${value}M"
    return None

def detect_round_type(text: str) -> Optional[str]:
    """Detect funding round type."""
    text_lower = text.lower()
    if 'series a' in text_lower: return 'Series A'
    if 'series b' in text_lower: return 'Series B'
    if 'series c' in text_lower: return 'Series C'
    if 'series d' in text_lower: return 'Series D'
    if 'series e' in text_lower: return 'Series E'
    if 'extension' in text_lower: return 'Extension'
    if 'secondary' in text_lower: return 'Secondary'
    if 'raising' in text_lower or 'round' in text_lower: return 'Unknown Round'
    return None

def process_funding_signal(signal: Dict) -> bool:
    """Process a raw funding signal and create structured event if possible."""
    company_name = signal.get('company') or ''
    company_id = get_company_id(company_name)
    if not company_id:
        return False

    text = signal.get('text', '')
    valuation = parse_valuation(text)
    round_type = detect_round_type(text)

    if valuation or round_type:
        conn = get_conn()
        cursor = conn.cursor()
        
        # Create funding event (matching actual schema)
        cursor.execute("""
            INSERT INTO funding_events 
            (company_id, round_type, amount_usd, valuation_usd, announced_date, source, source_url, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            company_id,
            round_type or 'Unknown',
            int(valuation[0] * 1_000_000) if valuation else None,
            int(valuation[0] * 1_000_000_000) if valuation else None,
            (signal.get('posted_at') or '')[:10] if signal.get('posted_at') else None,
            'X / Grok',
            signal.get('url'),
            signal.get('confidence', 0.7)
        ))
        
        conn.commit()
        conn.close()
        logger.info("Created funding event for company_id=%s round=%s", company_id, round_type)
        return True
    
    return False

def run_funding_detector():
    """Scan all unprocessed funding signals and create events."""
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, company_id, data_json 
        FROM raw_signals 
        WHERE source = 'x_funding' AND processed = 0
    """)
    signals = cursor.fetchall()
    
    processed = 0
    for sig_id, company_id, data_json in signals:
        try:
            data = json.loads(data_json)
            if process_funding_signal(data):
                cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (sig_id,))
                processed += 1
        except (json.JSONDecodeError, sqlite3.Error) as e:
            logger.error("Error processing signal %s: %s", sig_id, e)
    
    conn.commit()
    conn.close()
    logger.info("Funding Detector: Processed %d signals into structured events.", processed)
    return processed

if __name__ == "__main__":
    run_funding_detector()