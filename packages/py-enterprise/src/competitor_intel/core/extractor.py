"""LLM-powered event extraction — converts raw signals into structured intelligence events."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from competitor_intel.core.types import EventType
from competitor_intel.db.models import IntelligenceEvent, RawSignal
from competitor_intel.db.session import get_session

logger = structlog.getLogger()


class EventExtractor:
    """Extracts structured intelligence events from raw signals using LLM analysis.

    Event types extracted:
    - funding_round: New funding rounds with amount, investors
    - acquisition: Company acquisitions
    - partnership: Strategic partnerships
    - product_launch: New product/feature launches
    - pricing_change: Pricing updates
    - rumored_round: Unconfirmed funding rumors
    - mega_round: Rounds above $100M
    """

    FUNDING_KEYWORDS = [
        "raised",
        "funding",
        "series a",
        "series b",
        "series c",
        "seed round",
        "series seed",
        "round",
        "investment",
        "invested",
        "valuation",
        "led by",
        "participated",
        "investors",
        "funded",
    ]

    ACQUISITION_KEYWORDS = [
        "acquired",
        "acquisition",
        "buying",
        "bought",
        "merge",
        "merger",
        "acquires",
        "takeover",
    ]

    PRODUCT_KEYWORDS = [
        "launch",
        "released",
        "announced",
        "new feature",
        "new product",
        "introducing",
        "unveiled",
        "rolled out",
        "ga",
        "general availability",
    ]

    PRICING_KEYWORDS = [
        "pricing",
        "price increase",
        "price cut",
        "new pricing",
        "pricing update",
        "plan changes",
    ]

    def extract_from_signals(self, limit: int = 50) -> list[IntelligenceEvent]:
        """Process unprocessed raw signals and extract events."""
        with get_session() as session:
            signals = (
                session.execute(
                    select(RawSignal)
                    .where(RawSignal.processed.is_(False))
                    .order_by(RawSignal.detected_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )

        events = []
        for signal in signals:
            try:
                extracted = self._extract_event(signal)
                if extracted:
                    events.append(extracted)
            except Exception as e:
                logger.error("extraction_error", signal_id=signal.id, error=str(e))

        logger.info(
            "extraction_complete", signals_processed=len(signals), events_extracted=len(events)
        )
        return events

    def _extract_event(self, signal: RawSignal) -> IntelligenceEvent | None:
        """Extract an intelligence event from a single raw signal."""
        data = signal.data_json
        title = data.get("title", "").lower()
        summary = data.get("summary", "").lower()
        text = f"{title} {summary}"

        event_type = self._classify_event(text)
        if not event_type:
            return None

        event = IntelligenceEvent(
            company_id=signal.company_id,
            event_type=event_type,
            confidence=self._compute_confidence(text, event_type),
            source=signal.source,
            source_url=data.get("url"),
            announced_date=self._extract_date(data),
            raw_signal_id=signal.id,
        )

        # Extract structured fields based on event type
        if event_type in (EventType.FUNDING_ROUND, EventType.RUMORED_ROUND, EventType.MEGA_ROUND):
            self._extract_funding_fields(event, text, data)

        # Mark signal as processed
        with get_session() as session:
            signal.processed = True
            session.add(event)
            session.commit()
            session.refresh(event)

        return event

    def _classify_event(self, text: str) -> str | None:
        """Classify text into an event type using keyword matching."""
        text_lower = text.lower()

        # Check for mega rounds first (highest priority)
        if self._has_keywords(text_lower, self.FUNDING_KEYWORDS):
            amount = self._extract_amount(text)
            if amount and amount >= 100_000_000:
                return EventType.MEGA_ROUND.value
            return EventType.FUNDING_ROUND.value

        if self._has_keywords(text_lower, self.ACQUISITION_KEYWORDS):
            return EventType.ACQUISITION.value

        if self._has_keywords(text_lower, self.PRODUCT_KEYWORDS):
            return EventType.PRODUCT_LAUNCH.value

        if self._has_keywords(text_lower, self.PRICING_KEYWORDS):
            return EventType.PRICING_CHANGE.value

        # Check for rumored funding
        rumor_indicators = ["rumored", "reportedly", "sources say", "might raise", "could raise"]
        if self._has_keywords(text_lower, rumor_indicators) and self._has_keywords(
            text_lower, self.FUNDING_KEYWORDS
        ):
            return EventType.RUMORED_ROUND.value

        return None

    def _compute_confidence(self, text: str, _event_type: str) -> float:
        """Compute confidence score for event classification."""
        base_confidence = 0.7

        # Higher confidence for specific sources

        # Check for rumor indicators (lower confidence)
        rumor_words = ["rumored", "reportedly", "sources", "might", "could", "allegedly"]
        if any(w in text.lower() for w in rumor_words):
            base_confidence -= 0.2

        return min(max(base_confidence, 0.3), 0.95)

    def _extract_funding_fields(self, event: IntelligenceEvent, text: str, _data: dict):
        """Extract funding-specific fields."""
        amount = self._extract_amount(text)
        if amount:
            event.amount_usd = amount

        # Extract round type
        round_types = [
            "seed",
            "series a",
            "series b",
            "series c",
            "series d",
            "series e",
            "pre-seed",
        ]
        for rt in round_types:
            if rt in text.lower():
                event.round_type = rt.title()
                break

        # Check if mega round
        if amount and amount >= 100_000_000:
            event.event_type = EventType.MEGA_ROUND.value

        # Check for rumor indicators
        rumor_words = ["rumored", "reportedly", "sources say"]
        if any(w in text.lower() for w in rumor_words):
            event.event_type = EventType.RUMORED_ROUND.value
            event.is_rumor = True

    def _extract_amount(self, text: str) -> int | None:
        """Extract funding amount from text."""
        import re

        # Match patterns like "$50M", "$50 million", "$50,000,000"
        patterns = [
            r"\$(\d+(?:\.\d+)?)\s*(?:million|m\b)",
            r"\$(\d+(?:\.\d+)?)\s*million",
            r"\$(\d+(?:\.\d+)?)\s*(?:billion|b\b)",
            r"\$(\d+(?:,\d{3})+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                amount = float(amount_str)

                if "billion" in text.lower() or "b" in text.lower():
                    amount *= 1_000_000_000
                elif "million" in text.lower() or "m" in text.lower():
                    amount *= 1_000_000

                return int(amount)

        return None

    def _extract_date(self, data: dict) -> datetime | None:
        """Extract date from signal data."""
        date_fields = ["detected_at", "published_at", "announced_date", "date"]

        for field in date_fields:
            if field in data and data[field]:
                try:
                    return datetime.fromisoformat(str(data[field]).replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

        return datetime.now(UTC)

    def _has_keywords(self, text: str, keywords: list[str]) -> bool:
        """Check if text contains any of the keywords."""
        return any(kw in text for kw in keywords)
