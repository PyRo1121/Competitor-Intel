#!/usr/bin/env python3
"""
Enhanced Funding & Deal Detector
Catches ALL types of capital flow:
- Traditional VC: Seed, Series A/B/C/D, Growth
- Strategic/Corporate: XAI invests in Cursor, NVIDIA backs CoreWeave
- Acquisitions with investment components: OpenAI acquires + invests
- Partnerships with equity: Microsoft-OpenAI $10B+ deal
- Debt financing, revenue-based financing, secondary transactions
- Public company investments in private companies
- Government contracts/grants with equity implications
"""

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("enhanced_funding")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_conn

# BROAD FUNDING SIGNALS - catches everything
FUNDING_KEYWORDS = [
    # Traditional
    "raised", "funding", "series a", "series b", "series c", "series d", "series e",
    "seed round", "pre-seed", "angel round", "growth round", "late-stage",
    # Strategic/Corporate
    "strategic investment", "corporate venture", "strategic round",
    "invests in", "backs", "pours", "pumps", "injects", "commitment",
    "partnership worth", "partnership valued", "multi-year deal",
    # Acquisitions with investment
    "acquires stake", "takes stake", "buys stake", "equity stake",
    "majority stake", "minority stake", "controlling stake",
    # Mega deals
    "billion dollar", "multi-billion", "billion-dollar", "billion+",
    "landmark deal", "massive investment", "major investment",
    # Debt/Alternative
    "debt financing", "credit facility", "revolving credit", "term loan",
    "revenue-based financing", "venture debt", "convertible note",
    # Public company actions
    "public offering", "ipo", "direct listing", "spac merger",
    "goes public", "files for ipo", "s-1 filing", "registration statement",
    # Government/Grants
    "defense contract", "government contract", "darpa", "nsf grant",
    "sbir", "sttr", "grant funding", "federal funding",
    # Secondary/Other
    "secondary transaction", "secondary sale", "share buyback",
    "tender offer", "recapitalization", "restructuring",
]

# Event type classification
DEAL_TYPES = {
    "Strategic Investment": {
        "patterns": [
            r"(?:strategic|corporate)\s+(?:investment|investor|backer)",
            r"(?:xai|openai|microsoft|google|amazon|nvidia|meta)\s+(?:invests?|backs?|pours?)",
            r"invests?\s+\$?[\d,.]+\s*(?:billion|million)",
            r"(?:takes?|acquires?|buys?)\s+(?:a\s+)?(?:majority|minority|controlling)\s+stake",
            r"equity\s+(?:investment|stake|partnership)",
        ],
        "keywords": ["strategic investment", "corporate venture", "equity stake", 
                     "takes stake", "acquires stake", "backs", "invests in"],
    },
    "Partnership Deal": {
        "patterns": [
            r"(?:partnership|deal|alliance)\s+(?:worth|valued\s+at)\s+\$?[\d,.]+\s*(?:billion|million)",
            r"multi[- ]?year\s+(?:partnership|deal|agreement)",
            r"(?:microsoft|google|amazon|nvidia|meta)\s+(?:partners|teams\s+up|collaborates)",
        ],
        "keywords": ["partnership worth", "partnership valued", "multi-year deal",
                     "collaboration deal", "strategic partnership"],
    },
    "Mega Round": {
        "patterns": [
            r"\$?[\d,.]+\s*(?:billion|b)\s+(?:round|funding|investment)",
            r"(?:largest|biggest|massive|landmark)\s+(?:round|deal|investment)",
        ],
        "keywords": ["billion dollar", "multi-billion", "billion+", "landmark deal",
                     "massive investment", "largest round"],
    },
    "Acquisition": {
        "patterns": [
            r"(?:acquires?|buys?|purchases?)\s+[A-Z]",
            r"(?:merger|acquisition|buyout)\s+(?:of|with)",
        ],
        "keywords": ["acquires", "acquisition", "buys", "purchased", "merger", "buyout"],
    },
    "Debt Financing": {
        "patterns": [
            r"(?:debt|credit|loan|facility)\s+(?:financing|facility|raise)",
            r"\$?[\d,.]+\s*(?:million|billion)\s+(?:credit|debt|loan)",
        ],
        "keywords": ["debt financing", "credit facility", "venture debt", 
                     "term loan", "revolving credit", "convertible note"],
    },
    "Public Market": {
        "patterns": [
            r"(?:files?|files\s+for)\s+(?:ipo|s-1|registration)",
            r"(?:going|goes)\s+public",
            r"(?:spac|special\s+purpose)\s+(?:merger|acquisition)",
        ],
        "keywords": ["ipo", "going public", "s-1 filing", "spac merger", 
                     "direct listing", "public offering"],
    },
    "Traditional VC": {
        "patterns": [
            r"(?:series|round)\s*[a-e]\+?",
            r"(?:seed|pre[- ]?seed)\s*(?:round)?",
            r"(?:growth|late[- ]?stage)\s*(?:round)?",
        ],
        "keywords": ["series a", "series b", "series c", "seed round", 
                     "growth round", "venture capital"],
    },
}

