"""Website change detection collector."""

import hashlib
from datetime import datetime
from typing import Any

import structlog

from competitor_intel.core.collector import BaseCollector
from competitor_intel.core.types import SignalType
from competitor_intel.db.models import Company, WebsiteSnapshot
from competitor_intel.db.session import get_session

logger = structlog.get_logger()


class WebsiteCollector(BaseCollector):
    """Monitor company websites for changes.
    
    Detects:
    - Content changes
    - New blog posts
    - Pricing updates
    - Product launches
    """
    
    def __init__(self):
        super().__init__("website")
    
    @property
    def source_type(self) -> str:
        return "website"
    
    async def collect(self) -> list[dict[str, Any]]:
        """Monitor tracked company websites for changes."""
        # Get companies with websites from database
        with get_session() as session:
            companies = session.query(Company).filter(
                Company.website.isnot(None)
            ).limit(20).all()
        
        signals = []
        for company in companies:
            try:
                signal = await self._check_website(company)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.warning(
                    "website_check_error",
                    company=company.name,
                    url=company.website,
                    error=str(e),
                )
        
        logger.info("website_collection_complete", total_signals=len(signals))
        return signals
    
    async def _check_website(self, company: Company) -> dict[str, Any] | None:
        """Check a single website for changes."""
        if not company.website:
            return None
        
        response = await self.fetch(company.website)
        content = response.text
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check against last snapshot
        with get_session() as session:
            last_snapshot = session.query(WebsiteSnapshot).filter(
                WebsiteSnapshot.company_id == company.id
            ).order_by(WebsiteSnapshot.checked_at.desc()).first()
            
            if last_snapshot and last_snapshot.content_hash == content_hash:
                logger.debug(
                    "website_no_change",
                    company=company.name,
                    url=company.website,
                )
                return None
            
            # Store new snapshot
            snapshot = WebsiteSnapshot(
                company_id=company.id,
                website=company.website,
                content_hash=content_hash,
            )
            session.add(snapshot)
        
        logger.info(
            "website_change_detected",
            company=company.name,
            url=company.website,
        )
        
        return {
            "title": f"Website change detected: {company.name}",
            "summary": f"Content updated on {company.website}",
            "url": company.website,
            "source": "website",
            "signal_type": SignalType.WEBSITE_CHANGE.value,
            "detected_at": datetime.utcnow().isoformat(),
            "company_id": company.id,
            "metadata": {
                "company": company.name,
                "content_hash": content_hash,
                "previous_hash": last_snapshot.content_hash if last_snapshot else None,
            },
        }
