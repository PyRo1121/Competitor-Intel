"""SQLAlchemy 2.0 models for competitor intelligence."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class."""


class Company(Base):
    """Tracked competitor company."""

    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_companies_slug"),
        UniqueConstraint("name", name="uq_companies_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    x_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    github_org: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), default="AI/Productivity")
    status: Mapped[str] = mapped_column(String(50), default="active")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    first_tracked_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    funding_events: Mapped[list["FundingEvent"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    raw_signals: Mapped[list["RawSignal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    intelligence_events: Mapped[list["IntelligenceEvent"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    product_updates: Mapped[list["ProductUpdate"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    x_posts: Mapped[list["XPost"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    github_activity: Mapped[list["GitHubActivity"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    rss_items: Mapped[list["RSSItem"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    company_details: Mapped[Optional["CompanyDetails"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    funding_rounds: Mapped[list["FundingRound"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    team_members: Mapped[list["TeamMember"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    github_metrics: Mapped[list["GitHubMetrics"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    x_activity: Mapped[list["XActivity"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    competitive_positioning: Mapped[list["CompetitivePositioning"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    job_postings: Mapped[list["JobPosting"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    competitor_relationships_as_company: Mapped[list["CompetitorRelationship"]] = relationship(
        foreign_keys="CompetitorRelationship.company_id",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    competitor_relationships_as_competitor: Mapped[list["CompetitorRelationship"]] = relationship(
        foreign_keys="CompetitorRelationship.competitor_id",
        back_populates="competitor",
        cascade="all, delete-orphan",
    )
    technology_stack: Mapped[list["TechnologyStack"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    website_snapshots: Mapped[list["WebsiteSnapshot"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    customer_signals: Mapped[list["CustomerSignal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    ip_assets: Mapped[list["IPAsset"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    revenue_signals: Mapped[list["RevenueSignal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    market_signals: Mapped[list["MarketSignal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    executive_moves: Mapped[list["ExecutiveMove"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class FundingEvent(Base):
    """Funding round or investment event."""

    __tablename__ = "funding_events"
    __table_args__ = (UniqueConstraint("source_url", name="uq_funding_source_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    round_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valuation_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    announced_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    investors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="unknown")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="funding_events")


class RawSignal(Base):
    """Raw collected signal from any source."""

    __tablename__ = "raw_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    semantic_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    company: Mapped[Optional["Company"]] = relationship(back_populates="raw_signals")


class IntelligenceEvent(Base):
    """Extracted intelligence event from raw signals."""

    __tablename__ = "intelligence_events"
    __table_args__ = (UniqueConstraint("source_url", name="uq_intelligence_source_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    round_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valuation_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_investor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_rumor: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    announced_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="unknown")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_signal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("raw_signals.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="intelligence_events")


class WebsiteSnapshot(Base):
    """Website content snapshot for change detection."""

    __tablename__ = "website_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    website: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    changed_elements: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="website_snapshots")


class ProductUpdate(Base):
    """Product/feature updates from companies."""

    __tablename__ = "product_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    update_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    announced_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    semantic_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="product_updates")


class XPost(Base):
    """X/Twitter posts from tracked companies."""

    __tablename__ = "x_posts"
    __table_args__ = (UniqueConstraint("post_id", name="uq_x_post_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    post_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    retweets: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_founder_post: Mapped[bool] = mapped_column(Boolean, default=False)
    sentiment: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="x_posts")


class GitHubActivity(Base):
    """GitHub activity events for tracked companies."""

    __tablename__ = "github_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stars_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="github_activity")


class RSSItem(Base):
    """RSS/blog items from company feeds."""

    __tablename__ = "rss_items"
    __table_args__ = (UniqueConstraint("url", name="uq_rss_item_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    feed_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    semantic_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped[Optional["Company"]] = relationship(back_populates="rss_items")


class CompanyDetails(Base):
    """Deep enrichment data for companies."""

    __tablename__ = "company_details"
    __table_args__ = (UniqueConstraint("company_id", name="uq_company_details_company"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headquarters: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_size_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    business_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tech_stack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description_long: Mapped[str | None] = mapped_column(Text, nullable=True)
    traction: Mapped[str | None] = mapped_column(Text, nullable=True)
    moat: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    company: Mapped["Company"] = relationship(back_populates="company_details")


class FundingRound(Base):
    """Detailed funding round history."""

    __tablename__ = "funding_rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    round_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valuation_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    announced_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lead_investor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    co_investors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="funding_rounds")


class TeamMember(Base):
    """Team members (key hires, departures, founders)."""

    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_founder: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    left_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="team_members")


class Product(Base):
    """Products and features offered by companies."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pricing_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    launch_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="products")


class GitHubMetrics(Base):
    """Deep GitHub metrics for company repos."""

    __tablename__ = "github_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    repo_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_commits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commits_last_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contributor_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_contributors_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    languages_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    release_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_release_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issue_resolution_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    star_growth_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fork_growth_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="github_metrics")


class XActivity(Base):
    """X/Twitter activity analytics for companies."""

    __tablename__ = "x_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    post_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_retweets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_replies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sentiment_positive: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_neutral: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_negative: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_topics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    engagement_velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="x_activity")


class CompetitivePositioning(Base):
    """Competitive positioning scores and analysis."""

    __tablename__ = "competitive_positioning"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(100), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comparison_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="competitive_positioning")


class JobPosting(Base):
    """Job postings (hiring velocity = growth signal)."""

    __tablename__ = "job_postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salary_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="job_postings")


class CompetitorRelationship(Base):
    """Competitor relationships (who competes with whom)."""

    __tablename__ = "competitor_relationships"
    __table_args__ = (UniqueConstraint("company_id", "competitor_id", name="uq_competitor_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    competitor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(50), default="direct")
    overlap_areas: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    market_share_estimate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(
        foreign_keys=[company_id], back_populates="competitor_relationships_as_company"
    )
    competitor: Mapped["Company"] = relationship(
        foreign_keys=[competitor_id], back_populates="competitor_relationships_as_competitor"
    )


class TechnologyStack(Base):
    """Technology stack detections for companies."""

    __tablename__ = "technology_stack"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    technology: Mapped[str] = mapped_column(String(255), nullable=False)
    detection_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    first_detected: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    last_confirmed: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="technology_stack")


class CustomerSignal(Base):
    """Customer signals (wins, case studies, testimonials, churn)."""

    __tablename__ = "customer_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signal_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="customer_signals")


class IPAsset(Base):
    """Patents and trademarks (IP intelligence)."""

    __tablename__ = "ip_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filing_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    filing_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    company: Mapped["Company"] = relationship(back_populates="ip_assets")


class RevenueSignal(Base):
    """Revenue and pricing signals (new pricing tiers, revenue estimates)."""

    __tablename__ = "revenue_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pricing_change: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="unknown")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="revenue_signals")


class MarketSignal(Base):
    """Market signals (market share estimates, TAM analysis, growth rates)."""

    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    market_share_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    tam_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    growth_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="unknown")
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="market_signals")


class ExecutiveMove(Base):
    """Executive hires, departures, and role changes."""

    __tablename__ = "executive_moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    executive_name: Mapped[str] = mapped_column(String(255), nullable=False)
    move_type: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    previous_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    announced_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="unknown")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    company: Mapped["Company"] = relationship(back_populates="executive_moves")


class AlertRule(Base):
    """Alert rules for real-time notifications."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    event_types: Mapped[dict] = mapped_column(JSON, nullable=False)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    channel: Mapped[str] = mapped_column(String(50), default="discord")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AlertSent(Base):
    """Track sent alerts to avoid duplicates."""

    __tablename__ = "alerts_sent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("intelligence_events.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class Report(Base):
    """Generated intelligence reports."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_date())
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    companies_changed: Mapped[int] = mapped_column(Integer, default=0)
    high_signal_count: Mapped[int] = mapped_column(Integer, default=0)
    discord_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    obsidian_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
