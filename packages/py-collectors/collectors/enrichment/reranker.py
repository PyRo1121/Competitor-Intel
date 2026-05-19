#!/usr/bin/env python3
"""
Semantic Reranker for Competitor Intelligence Search
Reranks database search results using embedding cosine similarity
to surface the most relevant matches for a query.
"""

import json
import logging
import sqlite3
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("reranker")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from db.connection import get_conn
from collectors.enrichment.embedding_generator import get_embedding, cosine_similarity


def rerank_companies(query: str, top_k: int = 10) -> List[Dict]:
    """Search and rerank companies by semantic relevance."""
    query_emb = get_embedding(query)
    if not query_emb:
        logger.warning("Failed to generate query embedding")
        return []
    
    conn = get_conn()
    cursor = conn.cursor()
    
    # Get companies with embeddings
    cursor.execute("""
        SELECT c.id, c.name, c.industry, c.github_stars, c.score,
               cd.description_long, cd.business_model, cd.tech_stack, cd.embedding
        FROM companies c
        LEFT JOIN company_details cd ON cd.company_id = c.id
        WHERE cd.embedding IS NOT NULL
        LIMIT 100
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    scored = []
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
            score = cosine_similarity(query_emb, emb)
            
            # Boost by company score if available
            company_score = row["score"] or 0
            final_score = min(1.0, score + (company_score * 0.05))
            
            scored.append({
                "type": "company",
                "id": row["id"],
                "name": row["name"],
                "industry": row["industry"],
                "github_stars": row["github_stars"],
                "score": final_score,
                "description": row["description_long"],
                "business_model": row["business_model"],
                "tech_stack": row["tech_stack"],
            })
        except (json.JSONDecodeError, TypeError):
            continue
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def rerank_funding(query: str, top_k: int = 10) -> List[Dict]:
    """Search and rerank funding rounds by semantic relevance."""
    query_emb = get_embedding(query)
    if not query_emb:
        return []
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT fr.id, c.name, fr.round_type, fr.amount_usd, 
               fr.valuation_usd, fr.lead_investor, fr.embedding
        FROM funding_rounds fr
        JOIN companies c ON c.id = fr.company_id
        WHERE fr.embedding IS NOT NULL
        LIMIT 100
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    scored = []
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
            score = cosine_similarity(query_emb, emb)
            
            # Boost by amount for funding-specific queries
            amount = row["amount_usd"] or 0
            amount_boost = min(0.1, amount / 10_000_000_000)  # Max 0.1 boost for $10B+
            
            final_score = min(1.0, score + amount_boost)
            
            scored.append({
                "type": "funding",
                "id": row["id"],
                "company": row["name"],
                "round": row["round_type"],
                "amount": row["amount_usd"],
                "valuation": row["valuation_usd"],
                "lead_investor": row["lead_investor"],
                "score": final_score,
            })
        except (json.JSONDecodeError, TypeError):
            continue
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def rerank_events(query: str, top_k: int = 10) -> List[Dict]:
    """Search and rerank intelligence events by semantic relevance."""
    query_emb = get_embedding(query)
    if not query_emb:
        return []
    
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ie.id, c.name, ie.event_type, ie.amount_usd, 
               ie.confidence, ie.source, ie.created_at, ie.embedding
        FROM intelligence_events ie
        LEFT JOIN companies c ON c.id = ie.company_id
        WHERE ie.embedding IS NOT NULL
        LIMIT 200
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    scored = []
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
            score = cosine_similarity(query_emb, emb)
            
            # Boost by confidence
            conf = row["confidence"] or 0.5
            final_score = min(1.0, score + (conf * 0.05))
            
            scored.append({
                "type": "event",
                "id": row["id"],
                "company": row["name"],
                "event_type": row["event_type"],
                "amount": row["amount_usd"],
                "confidence": conf,
                "source": row["source"],
                "date": row["created_at"],
                "score": final_score,
            })
        except (json.JSONDecodeError, TypeError):
            continue
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def unified_search(query: str, top_k: int = 15) -> Dict[str, List[Dict]]:
    """Unified search across all content types with reranking."""
    logger.info("Unified search for: '%s'", query)
    
    companies = rerank_companies(query, top_k=5)
    funding = rerank_funding(query, top_k=5)
    events = rerank_events(query, top_k=10)
    
    # Merge and deduplicate by ID
    all_results = companies + funding + events
    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "companies": companies,
        "funding": funding,
        "events": events,
        "top_results": all_results[:top_k],
    }


def print_results(results: Dict):
    """Pretty print search results."""
    print(f"\n{'='*60}")
    print(f"SEARCH RESULTS")
    print(f"{'='*60}")
    
    if results["companies"]:
        print(f"\nCompanies ({len(results['companies'])}):")
        for c in results["companies"]:
            stars = f" ⭐{c['github_stars']:,}" if c['github_stars'] else ""
            print(f"  [{c['score']:.3f}] {c['name']}{stars} | {c['industry'] or 'Unknown'}")
            if c['description']:
                print(f"    {c['description'][:80]}...")
    
    if results["funding"]:
        print(f"\nFunding Rounds ({len(results['funding'])}):")
        for f in results["funding"]:
            amt = f"${f['amount']:,}" if f['amount'] else "Undisclosed"
            lead = f" led by {f['lead_investor']}" if f['lead_investor'] else ""
            print(f"  [{f['score']:.3f}] {f['company']} | {f['round']} | {amt}{lead}")
    
    if results["events"]:
        print(f"\nEvents ({len(results['events'])}):")
        for e in results["events"][:5]:
            company = e['company'] or 'Unknown'
            amt = f" ${e['amount']:,}" if e['amount'] else ""
            print(f"  [{e['score']:.3f}] {company} | {e['event_type']}{amt}")
    
    print(f"\n{'='*60}")


if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Semantic search with reranking")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--top-k", type=int, default=15, help="Number of results")
    args = parser.parse_args()
    
    results = unified_search(args.query, top_k=args.top_k)
    print_results(results)
