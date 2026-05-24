"""Env guards for legacy collectors that bypass signal_processor + rollups."""

from __future__ import annotations

import logging
import os

_LEGACY_EVENT_MSG = (
    "%s: CI_STRICT_PIPELINE=1 — direct intelligence_events writes disabled; "
    "use signal_processor + funding_rollup (daily registry path)."
)


def strict_pipeline_blocks_legacy_events(component: str) -> bool:
    """When True, caller should skip legacy event inserts (CLI/on-demand only)."""
    if os.environ.get("CI_STRICT_PIPELINE", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return False
    logging.getLogger(component).warning(_LEGACY_EVENT_MSG, component)
    return True


_FUNDING_EVENTS_MSG = (
    "%s: CI_STRICT_PIPELINE=1 — funding_events writes disabled; "
    "use signal_processor + funding_rollup."
)


def strict_pipeline_blocks_funding_events(component: str) -> bool:
    """When True, caller should skip legacy funding_events table inserts."""
    if os.environ.get("CI_STRICT_PIPELINE", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return False
    logging.getLogger(component).warning(_FUNDING_EVENTS_MSG, component)
    return True
