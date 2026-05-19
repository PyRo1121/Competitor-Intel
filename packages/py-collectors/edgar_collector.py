"""
EDGAR Form D Collector — SEC submissions API for known AI/tech CIKs.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from collectors.sources_registry import SEC_USER_AGENT
from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from utils.http import close_http_client, safe_request

logger = logging.getLogger("edgar_collector")

AI_TECH_CIKS = [
    "0001874178",  # Anthropic
    "0001855744",  # Anysphere (Cursor)
    "0001818212",  # Scale AI
    "0001835632",  # Perplexity AI
    "0001840503",  # Adept
    "0001847590",  # Runway
    "0001852016",  # ElevenLabs
    "0001868275",  # Character.AI
    "0001878333",  # Inflection AI
    "0001881750",  # xAI
    "0001900768",  # Stability AI
]

SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept": "application/json",
}


def fetch_recent_form_d_filings(days_back: int = 30) -> List[Dict[str, Any]]:
    logger.info("Fetching recent SEC Form D filings...")
    signals: List[Dict[str, Any]] = []
    base_url = "https://data.sec.gov/submissions/CIK{}.json"
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    for cik in AI_TECH_CIKS:
        url = base_url.format(cik.zfill(10))
        resp = safe_request(url, timeout=12.0, headers=SEC_HEADERS)
        if resp is None:
            continue
        try:
            data = resp.json()
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accessions = filings.get("accessionNumber", [])
            for i, form in enumerate(forms):
                if form in ("D", "D/A") and dates[i] >= cutoff:
                    signals.append(
                        {
                            "company_cik": cik,
                            "accession": accessions[i],
                            "filing_date": dates[i],
                            "form": form,
                            "kind": "form_d",
                            "category": "funding",
                        }
                    )
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            logger.warning("Error parsing CIK %s: %s", cik, exc)

    logger.info("Found %s recent Form D filings", len(signals))
    return signals


def store_edgar_signals(signals: List[Dict[str, Any]]) -> int:
    if not signals:
        return 0

    conn = get_conn()
    cursor = conn.cursor()
    inserted = 0
    detected_at = datetime.now().isoformat()

    for sig in signals:
        accession = sig.get("accession") or ""
        cik = sig.get("company_cik") or ""
        if not accession:
            continue
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=D&dateb=&owner=exclude&count=40"
        dedup_key = f"form_d_{cik}_{accession}"
        payload = {
            **sig,
            "url": url,
            "link": url,
            "source": "sec_edgar",
            "detected_at": detected_at,
        }
        if insert_raw_signal_dedup(
            cursor,
            "sec_edgar",
            url,
            payload,
            detected_at=detected_at,
            dedup_key=dedup_key,
        ):
            inserted += 1

    conn.commit()
    conn.close()
    logger.info("EDGAR collector stored %s new Form D signals", inserted)
    return inserted


def run_edgar_collector() -> int:
    try:
        signals = fetch_recent_form_d_filings()
        return store_edgar_signals(signals)
    finally:
        close_http_client()


def run() -> int:
    return run_edgar_collector()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