# Major strategic/corporate investors to watch
STRATEGIC_INVESTORS = [
    "microsoft", "google", "alphabet", "amazon", "nvidia", "meta", "facebook",
    "apple", "salesforce", "oracle", "ibm", "intel", "amd", "qualcomm",
    "samsung", "softbank", "tencent", "alibaba", "baidu", "bytedance",
    "xai", "openai", "anthropic", "cohere", "stability ai", "midjourney",
    "anduril", "palantir", "defense", "nsa", "cia", "dod", "darpa",
    "saudi", "pif", "mubadala", "temasek", "gic", "qia",
]


def extract_amount_enhanced(text: str) -> Optional[int]:
    """Extract any dollar amount from text with comprehensive patterns."""
    if not text:
        return None
    
    text = text.replace(",", "")
    
    # Billion with explicit $ sign
    m = re.search(r"\$([\d.]+)\s*(?:billion|b)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1)) * 1_000_000_000)
        except ValueError:
            pass
    
    # Billion without $ (e.g., "10 billion")
    m = re.search(r"([\d.]+)\s*(?:billion|b)\s+(?:dollar|deal|investment|round)", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1)) * 1_000_000_000)
        except ValueError:
            pass
    
    # Million with explicit $ sign
    m = re.search(r"\$([\d.]+)\s*(?:million|m)\b", text, re.IGNORECASE)
    if m:
        try:
            return int(float(m.group(1)) * 1_000_000)
        except ValueError:
            pass
    
    # Raw numbers with $ and commas already removed
    m = re.search(r"\$([\d]+)\b", text)
    if m:
        try:
            val = int(m.group(1))
            if val > 1_000_000:  # Only catch large amounts
                return val
        except ValueError:
            pass
    
    return None


def classify_deal_type(text: str) -> Tuple[str, float]:
    """Classify deal type with confidence score."""
    text_lower = text.lower()
    scores = {}
    
    for deal_type, config in DEAL_TYPES.items():
        score = 0.0
        
        # Check regex patterns
        for pattern in config["patterns"]:
            if re.search(pattern, text_lower):
                score += 0.4
        
        # Check keywords
        keyword_matches = sum(1 for kw in config["keywords"] if kw in text_lower)
        score += keyword_matches * 0.15
        
        if score > 0:
            scores[deal_type] = min(score, 1.0)
    
    if not scores:
        # Check if it's funding-related at all
        if any(kw in text_lower for kw in FUNDING_KEYWORDS):
            return "Funding Round", 0.5
        return "General News", 0.0
    
    best = max(scores, key=scores.get)
    return best, scores[best]


def extract_strategic_investors(text: str) -> List[str]:
    """Extract known strategic/corporate investors from text."""
    text_lower = text.lower()
    found = []
    
    for investor in STRATEGIC_INVESTORS:
        if investor in text_lower:
            found.append(investor.title())
    
    # Also look for "led by" or "backed by" patterns
    m = re.search(r"(?:led\s+by|backed\s+by|investment\s+from)\s+([A-Z][A-Za-z0-9&\s]{2,50}?)(?:,|;|\.|\s+and|\s+with|$)", text)
    if m:
        name = m.group(1).strip()
        if name and name not in found:
            found.append(name)
    
    return list(set(found))[:5]  # Deduplicate, limit to 5


def extract_counterparty(text: str) -> Optional[str]:
    """Extract the other company in a deal (e.g., XAI invests IN Cursor)."""
    patterns = [
        r"([A-Z][A-Za-z0-9.]+)\s+(?:invests?|backs?|acquires?|buys?|takes?)\s+(?:a\s+)?(?:stake\s+in\s+)?(?:in\s+)?([A-Z][A-Za-z0-9.]+)",
        r"([A-Z][A-Za-z0-9.]+)\s+(?:partners\s+with|teams\s+up\s+with|collaborates\s+with)\s+([A-Z][A-Za-z0-9.]+)",
        r"([A-Z][A-Za-z0-9.]+)\s+(?:acquires?|buys?)\s+([A-Z][A-Za-z0-9.]+)",
    ]
    
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(2).strip()
    
    return None


