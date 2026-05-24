"""Alert engine rule matching."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from alerts.alert_engine import (  # noqa: E402
    _parse_event_types,
    classify_event_type,
    match_db_rule,
)


def test_parse_event_types_api_shape():
    types = _parse_event_types('{"types": ["Funding Round", "Acquisition"]}')
    assert types == ["Funding Round", "Acquisition"]


def test_classify_funding_keywords():
    assert (
        classify_event_type({"event_type": "news", "text": "raised series a funding"}) == "funding"
    )


def test_match_db_rule_company_filter():
    rule = {
        "name": "acme-only",
        "company_id": 1,
        "event_types": ["Funding Round"],
        "min_confidence": 0.5,
        "channel": "discord",
    }
    assert match_db_rule(
        rule,
        company_id=1,
        event_type="Funding Round",
        confidence=0.8,
        amount_usd=5_000_000,
    )
    assert not match_db_rule(
        rule,
        company_id=2,
        event_type="Funding Round",
        confidence=0.8,
        amount_usd=5_000_000,
    )
