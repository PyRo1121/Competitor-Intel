"""Knowledge graph — maps relationships between entities for intelligence analysis."""

from collections import defaultdict
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select

from competitor_intel.db.models import (
    Company,
    CompetitorRelationship,
    FundingRound,
    TeamMember,
    TechnologyStack,
)
from competitor_intel.db.session import get_session

logger = structlog.getLogger()


class KnowledgeGraph:
    """Builds and queries a knowledge graph of company relationships.

    Graph nodes:
    - Companies
    - Investors
    - Founders/Executives
    - Technologies

    Graph edges:
    - company ↔ competitor (competes with)
    - company ← investor (funded by)
    - company ← founder (founded by)
    - company → technology (uses)
    - company ↔ company (shared investor)
    """

    def get_company_graph(self, company_id: int) -> dict:
        """Get the full knowledge graph for a company."""
        with get_session() as session:
            company = session.get(Company, company_id)
            if not company:
                return {"error": "Company not found"}

            return {
                "company": self._get_company_info(session, company_id),
                "competitors": self._get_competitors(session, company_id),
                "investors": self._get_investors(session, company_id),
                "team": self._get_team(session, company_id),
                "tech_stack": self._get_tech_stack(session, company_id),
                "shared_investors": self._get_shared_investors(session, company_id),
                "competitive_landscape": self._get_competitive_landscape(session, company_id),
            }

    def get_investor_graph(self, investor_name: str) -> dict:
        """Get all companies funded by an investor."""
        with get_session() as session:
            # Search funding rounds for this investor
            rounds = (
                session.execute(
                    select(FundingRound).where(FundingRound.lead_investor.contains(investor_name))
                )
                .scalars()
                .all()
            )

            companies = []
            total_invested = 0
            for r in rounds:
                company = session.get(Company, r.company_id)
                if company:
                    companies.append(
                        {
                            "name": company.name,
                            "round_type": r.round_type,
                            "amount_usd": r.amount_usd,
                            "announced_date": r.announced_date.isoformat()
                            if r.announced_date
                            else None,
                        }
                    )
                    total_invested += r.amount_usd or 0

            return {
                "investor": investor_name,
                "portfolio": companies,
                "portfolio_count": len(companies),
                "total_invested_usd": total_invested,
            }

    def get_tech_trends(self, category: str | None = None) -> dict:
        """Get technology adoption trends across tracked companies."""
        with get_session() as session:
            query = select(
                TechnologyStack.technology,
                TechnologyStack.category,
                func.count(TechnologyStack.id).label("adoption_count"),
            ).group_by(TechnologyStack.technology, TechnologyStack.category)

            if category:
                query = query.where(TechnologyStack.category == category)

            query = query.order_by(func.count(TechnologyStack.id).desc())

            results = session.execute(query).all()

            return {
                "category": category or "all",
                "technologies": [
                    {
                        "name": r.technology,
                        "category": r.category,
                        "adoption_count": r.adoption_count,
                    }
                    for r in results
                ],
            }

    def find_companies_by_tech(self, technology: str) -> list[dict]:
        """Find all companies using a specific technology."""
        with get_session() as session:
            stacks = (
                session.execute(
                    select(TechnologyStack).where(
                        TechnologyStack.technology.ilike(f"%{technology}%")
                    )
                )
                .scalars()
                .all()
            )

            companies = []
            for stack in stacks:
                company = session.get(Company, stack.company_id)
                if company:
                    companies.append(
                        {
                            "name": company.name,
                            "technology": stack.technology,
                            "category": stack.category,
                            "confidence": stack.confidence,
                        }
                    )

            return companies

    def _get_company_info(self, session, company_id: int) -> dict:
        """Get basic company information."""
        company = session.get(Company, company_id)
        return {
            "id": company.id,
            "name": company.name,
            "slug": company.slug,
            "industry": company.industry,
            "status": company.status,
            "score": company.score,
        }

    def _get_competitors(self, session, company_id: int) -> list[dict]:
        """Get direct competitors."""
        rels = (
            session.execute(
                select(CompetitorRelationship).where(
                    CompetitorRelationship.company_id == company_id
                )
            )
            .scalars()
            .all()
        )

        competitors = []
        for rel in rels:
            competitor = session.get(Company, rel.competitor_id)
            if competitor:
                competitors.append(
                    {
                        "name": competitor.name,
                        "relationship_type": rel.relationship_type,
                        "overlap_areas": rel.overlap_areas,
                        "confidence": rel.confidence,
                    }
                )

        return competitors

    def _get_investors(self, session, company_id: int) -> list[dict]:
        """Get all investors for a company."""
        rounds = (
            session.execute(
                select(FundingRound)
                .where(FundingRound.company_id == company_id)
                .order_by(FundingRound.announced_date.desc())
            )
            .scalars()
            .all()
        )

        investors = []
        for r in rounds:
            if r.lead_investor:
                investors.append(
                    {
                        "name": r.lead_investor,
                        "role": "lead",
                        "round_type": r.round_type,
                        "amount_usd": r.amount_usd,
                    }
                )
            if r.co_investors:
                co_investors = r.co_investors if isinstance(r.co_investors, list) else []
                for inv in co_investors:
                    investors.append(
                        {
                            "name": inv,
                            "role": "co-investor",
                            "round_type": r.round_type,
                        }
                    )

        return investors

    def _get_team(self, session, company_id: int) -> dict:
        """Get team information."""
        founders = (
            session.execute(
                select(TeamMember).where(
                    TeamMember.company_id == company_id,
                    TeamMember.is_founder,
                )
            )
            .scalars()
            .all()
        )

        recent_hires = (
            session.execute(
                select(TeamMember).where(
                    TeamMember.company_id == company_id,
                    TeamMember.joined_date >= datetime.now(UTC).replace(month=1, day=1),
                    TeamMember.left_date.is_(None),
                )
            )
            .scalars()
            .all()
        )

        return {
            "founders": [{"name": f.name, "role": f.role} for f in founders],
            "recent_hires": [{"name": h.name, "role": h.role} for h in recent_hires[:5]],
        }

    def _get_tech_stack(self, session, company_id: int) -> list[dict]:
        """Get technology stack for a company."""
        stacks = (
            session.execute(
                select(TechnologyStack)
                .where(TechnologyStack.company_id == company_id)
                .order_by(TechnologyStack.category)
            )
            .scalars()
            .all()
        )

        by_category = defaultdict(list)
        for s in stacks:
            by_category[s.category].append(
                {
                    "name": s.technology,
                    "confidence": s.confidence,
                }
            )

        return [{"category": k, "technologies": v} for k, v in by_category.items()]

    def _get_shared_investors(self, session, company_id: int) -> list[dict]:
        """Find companies that share investors (potential competitors)."""
        my_investors = set()
        rounds = (
            session.execute(select(FundingRound).where(FundingRound.company_id == company_id))
            .scalars()
            .all()
        )

        for r in rounds:
            if r.lead_investor:
                my_investors.add(r.lead_investor)

        if not my_investors:
            return []

        # Find other companies with same investors
        all_rounds = session.execute(select(FundingRound)).scalars().all()
        shared = []

        for r in all_rounds:
            if r.company_id == company_id:
                continue
            if r.lead_investor in my_investors:
                company = session.get(Company, r.company_id)
                if company:
                    shared.append(
                        {
                            "company": company.name,
                            "shared_investor": r.lead_investor,
                            "round_type": r.round_type,
                        }
                    )

        return shared[:10]

    def _get_competitive_landscape(self, session, company_id: int) -> dict:
        """Get competitive landscape analysis."""
        company = session.get(Company, company_id)

        # Find companies in same industry
        peers = (
            session.execute(
                select(Company).where(
                    Company.industry == company.industry,
                    Company.id != company_id,
                    Company.status == "active",
                )
            )
            .scalars()
            .all()
        )

        return {
            "industry": company.industry,
            "peer_count": len(peers),
            "peers": [
                {"name": p.name, "score": p.score, "status": p.status}
                for p in sorted(peers, key=lambda x: x.score or 0, reverse=True)[:10]
            ],
        }
