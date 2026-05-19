#!/usr/bin/env python3
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple
from collections import defaultdict

logger = logging.getLogger("competitor_mapper")

from db.connection import get_conn
from collectors.signal_processor_v2 import fuzzy_match_company, load_aliases

INDUSTRY_KEYWORDS = {
    "ai_infra": ["llm", "model", "training", "inference", "gpu", "compute", "foundation model"],
    "ai_agents": ["agent", "autonomous", "workflow", "automation", "copilot", "assistant"],
    "ai_code": ["code generation", "code completion", "ide", "developer tool", "programming"],
    "ai_search": ["search", "retrieval", "rag", "semantic search", "knowledge base"],
    "ai_video": ["video generation", "video editing", "text to video", "image to video"],
    "ai_voice": ["voice", "speech", "tts", "text to speech", "voice cloning", "audio"],
    "ai_security": ["security", "threat detection", "vulnerability", "compliance", "privacy"],
    "ai_data": ["data pipeline", "etl", "data warehouse", "analytics", "bi"],
}


def extract_companies_from_text(text: str, cursor: sqlite3.Cursor) -> List[Tuple[int, str]]:
    aliases = load_aliases(cursor)
    text_lower = text.lower()
    found = []
    cursor.execute("SELECT id, name FROM companies")
    for cid, name in cursor.fetchall():
        if name.lower() in text_lower:
            found.append((cid, name))
    return found


def compute_overlap_areas(company_a: dict, company_b: dict) -> List[str]:
    areas = []
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        a_text = " ".join(str(v or "") for v in company_a.values()).lower()
        b_text = " ".join(str(v or "") for v in company_b.values()).lower()
        a_matches = sum(1 for kw in keywords if kw in a_text)
        b_matches = sum(1 for kw in keywords if kw in b_text)
        if a_matches > 0 and b_matches > 0:
            areas.append(industry)
    if company_a.get("industry") and company_b.get("industry"):
        if company_a["industry"].lower() == company_b["industry"].lower():
            areas.append(company_a["industry"])
    return list(set(areas))


def build_competitor_map(window_days: int = 30, min_co_mentions: int = 2) -> Dict[str, Any]:
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, data_json, detected_at FROM raw_signals
        WHERE detected_at >= datetime('now', '-{} days')
        ORDER BY detected_at DESC
        """.format(window_days)
    )
    signals = cursor.fetchall()

    co_mentions = defaultdict(int)
    for sig_id, data_json, detected_at in signals:
        try:
            data = json.loads(data_json or "{}")
        except json.JSONDecodeError:
            continue
        text = " ".join(str(data.get(k, "") or "") for k in ("title", "description", "text"))
        companies = extract_companies_from_text(text, cursor)
        if len(companies) < 2:
            continue
        for i in range(len(companies)):
            for j in range(i + 1, len(companies)):
                a_id, b_id = companies[i][0], companies[j][0]
                if a_id != b_id:
                    pair = (min(a_id, b_id), max(a_id, b_id))
                    co_mentions[pair] += 1

    cursor.execute("SELECT id, name, industry FROM companies")
    company_info = {row[0]: {"name": row[1], "industry": row[2] or ""} for row in cursor.fetchall()}

    inserted = 0
    for (a_id, b_id), count in co_mentions.items():
        if count < min_co_mentions:
            continue
        a_info = company_info.get(a_id, {})
        b_info = company_info.get(b_id, {})
        overlap = compute_overlap_areas(a_info, b_info)
        confidence = min(count / 10, 1.0)
        if overlap:
            confidence = min(confidence + 0.2, 1.0)

        relationship_type = "competitor"
        if overlap:
            relationship_type = "direct_competitor" if len(overlap) >= 2 else "indirect_competitor"

        try:
            cursor.execute(
                """
                INSERT INTO competitor_relationships
                (company_id, competitor_id, relationship_type, overlap_areas, confidence, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, competitor_id) DO UPDATE SET
                    confidence = MAX(excluded.confidence, competitor_relationships.confidence),
                    overlap_areas = excluded.overlap_areas,
                    extracted_at = excluded.extracted_at
                """,
                (a_id, b_id, relationship_type, json.dumps(overlap), confidence, datetime.now(timezone.utc).isoformat()),
            )
            cursor.execute(
                """
                INSERT INTO competitor_relationships
                (company_id, competitor_id, relationship_type, overlap_areas, confidence, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, competitor_id) DO UPDATE SET
                    confidence = MAX(excluded.confidence, competitor_relationships.confidence),
                    overlap_areas = excluded.overlap_areas,
                    extracted_at = excluded.extracted_at
                """,
                (b_id, a_id, relationship_type, json.dumps(overlap), confidence, datetime.now(timezone.utc).isoformat()),
            )
            inserted += 1
        except Exception as e:
            logger.warning("Failed to insert competitor relationship: %s", e)

    conn.commit()
    conn.close()
    logger.info("Built competitor map: %d relationships from %d co-mention pairs", inserted, len(co_mentions))
    return {"relationships": inserted, "co_mention_pairs": len(co_mentions)}


def run() -> Dict[str, Any]:
    return build_competitor_map()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
