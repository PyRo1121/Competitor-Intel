"""Core type definitions and enums."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SignalType(StrEnum):
    """Types of raw signals."""

    FUNDING_NEWS = "funding_news"
    PRODUCT_UPDATE = "product_update"
    SOCIAL_MOMENTUM = "social_momentum"
    GITHUB_ACTIVITY = "github_activity"
    WEBSITE_CHANGE = "website_change"
    SEC_FILING = "sec_filing"
    RSS_ITEM = "rss_item"
    UNKNOWN = "unknown"


class EventType(StrEnum):
    """Types of intelligence events."""

    FUNDING_ROUND = "funding_round"
    ACQUISITION = "acquisition"
    PARTNERSHIP = "partnership"
    PRODUCT_LAUNCH = "product_launch"
    PRICING_CHANGE = "pricing_change"
    RUMORED_ROUND = "rumored_round"
    MEGA_ROUND = "mega_round"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """Signal sources."""

    TECHCRUNCH = "techcrunch"
    RSS = "rss"
    GITHUB = "github"
    WEBSITE = "website"
    SEC_EDGAR = "sec_edgar"
    X = "x"
    MANUAL = "manual"


class CollectorStatus(StrEnum):
    """Collector run status."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_IMPLEMENTED = "not_implemented"


class CollectorResult(BaseModel):
    """Result from a collector run."""

    collector_name: str
    status: CollectorStatus
    signals_collected: int = 0
    signals_stored: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CollectorMetrics(BaseModel):
    """Metrics for collector performance tracking."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limit_hits: int = 0
    avg_response_time_ms: float = 0.0
    total_bytes_downloaded: int = 0
