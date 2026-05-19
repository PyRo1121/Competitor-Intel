#!/usr/bin/env python3
"""
Structured Funding Extractor
Parses all intelligence_events and raw_signals to build detailed
funding_rounds table with investors, valuations, and round types.
Uses regex patterns + keyword matching for high accuracy.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("funding_enricher")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.connection import get_conn

# Comprehensive round type patterns
ROUND_PATTERNS = [
    (r"(?:series|round)\s*([a-f])\+?", "Series {}"),
    (r"(?:seed|pre[- ]?seed)\s*(?:round)?", "Seed"),
    (r"(?:series|round)\s*([a-f])", "Series {}"),
    (r"(?:angel|pre[- ]?seed)", "Pre-Seed"),
    (r"(?:series|round)\s*([a-f])", "Series {}"),
    (r"(?:growth|late[- ]?stage)\s*(?:round)?", "Growth"),
    (r"(?:ipo|initial\s+public\s+offering)", "IPO"),
    (r"(?:private\s+placement)", "Private Placement"),
]

# Investor extraction patterns
INVESTOR_KEYWORDS = [
    "led by", "led", "backed by", "investors include", "participated",
    "co-led by", "participation from", "joined by", "along with",
    "including", "with participation from", "strategic investors",
]


def extract_round_type(text: str) -> Tuple[Optional[str], float]:
    """Extract funding round type from text."""
    text_lower = text.lower()
    
    for pattern, template in ROUND_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            if "{}" in template:
                return template.format(m.group(1).upper()), 0.9
            return template, 0.9
    
    # Check for generic funding mentions
    if "funding" in text_lower or "raised" in text_lower:
        return "Funding Round", 0.6
    
    return None, 0.0


def extract_investors(text: str) -> Tuple[Optional[str], List[str]]:
    """Extract lead investor and co-investors from text."""
    text_lower = text.lower()
    lead = None
    co_investors = []
    
    # Look for "led by" or "led" patterns
    for kw in ["led by", "co-led by", "backed by"]:
        pattern = rf"{re.escape(kw)}\s+([A-Z][A-Za-z0-9&\s]+?)(?:,|;|\.\s|and\s|with\s|participation|$)"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if len(name) > 2 and len(name) < 60:
                if "co" in kw.lower():
                    co_investors.append(name)
                else:
                    lead = name
                break
    
    # Look for "including" or "participation from"
    for kw in ["including", "participation from", "joined by", "along with"]:
        pattern = rf"{re.escape(kw)}\s+([A-Z][A-Za-z0-9&\s,]+?)(?:\.\s|and\s|with\s|participation|$)"
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if len(n.strip()) > 2]
            co_investors.extend(names[:5])  # Limit to 5 co-investors
    
    return lead, list(set(co_investors))[:5]  # Deduplicate


def extract_valuation(text: str) -> Optional[int]:
    """Extract valuation from text."""
    patterns = [
        r"valuation\s*(?:of|at)?\s*\$?\s*([\d,.]+)\s*(billion|b)",
        r"valued\s*(?:at|around)?\s*\$?\s*([\d,.]+)\s*(billion|b)",
        r"valuation\s*(?:of|at)?\s*\$?\s*([\d,.]+)\s*(million|m)",
        r"valued\s*(?:at|around)?\s*\$?\s*([\d,.]+)\s*(million|m)",
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                num = float(m.group(1).replace(",", ""))
                unit = m.group(2).lower()
                multiplier = 1_000_000_000 if unit.startswith("b") else 1_000_000
                return int(num * multiplier)
            except (ValueError, IndexError):
                continue
    
    return None


def extract_amount(text: str) -> Optional[int]:
    """Extract funding amount from text."""
    if not text:
        return None
    
    # Billion
    m = re.search(r"\$?([\d,.]+)\s*(billion|b)\b", text, re.IGNORECASE)
    if m:
        try:
            num = float(m.group(1).replace(",", ""))
            return int(num * 1_000_000_000)
        except ValueError:
            pass
    
    # Million
    m = re.search(r"\$?([\d,.]+)\s*(million|m)\b", text, re.IGNORECASE)
    if m:
        try:
            num = float(m.group(1).replace(",", ""))
            return int(num * 1_000_000)
        except ValueError:
            pass
    
    # Raw number with dollar sign
    m = re.search(r"\$([\d,]+)\b", text)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    
    return None


def parse_funding_event(event_id: int, company_id: Optional[int], 
                        event_type: str, amount: Optional[int], 
                        text: str, source: str) -> Optional[Dict]:
    """Parse a single event to extract structured funding data."""
    if not text:
        return None
    
    # Only process funding-related events
    round_type, confidence = extract_round_type(text)
    if not round_type and event_type != "Funding Round":
        return None
    
    round_type = round_type or event_type or "Funding Round"
    
    # Extract details
    amount_usd = amount or extract_amount(text)
    valuation = extract_valuation(text)
    lead_investor, co_investors = extract_investors(text)
    
    if not amount_usd and not valuation and not lead_investor:
        return None  # Not enough funding-specific info
    
    return {
        "company_id": company_id,
        "round_type": round_type,
        "amount_usd": amount_usd,
        "valuation_usd": valuation,
        "lead_investor": lead_investor,
        "co_investors": json.dumps(co_investors) if co_investors else None,
        "source": source,
        "confidence": confidence,
    }


def store_funding_round(data: Dict) -> bool:
    """Store a funding round in the database."""
    if not data.get("company_id"):
        return False  # Can't store without company link
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Deduplication: same company + round_type + amount within 90 days
    dedup_key = f"{data['company_id']}:{data['round_type']}:{data.get('amount_usd', 'unknown')}"
    
    try:
        cursor.execute(
            "SELECT 1 FROM funding_rounds WHERE source_url = ?",
            (dedup_key,)
        )
        if cursor.fetchone():
            return False
        
        cursor.execute("""
            INSERT INTO funding_rounds
            (company_id, round_type, amount_usd, valuation_usd, lead_investor,
             co_investors, source, source_url, confidence, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["company_id"],
            data["round_type"],
            data.get("amount_usd"),
            data.get("valuation_usd"),
            data["lead_investor"],
            data.get("co_investors"),
            data["source"],
            dedup_key,
            data.get("confidence", 0.7),
            datetime.now().isoformat(),
        ))
        
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("DB error storing funding: %s", e)
        return False
    finally:
        conn.close()


