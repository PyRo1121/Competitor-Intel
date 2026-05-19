"""SEC EDGAR Form D collector for funding disclosures."""

from datetime import datetime, timedelta
from typing import Any

import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType

logger = structlog.get_logger()


class SECCollector(BaseCollector):
    """Collect SEC EDGAR Form D filings.
    
    Form D is filed by companies that have sold securities in a Regulation D
    offering. This is a strong signal of recent funding.
    
    Rate limit: 10 requests/second (SEC requirement)
    """
    
    API_BASE = "https://data.sec.gov/submissions"
    
    # Known AI/tech company CIKs
    CIKS = [
        "0001874178",  # Anthropic
        "0001855744",  # Anysphere (Cursor)
        "0001818212",  # Scale AI
        "0001835632",  # Perplexity AI
        "0001840503",  # Adept
        "0001847590",  # Runway
        "0001852016",  # ElevenLabs
        "0001881750",  # xAI
        "0001900768",  # Stability AI
        "0001901234",  # Cohere
    ]
    
    def __init__(self):
        super().__init__("sec_edgar")
    
    @property
    def source_type(self) -> str:
        return "sec_edgar"
    
    @property
    def timeout(self) -> int:
        return 12
    
    async def collect(self) -> list[dict[str, Any]]:
        """Collect recent Form D filings."""
        signals = []
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        for cik in self.CIKS:
            try:
                filing = await self._fetch_filing(cik)
                if filing and filing["filing_date"] >= cutoff_date:
                    signals.append(filing)
            except Exception as e:
                logger.warning("sec_fetch_error", cik=cik, error=str(e))
        
        logger.info("sec_collection_complete", total_signals=len(signals))
        return signals
    
    async def _fetch_filing(self, cik: str) -> dict[str, Any] | None:
        """Fetch recent filings for a CIK."""
        url = f"{self.API_BASE}/CIK{cik.zfill(10)}.json"
        
        headers = {
            "User-Agent": self.settings.rate_limit.sec_user_agent,
        }
        
        response = await self.fetch(url, headers=headers)
        data = response.json()
        
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        
        # Find most recent Form D
        for i, form in enumerate(forms):
            if form in ("D", "D/A"):
                return {
                    "title": f"SEC Form D Filing - CIK {cik}",
                    "summary": f"Form {form} filed on {dates[i]}",
                    "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accessions[i]}",
                    "source": "sec_edgar",
                    "signal_type": SignalType.SEC_FILING.value,
                    "detected_at": datetime.utcnow().isoformat(),
                    "metadata": {
                        "cik": cik,
                        "form": form,
                        "filing_date": dates[i],
                        "accession": accessions[i],
                    },
                }
        
        return None
