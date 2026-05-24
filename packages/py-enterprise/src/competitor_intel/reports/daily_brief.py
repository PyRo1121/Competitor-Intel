"""Daily intelligence brief generator with trend analysis and AI-powered insights."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import func

from competitor_intel.db.models import (
    Company,
    FundingRound,
    IntelligenceEvent,
    JobPosting,
    TeamMember,
)
from competitor_intel.db.session import get_session
from competitor_intel.settings import get_settings

logger = structlog.getLogger()


class DailyBriefReporter:
    """Generate daily intelligence briefs with trend analysis.

    Outputs:
    - JSON: Machine-readable format
    - CSV: Spreadsheet-compatible format
    - Markdown: Human-readable format with sections
    """

    def __init__(self):
        self.settings = get_settings()
        self.exports_dir = self.settings.exports_dir
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> dict[str, Any]:
        """Generate the daily brief with comprehensive analysis."""
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        with get_session() as session:
            # Events by timeframe
            events_24h = self._get_events(session, hours=24)
            events_7d = self._get_events(session, days=7)
            events_30d = self._get_events(session, days=30)

            # Trending companies (most events in 7 days)
            trending = self._get_trending_companies(session, days=7)

            # Funding activity
            funding_activity = self._get_funding_activity(session, days=30)

            # Hiring trends
            hiring_trends = self._get_hiring_trends(session, days=30)

            # Executive moves
            exec_moves = self._get_executive_moves(session, days=30)

            # Top companies by score
            top_companies = (
                session.query(Company)
                .filter(Company.score.isnot(None))
                .order_by(Company.score.desc())
                .limit(10)
                .all()
            )

            # Mega rounds in last 30 days
            mega_rounds = (
                session.query(IntelligenceEvent)
                .filter(
                    IntelligenceEvent.event_type == "mega_round",
                    IntelligenceEvent.created_at >= today - timedelta(days=30),
                )
                .order_by(IntelligenceEvent.amount_usd.desc().nulls_last())
                .all()
            )

            # Rumored rounds
            rumors = (
                session.query(IntelligenceEvent)
                .filter(
                    IntelligenceEvent.is_rumor,
                    IntelligenceEvent.created_at >= today - timedelta(days=7),
                )
                .all()
            )

        # Generate AI-powered analysis
        analysis = self._generate_analysis(events_7d, funding_activity, hiring_trends)

        return {
            "title": "Daily Intelligence Brief",
            "date": today_str,
            "generated_at": today.isoformat(),
            "summary": {
                "events_24h": len(events_24h),
                "events_7d": len(events_7d),
                "events_30d": len(events_30d),
                "trending_companies": len(trending),
                "total_funding_30d": funding_activity.get("total_amount", 0),
                "active_job_postings": hiring_trends.get("total_active", 0),
            },
            "analysis": analysis,
            "mega_rounds": [
                {
                    "company": e.company.name if e.company else "Unknown",
                    "amount_usd": e.amount_usd,
                    "round_type": e.round_type,
                    "investor": e.lead_investor,
                    "date": e.announced_date.isoformat() if e.announced_date else None,
                }
                for e in mega_rounds
            ],
            "rumors": [
                {
                    "company": e.company.name if e.company else "Unknown",
                    "round_type": e.round_type,
                    "confidence": e.confidence,
                    "source": e.source,
                }
                for e in rumors
            ],
            "trending": [
                {
                    "name": t["name"],
                    "event_count": t["event_count"],
                    "event_types": t["event_types"],
                }
                for t in trending[:10]
            ],
            "funding_activity": funding_activity,
            "hiring_trends": hiring_trends,
            "executive_moves": exec_moves,
            "top_companies": [
                {
                    "rank": i + 1,
                    "name": c.name,
                    "score": c.score,
                    "industry": c.industry,
                    "status": c.status,
                }
                for i, c in enumerate(top_companies)
            ],
            "recent_events": [
                {
                    "id": e.id,
                    "company": e.company.name if e.company else "Unknown",
                    "type": e.event_type,
                    "amount_usd": e.amount_usd,
                    "confidence": e.confidence,
                    "source": e.source,
                    "date": e.announced_date.isoformat() if e.announced_date else None,
                }
                for e in events_7d[:15]
            ],
        }

    def _get_events(self, session, hours: int = 0, days: int = 0) -> list:
        """Get events within timeframe."""
        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
        else:
            cutoff = datetime.now() - timedelta(days=days)

        return (
            session.query(IntelligenceEvent)
            .filter(IntelligenceEvent.created_at >= cutoff)
            .order_by(
                IntelligenceEvent.confidence.desc(),
                IntelligenceEvent.amount_usd.desc().nulls_last(),
            )
            .all()
        )

    def _get_trending_companies(self, session, days: int = 7) -> list[dict]:
        """Get companies with most activity in period."""
        cutoff = datetime.now() - timedelta(days=days)

        events = (
            session.query(IntelligenceEvent)
            .filter(
                IntelligenceEvent.created_at >= cutoff,
                IntelligenceEvent.company_id.isnot(None),
            )
            .all()
        )

        company_events = {}
        for e in events:
            cid = e.company_id
            if cid not in company_events:
                company_events[cid] = {"name": "", "count": 0, "types": set()}
            company_events[cid]["count"] += 1
            company_events[cid]["types"].add(e.event_type)

        # Enrich with company names
        for cid, data in company_events.items():
            company = session.get(Company, cid)
            if company:
                data["name"] = company.name

        return sorted(
            [
                {"name": d["name"], "event_count": d["count"], "event_types": list(d["types"])}
                for d in company_events.values()
            ],
            key=lambda x: x["event_count"],
            reverse=True,
        )

    def _get_funding_activity(self, session, days: int = 30) -> dict:
        """Get funding activity summary."""
        cutoff = datetime.now() - timedelta(days=days)

        rounds = session.query(FundingRound).filter(FundingRound.announced_date >= cutoff).all()

        total = sum(r.amount_usd or 0 for r in rounds)
        by_round = {}
        for r in rounds:
            rt = r.round_type or "unknown"
            if rt not in by_round:
                by_round[rt] = {"count": 0, "total": 0}
            by_round[rt]["count"] += 1
            by_round[rt]["total"] += r.amount_usd or 0

        return {
            "total_rounds": len(rounds),
            "total_amount": total,
            "by_round_type": by_round,
            "avg_round_size": total // len(rounds) if rounds else 0,
        }

    def _get_hiring_trends(self, session, days: int = 30) -> dict:
        """Get hiring activity summary."""
        cutoff = datetime.now() - timedelta(days=days)

        active = session.query(JobPosting).filter(JobPosting.is_active).count()

        new_postings = session.query(JobPosting).filter(JobPosting.posted_at >= cutoff).count()

        # Top hiring companies
        top_hiring = (
            session.query(
                Company.name,
                session.query(func.count(JobPosting.id))
                .filter(JobPosting.company_id == Company.id, JobPosting.is_active)
                .label("job_count"),
            )
            .filter(
                session.query(func.count(JobPosting.id)).filter(
                    JobPosting.company_id == Company.id, JobPosting.is_active
                )
                > 0
            )
            .order_by(
                session.query(func.count(JobPosting.id))
                .filter(JobPosting.company_id == Company.id, JobPosting.is_active)
                .desc()
            )
            .limit(10)
            .all()
        )

        return {
            "total_active": active,
            "new_postings_30d": new_postings,
            "top_hiring": [{"name": r[0], "jobs": r[1]} for r in top_hiring],
        }

    def _get_executive_moves(self, session, days: int = 30) -> list[dict]:
        """Get recent executive moves."""
        cutoff = datetime.now() - timedelta(days=days)

        moves = (
            session.query(TeamMember, Company)
            .join(Company, TeamMember.company_id == Company.id)
            .filter(TeamMember.joined_date >= cutoff)
            .order_by(TeamMember.joined_date.desc())
            .limit(10)
            .all()
        )

        return [
            {
                "name": m.name,
                "role": m.role,
                "company": c.name,
                "joined": m.joined_date.isoformat() if m.joined_date else None,
                "is_founder": m.is_founder,
            }
            for m, c in moves
        ]

    def _generate_analysis(self, events_7d, funding_activity, hiring_trends) -> dict:
        """Generate AI-powered analysis summary."""
        # Event type distribution
        type_counts = {}
        for e in events_7d:
            et = e.event_type
            type_counts[et] = type_counts.get(et, 0) + 1

        # Top event types
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)

        # Funding analysis
        funding_total = funding_activity.get("total_amount", 0)
        funding_trend = "increasing" if funding_activity.get("total_rounds", 0) > 5 else "stable"

        # Hiring analysis
        hiring_total = hiring_trends.get("total_active", 0)
        hiring_trend = (
            "aggressive" if hiring_total > 50 else "moderate" if hiring_total > 20 else "slow"
        )

        return {
            "event_distribution": dict(sorted_types[:5]),
            "funding_trend": funding_trend,
            "funding_total_30d": funding_total,
            "hiring_trend": hiring_trend,
            "key_insights": self._generate_insights(events_7d, funding_activity),
        }

    def _generate_insights(self, events, funding_activity) -> list[str]:
        """Generate key insights from data."""
        insights = []

        # Check for mega rounds
        mega = [e for e in events if e.event_type == "mega_round"]
        if mega:
            for m in mega:
                company = m.company.name if m.company else "Unknown"
                amount = f"${m.amount_usd / 1_000_000:.0f}M" if m.amount_usd else "undisclosed"
                insights.append(f"Mega round: {company} raised {amount}")

        # Check for acquisition activity
        acquisitions = [e for e in events if e.event_type == "acquisition"]
        if acquisitions:
            insights.append(f"{len(acquisitions)} acquisition(s) detected this week")

        # Check funding velocity
        rounds = funding_activity.get("total_rounds", 0)
        if rounds >= 10:
            insights.append(f"High funding velocity: {rounds} rounds in 30 days")

        if not insights:
            insights.append("No major intelligence events this period")

        return insights

    def export_json(self, brief: dict[str, Any]) -> Path:
        """Export brief as JSON."""
        date_str = brief["date"].replace("-", "")
        filepath = self.exports_dir / f"daily_brief_{date_str}.json"

        with open(filepath, "w") as f:
            json.dump(brief, f, indent=2, default=str)

        return filepath

    def export_csv(self, brief: dict[str, Any]) -> Path:
        """Export brief as CSV."""
        date_str = brief["date"].replace("-", "")
        filepath = self.exports_dir / f"daily_brief_{date_str}.csv"

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "company",
                    "event_type",
                    "amount_usd",
                    "confidence",
                    "source",
                    "date",
                    "is_rumor",
                ]
            )

            for event in brief.get("recent_events", []):
                writer.writerow(
                    [
                        event["company"],
                        event["type"],
                        event.get("amount_usd", "") or "",
                        event.get("confidence", ""),
                        event.get("source", ""),
                        event.get("date", ""),
                        "",
                    ]
                )

        return filepath

    def export_markdown(self, brief: dict[str, Any]) -> Path:
        """Export brief as Markdown with full analysis."""
        date_str = brief["date"].replace("-", "")
        filepath = self.exports_dir / f"daily_brief_{date_str}.md"

        s = brief.get("summary", {})
        a = brief.get("analysis", {})

        lines = [
            f"# {brief['title']}",
            "",
            f"**Date**: {brief['date']}",
            "",
            "## Summary",
            "",
            f"- Events (24h): {s.get('events_24h', 0)}",
            f"- Events (7d): {s.get('events_7d', 0)}",
            f"- Events (30d): {s.get('events_30d', 0)}",
            f"- Total funding (30d): ${s.get('total_funding_30d', 0):,}",
            f"- Active job postings: {s.get('active_job_postings', 0)}",
            "",
            "## Key Insights",
            "",
        ]

        for insight in a.get("key_insights", []):
            lines.append(f"- {insight}")

        lines.extend(
            [
                "",
                "## Mega Rounds",
                "",
            ]
        )

        for mr in brief.get("mega_rounds", []):
            amount = f"${mr['amount_usd'] / 1_000_000:.0f}M" if mr["amount_usd"] else "Undisclosed"
            lines.append(f"- **{mr['company']}**: {amount} ({mr.get('round_type', 'N/A')})")

        lines.extend(
            [
                "",
                "## Trending Companies",
                "",
            ]
        )

        for t in brief.get("trending", [])[:5]:
            lines.append(
                f"- **{t['name']}**: {t['event_count']} events ({', '.join(t['event_types'])})"
            )

        lines.extend(
            [
                "",
                "## Top Companies",
                "",
            ]
        )

        for c in brief.get("top_companies", [])[:5]:
            lines.append(
                f"{c['rank']}. **{c['name']}** — Score: {c['score']:.1f} ({c['industry']})"
            )

        lines.extend(
            [
                "",
                "## Recent Events",
                "",
            ]
        )

        for e in brief.get("recent_events", [])[:10]:
            amount = f" ${e['amount_usd'] / 1_000_000:.0f}M" if e.get("amount_usd") else ""
            lines.append(
                f"- **{e['company']}**: {e['type']}{amount} (confidence: {e['confidence']:.0%})"
            )

        filepath.write_text("\n".join(lines), encoding="utf-8")
        return filepath

    def generate_and_export(self) -> list[Path]:
        """Generate brief and export all formats."""
        brief = self.generate()

        return [
            self.export_json(brief),
            self.export_csv(brief),
            self.export_markdown(brief),
        ]