def process_signal_for_funding(signal_id: int, company_id: Optional[int], 
                                source: str, data_json: str) -> Optional[Dict]:
    """Process a single signal to extract enhanced funding data."""
    try:
        data = json.loads(data_json) if data_json else {}
    except json.JSONDecodeError:
        data = {"raw": str(data_json)[:1000]}
    
    text = f"{data.get('title', '')} {data.get('summary', '')} {data.get('content', '')}"
    if not text.strip():
        return None
    
    # Classify deal type
    deal_type, confidence = classify_deal_type(text)
    
    # If not funding-related, skip
    if deal_type == "General News" and confidence == 0.0:
        return None
    
    # Extract amount
    amount = extract_amount_enhanced(text)
    
    # Extract investors
    investors = extract_strategic_investors(text)
    lead_investor = investors[0] if investors else None
    
    # Extract counterparty (who got the money)
    counterparty = extract_counterparty(text)
    
    # Extract valuation
    valuation = None
    m = re.search(r"(?:valuation|valued)\s+(?:at|of)\s+\$?([\d.]+)\s*(billion|million)", text, re.IGNORECASE)
    if m:
        try:
            num = float(m.group(1))
            mult = 1_000_000_000 if m.group(2).lower().startswith("b") else 1_000_000
            valuation = int(num * mult)
        except ValueError:
            pass
    
    return {
        "signal_id": signal_id,
        "company_id": company_id,
        "event_type": deal_type,
        "amount_usd": amount,
        "valuation_usd": valuation,
        "lead_investor": lead_investor,
        "co_investors": json.dumps(investors[1:]) if len(investors) > 1 else None,
        "counterparty": counterparty,
        "confidence": confidence,
        "source": source,
        "text_preview": text[:200],
    }


def store_enhanced_funding_event(data: Dict) -> bool:
    """Store a funding event with deduplication."""
    conn = get_conn()
    cursor = conn.cursor()
    
    # Deduplication key
    dedup = f"{data['company_id']}:{data['event_type']}:{data.get('amount_usd', 'unknown')}:{hash(data['text_preview']) % 10000}"
    
    try:
        cursor.execute("SELECT 1 FROM intelligence_events WHERE source_url = ?", (dedup,))
        if cursor.fetchone():
            return False
        
        cursor.execute("""
            INSERT INTO intelligence_events
            (company_id, event_type, amount_usd, valuation_usd, lead_investor,
             is_rumor, confidence, source, source_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["company_id"],
            data["event_type"],
            data.get("amount_usd"),
            data.get("valuation_usd"),
            data["lead_investor"],
            1 if "rumor" in data["event_type"].lower() else 0,
            data["confidence"],
            data["source"],
            dedup,
            datetime.now().isoformat(),
        ))
        
        # Also store in funding_rounds for structured data (only if company matched)
        if data.get("company_id") and (data.get("amount_usd") or data.get("valuation_usd")):
            cursor.execute("""
                INSERT INTO funding_rounds
                (company_id, round_type, amount_usd, valuation_usd, lead_investor,
                 co_investors, source, source_url, confidence, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["company_id"],
                data["event_type"],
                data.get("amount_usd"),
                data.get("valuation_usd"),
                data["lead_investor"],
                data.get("co_investors"),
                data["source"],
                dedup,
                data["confidence"],
                datetime.now().isoformat(),
            ))
        
        conn.commit()
        logger.info("Stored %s event: %s | %s | Amount: %s",
                   data["event_type"], data.get("lead_investor") or "Unknown",
                   data["text_preview"][:60],
                   f"${data['amount_usd']:,}" if data.get("amount_usd") else "N/A")
        return True
    except sqlite3.Error as e:
        logger.error("DB error: %s", e)
        return False
    finally:
        conn.close()


def run_enhanced_funding_detection(batch_size: int = 200) -> Dict:
    """Run enhanced funding detection on all unprocessed signals."""
    conn = get_conn()
    cursor = conn.cursor()
    
    # Get signals that might contain funding info
    cursor.execute("""
        SELECT id, company_id, source, data_json
        FROM raw_signals
        WHERE processed = 0 OR processed IS NULL
        ORDER BY detected_at DESC
        LIMIT ?
    """, (batch_size,))
    
    signals = cursor.fetchall()
    conn.close()
    
    if not signals:
        logger.info("No unprocessed signals to scan")
        return {"processed": 0, "funding_found": 0, "by_type": {}}
    
    logger.info("Scanning %d signals for funding/deals...", len(signals))
    
    stats = {"processed": 0, "funding_found": 0, "by_type": {}}
    
    for row in signals:
        result = process_signal_for_funding(
            row["id"], row["company_id"], row["source"], row["data_json"]
        )
        
        if result:
            if store_enhanced_funding_event(result):
                stats["funding_found"] += 1
                stats["by_type"][result["event_type"]] = stats["by_type"].get(result["event_type"], 0) + 1
        
        # Mark as processed
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE raw_signals SET processed = 1 WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        
        stats["processed"] += 1
    
    logger.info("Funding scan complete: %d signals, %d funding events found",
                stats["processed"], stats["funding_found"])
    for event_type, count in stats["by_type"].items():
        logger.info("  %s: %d", event_type, count)
    
    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    run_enhanced_funding_detection()
