"""Company scoring engine — computes intelligence scores for tracked companies."""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select

from competitor_intel.db.models import (
    Company,
    CompanyDetails,
    FundingRound,
    GitHubMetrics,
    IntelligenceEvent,
    JobPosting,
    TeamMember,
    XActivity,
)
from competitor_intel.db.session import get_session

logger = structlog.getLogger()


class ScoringEngine:
    """Computes composite intelligence scores for companies.

    Score components (0-100):
    - Funding momentum (25%): Recent funding, valuation growth
    - Engineering velocity (20%): GitHub activity, commits, contributors
    - Social momentum (15%): X/Twitter engagement, sentiment
    - Hiring velocity (15%): Job postings, key hires
    - Market presence (15%): Product launches, customer signals
    - Team strength (10%): Founders, key executives
    """

    def score_company(self, company_id: int) -> dict:
        """Compute comprehensive score for a company."""
        with get_session() as session:
            company = session.get(Company, company_id)
            if not company:
                return {"error": "Company not found"}

            scores = {
                "company_id": company_id,
                "company_name": company.name,
                "funding_momentum": self._score_funding(session, company_id),
                "engineering_velocity": self._score_engineering(session, company_id),
                "social_momentum": self._score_social(session, company_id),
                "hiring_velocity": self._score_hiring(session, company_id),
                "market_presence": self._score_market(session, company_id),
                "team_strength": self._score_team(session, company_id),
                "computed_at": datetime.now(UTC).isoformat(),
            }

            # Weighted composite
            scores["composite_score"] = round(
                scores["funding_momentum"] * 0.25
                + scores["engineering_velocity"] * 0.20
                + scores["social_momentum"] * 0.15
                + scores["hiring_velocity"] * 0.15
                + scores["market_presence"] * 0.15
                + scores["team_strength"] * 0.10,
                1,
            )

            # Update company score
            company.score = scores["composite_score"]
            company.last_updated_at = datetime.now(UTC)
            session.commit()

            logger.info(
                "company_scored",
                company=company.name,
                score=scores["composite_score"],
            )

            return scores

    def score_all_companies(self) -> list[dict]:
        """Score all tracked companies and return ranked list."""
        with get_session() as session:
            companies = session.execute(select(Company)).scalars().all()

        results = []
        for company in companies:
            try:
                score = self.score_company(company.id)
                results.append(score)
            except Exception as e:
                logger.error("scoring_error", company=company.name, error=str(e))

        # Sort by composite score descending
        results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
        return results

    def _score_funding(self, session, company_id: int) -> float:
        """Score funding momentum (0-100)."""
        cutoff = datetime.now(UTC) - timedelta(days=365)

        recent_rounds = (
            session.execute(
                select(FundingRound).where(
                    FundingRound.company_id == company_id,
                    FundingRound.announced_date >= cutoff,
                )
            )
            .scalars()
            .all()
        )

        if not recent_rounds:
            return 20.0  # Base score

        total_raised = sum(r.amount_usd or 0 for r in recent_rounds)
        round_count = len(recent_rounds)

        # Score based on amount and recency
        amount_score = min(total_raised / 100_000_000 * 50, 50)  # Up to 50 points for $100M+
        frequency_score = min(round_count * 15, 30)  # Up to 30 points for 2+ rounds
        base = 20.0

        return min(base + amount_score + frequency_score, 100.0)

    def _score_engineering(self, session, company_id: int) -> float:
        """Score engineering velocity (0-100)."""
        metrics = session.execute(
            select(GitHubMetrics)
            .where(GitHubMetrics.company_id == company_id)
            .order_by(GitHubMetrics.extracted_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not metrics:
            return 30.0  # Base score for having no GitHub data

        commits_score = min((metrics.commits_last_30d or 0) * 2, 40)
        contributors_score = min((metrics.active_contributors_30d or 0) * 5, 30)
        star_growth_score = min((metrics.star_growth_30d or 0) * 0.5, 20)
        base = 10.0

        return min(base + commits_score + contributors_score + star_growth_score, 100.0)

    def _score_social(self, session, company_id: int) -> float:
        """Score social momentum (0-100)."""
        activity = session.execute(
            select(XActivity)
            .where(XActivity.company_id == company_id)
            .order_by(XActivity.extracted_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not activity:
            return 25.0

        engagement_score = min((activity.avg_likes or 0) * 0.1, 40)
        volume_score = min((activity.post_count or 0) * 2, 30)
        sentiment_score = (activity.sentiment_positive or 0.5) * 20
        base = 10.0

        return min(base + engagement_score + volume_score + sentiment_score, 100.0)

    def _score_hiring(self, session, company_id: int) -> float:
        """Score hiring velocity (0-100)."""
        active_jobs = session.execute(
            select(func.count(JobPosting.id)).where(
                JobPosting.company_id == company_id,
                JobPosting.is_active,
            )
        ).scalar_one()

        recent_hires = session.execute(
            select(func.count(TeamMember.id)).where(
                TeamMember.company_id == company_id,
                TeamMember.joined_date >= datetime.now(UTC) - timedelta(days=90),
                TeamMember.left_date.is_(None),
            )
        ).scalar_one()

        job_score = min(active_jobs * 5, 50)
        hire_score = min(recent_hires * 10, 40)
        base = 10.0

        return min(base + job_score + hire_score, 100.0)

    def _score_market(self, session, company_id: int) -> float:
        """Score market presence (0-100)."""
        recent_events = session.execute(
            select(func.count(IntelligenceEvent.id)).where(
                IntelligenceEvent.company_id == company_id,
                IntelligenceEvent.created_at >= datetime.now(UTC) - timedelta(days=30),
            )
        ).scalar_one()

        event_score = min(recent_events * 5, 60)
        base = 40.0  # Base score for being tracked

        return min(base + event_score, 100.0)

    def _score_team(self, session, company_id: int) -> float:
        """Score team strength (0-100)."""
        founders = session.execute(
            select(func.count(TeamMember.id)).where(
                TeamMember.company_id == company_id,
                TeamMember.is_founder,
            )
        ).scalar_one()

        total_team = session.execute(
            select(func.count(TeamMember.id)).where(
                TeamMember.company_id == company_id,
                TeamMember.left_date.is_(None),
            )
        ).scalar_one()

        details = session.execute(
            select(CompanyDetails).where(CompanyDetails.company_id == company_id)
        ).scalar_one_or_none()

        founder_score = min(founders * 20, 40)
        team_score = min(total_team * 5, 40)
        enrichment_score = 20.0 if details and details.team_size else 0.0

        return min(founder_score + team_score + enrichment_score, 100.0)
