"""Unit tests for funding_rumor_detector valuation parsing."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.funding_rumor_detector import parse_valuation  # noqa: E402


def test_parse_valuation_billions():
    result = parse_valuation("Anthropic closed at $3B valuation")
    assert result is not None
    usd, label = result
    assert usd == 3_000_000_000
    assert "3" in label


def test_parse_valuation_millions():
    result = parse_valuation("raised $40 million")
    assert result is not None
    usd, _ = result
    assert usd == 40_000_000


def test_parse_valuation_no_match():
    assert parse_valuation("no numbers here") is None
