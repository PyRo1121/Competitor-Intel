"""Real-time alert engine — processes signals and fires alerts based on rules."""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from competitor_intel.db.models import AlertRule, AlertSent, IntelligenceEvent
from competitor_intel.db.session import get_session

logger = structlog.getLogger()


class AlertEngine:
    """Processes intelligence events and fires alerts based on configured rules.

    Alert triggers:
    - Funding rounds above threshold
    - Key executive hires/departures
    - Product launches from competitors
    - Mega rounds ($100M+)
    - Acquisition announcements
    - Rumored funding rounds
    - High-velocity hiring
    """

    def process_event(self, event: IntelligenceEvent) -> list[dict]:
        """Process a single intelligence event and fire matching alerts."""
        alerts_fired = []

        with get_session() as session:
            rules = session.execute(select(AlertRule).where(AlertRule.enabled)).scalars().all()

            for rule in rules:
                if not self._rule_matches(rule, event):
                    continue

                if self._already_alerted(session, event.id, rule.channel):
                    continue

                alert = self._fire_alert(rule, event)
                alerts_fired.append(alert)

                # Record alert sent
                sent = AlertSent(event_id=event.id, channel=rule.channel)
                session.add(sent)

            session.commit()

        return alerts_fired

    def process_unalerted_events(self, limit: int = 100) -> list[dict]:
        """Process all events that haven't been alerted yet."""
        with get_session() as session:
            alerted_ids = session.execute(select(AlertSent.event_id)).scalars().all()

            query = (
                select(IntelligenceEvent).order_by(IntelligenceEvent.created_at.desc()).limit(limit)
            )
            if alerted_ids:
                query = query.where(IntelligenceEvent.id.notin_(alerted_ids))

            events = session.execute(query).scalars().all()

        all_alerts = []
        for event in events:
            alerts = self.process_event(event)
            all_alerts.extend(alerts)

        return all_alerts

    def _rule_matches(self, rule: AlertRule, event: IntelligenceEvent) -> bool:
        """Check if an event matches an alert rule."""
        if event.confidence < rule.min_confidence:
            return False

        if rule.company_id and event.company_id != rule.company_id:
            return False

        event_types = rule.event_types
        if isinstance(event_types, dict):
            event_types = event_types.get("types", [])

        return event.event_type in event_types

    def _already_alerted(self, session, event_id: int, channel: str) -> bool:
        """Check if this event was already alerted on this channel."""
        existing = session.execute(
            select(AlertSent).where(
                AlertSent.event_id == event_id,
                AlertSent.channel == channel,
            )
        ).scalar_one_or_none()

        return existing is not None

    def _fire_alert(self, rule: AlertRule, event: IntelligenceEvent) -> dict:
        """Fire an alert and return alert details."""
        alert = {
            "rule_name": rule.name,
            "channel": rule.channel,
            "event_type": event.event_type,
            "company_id": event.company_id,
            "confidence": event.confidence,
            "fired_at": datetime.now(UTC).isoformat(),
            "message": self._format_alert_message(rule, event),
        }

        logger.info(
            "alert_fired",
            rule=rule.name,
            channel=rule.channel,
            event_type=event.event_type,
            company_id=event.company_id,
        )

        return alert

    def _format_alert_message(self, _rule: AlertRule, event: IntelligenceEvent) -> str:
        """Format alert message for the channel."""
        event_type_labels = {
            "funding_round": "Funding Round",
            "acquisition": "Acquisition",
            "partnership": "Partnership",
            "product_launch": "Product Launch",
            "pricing_change": "Pricing Change",
            "rumored_round": "Rumored Funding",
            "mega_round": "Mega Round ($100M+)",
        }

        label = event_type_labels.get(event.event_type, event.event_type)

        parts = [f"ALERT: {label}"]

        if event.amount_usd:
            amount = f"${event.amount_usd / 1_000_000:.0f}M"
            parts.append(f"Amount: {amount}")

        if event.lead_investor:
            parts.append(f"Lead: {event.lead_investor}")

        if event.round_type:
            parts.append(f"Round: {event.round_type}")

        parts.append(f"Confidence: {event.confidence:.0%}")

        return " | ".join(parts)

    def create_rule(
        self,
        name: str,
        event_types: list[str],
        channel: str = "discord",
        company_id: int | None = None,
        min_confidence: float = 0.5,
    ) -> AlertRule:
        """Create a new alert rule."""
        rule = AlertRule(
            name=name,
            company_id=company_id,
            event_types={"types": event_types},
            min_confidence=min_confidence,
            channel=channel,
            enabled=True,
        )

        with get_session() as session:
            session.add(rule)
            session.commit()
            session.refresh(rule)

        logger.info("alert_rule_created", rule_name=name)
        return rule
