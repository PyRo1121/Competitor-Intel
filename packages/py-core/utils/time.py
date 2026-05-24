"""Timezone-aware datetime helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Current UTC time (replaces deprecated ``datetime.utcnow()``)."""
    return datetime.now(UTC)
