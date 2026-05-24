"""Discord webhook reporter for daily intelligence briefs."""

from datetime import datetime
from typing import Any

import httpx
import structlog

from competitor_intel.db.models import Company, FundingEvent, IntelligenceEvent
from competitor_intel.db.session import get_session
from competitor_intel.settings import get_settings

logger = structlog.get_logger()


class DiscordReporter:
    """Generate and post intelligence briefs to Discord."""

    def __init__(self):
        self.settings = get_settings()

    def generate_brief(self) -> dict[str, Any]:
        """Generate a daily intelligence brief."""
        with get_session() as session:
            # Top companies by score
            top_companies = (
                session.query(Company)
                .filter(Company.score.isnot(None))
                .order_by(Company.score.desc())
                .limit(5)
                .all()
            )

            # Recent funding events
            recent_funding = (
                session.query(FundingEvent)
                .order_by(FundingEvent.announced_date.desc())
                .limit(5)
                .all()
            )

            # Recent intelligence events
            recent_events = (
                session.query(IntelligenceEvent)
                .order_by(IntelligenceEvent.created_at.desc())
                .limit(5)
                .all()
            )

        embed = {
            "title": "Competitor Intelligence Daily Brief",
            "description": f"**{datetime.now().strftime('%B %d, %Y')}**",
            "color": 0x5865F2,
            "fields": [],
            "footer": {"text": "Hermes Intelligence"},
        }

        # Top companies
        if top_companies:
            top_text = "\n".join([f"• **{c.name}** — Score: {c.score:.2f}" for c in top_companies])
            embed["fields"].append(
                {
                    "name": "🏆 Top Companies",
                    "value": top_text,
                    "inline": False,
                }
            )

        # Recent funding
        if recent_funding:
            funding_text = "\n".join(
                [
                    f"• **{f.company.name if f.company else 'Unknown'}** — "
                    f"{f.round_type} ${f.amount_usd:,}"
                    for f in recent_funding
                ]
            )
            embed["fields"].append(
                {
                    "name": "💰 Recent Funding",
                    "value": funding_text,
                    "inline": False,
                }
            )

        # Intelligence events
        if recent_events:
            events_text = "\n".join(
                [
                    f"• **{e.company.name if e.company else 'Unknown'}** — {e.event_type}"
                    for e in recent_events
                ]
            )
            embed["fields"].append(
                {
                    "name": "📊 Intelligence Events",
                    "value": events_text,
                    "inline": False,
                }
            )

        return embed

    async def post(self, embed: dict[str, Any] | None = None) -> bool:
        """Post brief to Discord webhook."""
        if embed is None:
            embed = self.generate_brief()

        if not self.settings.discord.webhook_url:
            logger.warning("discord_webhook_not_configured")
            return False

        try:
            async with httpx.AsyncClient(timeout=self.settings.discord.timeout) as client:
                response = await client.post(
                    self.settings.discord.webhook_url,
                    json={"embeds": [embed]},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            logger.info("discord_post_success")
            return True

        except Exception as e:
            logger.error("discord_post_failed", error=str(e))
            return False

    def preview(self) -> str:
        """Generate a text preview of the brief."""
        embed = self.generate_brief()

        lines = [
            f"# {embed['title']}",
            f"\n{embed['description']}",
            "",
        ]

        for field in embed["fields"]:
            lines.append(f"## {field['name']}")
            lines.append(field["value"])
            lines.append("")

        return "\n".join(lines)
