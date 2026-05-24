"""CI_STRICT_PIPELINE guards legacy funding writers (6-A04)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.big_deals_collector import run as big_deals_run  # noqa: E402
from collectors.pipeline_guard import (  # noqa: E402
    strict_pipeline_blocks_funding_events,
    strict_pipeline_blocks_legacy_events,
)


def test_strict_pipeline_blocks_by_default(monkeypatch):
    monkeypatch.delenv("CI_STRICT_PIPELINE", raising=False)
    assert strict_pipeline_blocks_legacy_events("test") is False


def test_strict_pipeline_blocks_when_set(monkeypatch):
    monkeypatch.setenv("CI_STRICT_PIPELINE", "1")
    assert strict_pipeline_blocks_legacy_events("test") is True


def test_big_deals_noop_under_strict_pipeline(monkeypatch):
    monkeypatch.setenv("CI_STRICT_PIPELINE", "1")
    assert big_deals_run() == 0


def test_strict_pipeline_blocks_funding_events_writes(monkeypatch):
    monkeypatch.setenv("CI_STRICT_PIPELINE", "1")
    assert strict_pipeline_blocks_funding_events("test") is True
