"""Ingestion service for validating and persisting collected signals."""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from competitor_intel.core.types import SignalType
from competitor_intel.db.models import RawSignal
from competitor_intel.db.session import get_session

logger = structlog.get_logger()


class IngestionService:
    """Centralized ingestion service for all collectors.
    
    Responsibilities:
    - Validate incoming signals
    - Check for duplicates
    - Normalize data
    - Persist to database
    - Track provenance
    """
    
    def __init__(self, dedup_window_days: int = 30):
        self.dedup_window_days = dedup_window_days
        self._cache: set[str] = set()  # In-memory dedup cache
    
    def ingest(
        self,
        signals: list[dict],
        source: str,
        signal_type: SignalType = SignalType.UNKNOWN,
    ) -> int:
        """Ingest signals into the database.
        
        Args:
            signals: List of signal dictionaries
            source: Source identifier (e.g., "rss", "github")
            signal_type: Type of signal
            
        Returns:
            Number of new signals stored
        """
        stored = 0
        
        with get_session() as session:
            for signal in signals:
                try:
                    if self._is_duplicate(session, signal, source):
                        continue
                    
                    raw_signal = self._create_raw_signal(signal, source, signal_type)
                    session.add(raw_signal)
                    stored += 1
                    
                except Exception as e:
                    logger.error(
                        "ingest_failed",
                        source=source,
                        signal_title=signal.get("title", "unknown"),
                        error=str(e),
                    )
        
        logger.info("ingest_complete", source=source, stored=stored, total=len(signals))
        return stored
    
    def _is_duplicate(
        self,
        session: Session,
        signal: dict,
        source: str,
    ) -> bool:
        """Check if signal is a duplicate.
        
        Checks by:
        1. URL (if present)
        2. Semantic hash of content
        3. Title + source within dedup window
        """
        url = signal.get("url")
        if url:
            existing = session.execute(
                select(RawSignal).where(
                    RawSignal.source == source,
                    RawSignal.data_json["url"].as_string() == url,
                    RawSignal.detected_at >= datetime.utcnow() - timedelta(
                        days=self.dedup_window_days
                    ),
                )
            ).scalar_one_or_none()
            
            if existing:
                return True
        
        # Check semantic hash
        title = signal.get("title", "")
        content_hash = str(hash(str(sorted(signal.items()))))
        
        if content_hash in self._cache:
            return True
        
        self._cache.add(content_hash)
        
        # Check title + source within window
        existing = session.execute(
            select(RawSignal).where(
                RawSignal.source == source,
                RawSignal.data_json["title"].as_string() == title,
                RawSignal.detected_at >= datetime.utcnow() - timedelta(
                    days=self.dedup_window_days
                ),
            )
        ).scalar_one_or_none()
        
        return existing is not None
    
    def _create_raw_signal(
        self,
        signal: dict,
        source: str,
        signal_type: SignalType,
    ) -> RawSignal:
        """Create a RawSignal ORM object from a dictionary."""
        return RawSignal(
            source=source,
            signal_type=signal_type.value,
            data_json=signal,
            detected_at=signal.get("detected_at", datetime.utcnow()),
            company_id=signal.get("company_id"),
            semantic_hash=signal.get("semantic_hash"),
            processed=False,
        )
    
    def get_unprocessed_signals(
        self,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> list[RawSignal]:
        """Get unprocessed signals for extraction."""
        with get_session() as session:
            query = select(RawSignal).where(RawSignal.processed == False)
            
            if source:
                query = query.where(RawSignal.source == source)
            
            query = query.order_by(RawSignal.detected_at.desc()).limit(limit)
            return list(session.execute(query).scalars().all())
    
    def mark_processed(self, signal_ids: list[int]):
        """Mark signals as processed."""
        with get_session() as session:
            for signal_id in signal_ids:
                signal = session.get(RawSignal, signal_id)
                if signal:
                    signal.processed = True