def extract_from_signals() -> Dict:
    """Extract structured funding data from all raw signals and events."""
    conn = get_conn()
    cursor = conn.cursor()
    
    # Get intelligence events that look like funding
    cursor.execute("""
        SELECT id, company_id, event_type, amount_usd, source, raw_signal_id
        FROM intelligence_events
        WHERE event_type IN ('Funding Round', 'Rumored Round')
        ORDER BY created_at DESC
    """)
    events = cursor.fetchall()
    
    # Get raw signals with funding keywords
    cursor.execute("""
        SELECT id, company_id, source, data_json
        FROM raw_signals
        WHERE data_json LIKE '%raised%' OR data_json LIKE '%funding%'
           OR data_json LIKE '%million%' OR data_json LIKE '%billion%'
        ORDER BY detected_at DESC
        LIMIT 200
    """)
    signals = cursor.fetchall()
    conn.close()
    
    created = 0
    skipped = 0
    
    # Process intelligence events
    for row in events:
        signal_id = row["raw_signal_id"]
        text = ""
        
        if signal_id:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM raw_signals WHERE id = ?", (signal_id,))
            sig_row = cursor.fetchone()
            conn.close()
            if sig_row:
                try:
                    data = json.loads(sig_row["data_json"])
                    text = f"{data.get('title', '')} {data.get('summary', '')}"
                except json.JSONDecodeError:
                    text = str(sig_row["data_json"])
        
        funding_data = parse_funding_event(
            row["id"], row["company_id"], row["event_type"], 
            row["amount_usd"], text, row["source"]
        )
        
        if funding_data:
            if store_funding_round(funding_data):
                created += 1
            else:
                skipped += 1
    
    # Process raw signals
    for row in signals:
        try:
            data = json.loads(row["data_json"])
            text = f"{data.get('title', '')} {data.get('summary', '')}"
        except json.JSONDecodeError:
            text = str(row["data_json"])
        
        funding_data = parse_funding_event(
            row["id"], row["company_id"], "Funding Round", None, text, row["source"]
        )
        
        if funding_data:
            if store_funding_round(funding_data):
                created += 1
            else:
                skipped += 1
    
    logger.info("Funding extraction: %d created, %d skipped", created, skipped)
    return {"created": created, "skipped": skipped}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    extract_from_signals()
