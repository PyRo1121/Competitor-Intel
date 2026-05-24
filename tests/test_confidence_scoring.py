"""Unit tests for honest confidence scoring (anti-gaming)."""

from __future__ import annotations

import pytest
from collectors.enrichment.confidence_scoring import (
    CONFIDENCE_WEIGHTS,
    WEIGHTS_VERSION,
    compute_corroboration,
)


def _claim(
    domain: str,
    weight: float,
    *,
    official: bool = False,
    rumor: bool = False,
    amount: int | None = 10_000_000,
    lead: str | None = None,
    round_type: str | None = "Series A",
    announced_date: str | None = "2025-01-15",
    extraction: float | None = 0.85,
    tier: str = "tier1",
):
    return {
        "source_url": f"https://{domain}/article",
        "source": domain.split(".")[0],
        "source_weight": weight,
        "source_tier": tier,
        "is_official": 1 if official else 0,
        "is_rumor": 1 if rumor else 0,
        "amount_usd": amount,
        "lead_investor": lead,
        "round_type": round_type,
        "announced_date": announced_date,
        "extraction_confidence": extraction,
    }


def test_weights_version_is_v3():
    assert WEIGHTS_VERSION == 3


def test_single_press_outlet_capped_below_building():
    score, meta = compute_corroboration([_claim("techcrunch.com", 0.78)])
    assert meta["unique_domains"] == 1
    assert score <= 0.40


def test_syndication_cannot_fake_diversity():
    claims = [_claim("techcrunch.com", 0.78) for _ in range(6)]
    score, meta = compute_corroboration(claims)
    assert meta["unique_domains"] == 1
    assert score < 0.45


def test_two_independent_domains_reaches_building():
    score, _ = compute_corroboration(
        [
            _claim("techcrunch.com", 0.78, announced_date="2025-01-10"),
            _claim("reuters.com", 0.78, announced_date="2025-01-12"),
        ]
    )
    assert score >= 0.45


def test_strong_requires_multiple_domains():
    score, meta = compute_corroboration(
        [
            _claim(
                "techcrunch.com",
                0.78,
                lead="Sequoia",
                announced_date="2025-01-01",
            ),
            _claim(
                "reuters.com",
                0.78,
                lead="Sequoia",
                announced_date="2025-01-08",
            ),
            _claim(
                "bloomberg.com",
                0.78,
                lead="Sequoia",
                announced_date="2025-01-15",
            ),
            _claim("ft.com", 0.78, lead="Sequoia", announced_date="2025-01-22"),
            _claim("axios.com", 0.78, lead="Sequoia", announced_date="2025-01-29"),
        ]
    )
    assert meta["unique_domains"] >= 5
    assert score >= 0.75


def test_mean_weight_not_max_dominates():
    single_tier1, _ = compute_corroboration([_claim("techcrunch.com", 0.78)])
    with_low, _ = compute_corroboration(
        [
            _claim("techcrunch.com", 0.78, announced_date="2025-01-10"),
            _claim("randomblog.io", 0.50, announced_date="2025-01-12"),
        ]
    )
    assert with_low > single_tier1


def test_official_single_domain_building_not_strong():
    score, meta = compute_corroboration([_claim("acme.com", 1.0, official=True, amount=5_000_000)])
    assert meta["official_present"] is True
    assert 0.45 <= score <= 0.60
    assert score < 0.75


def test_amount_disagreement_penalizes():
    agree, _ = compute_corroboration(
        [
            _claim("a.com", 0.7, amount=10_000_000, announced_date="2025-01-10"),
            _claim("b.com", 0.7, amount=10_500_000, announced_date="2025-01-12"),
        ]
    )
    disagree, meta = compute_corroboration(
        [
            _claim("a.com", 0.7, amount=10_000_000, announced_date="2025-01-10"),
            _claim("b.com", 0.7, amount=50_000_000, announced_date="2025-01-12"),
        ]
    )
    assert meta["amount_agreement"] is False
    assert agree > disagree


def test_rumor_penalty():
    clean, _ = compute_corroboration(
        [
            _claim("a.com", 0.78, announced_date="2025-01-10"),
            _claim("b.com", 0.78, announced_date="2025-01-12"),
        ]
    )
    with_rumor, meta = compute_corroboration(
        [
            _claim("a.com", 0.78, announced_date="2025-01-10"),
            _claim("b.com", 0.78, rumor=True, announced_date="2025-01-12"),
        ]
    )
    assert meta["rumor_present"] is True
    assert clean > with_rumor


def test_positive_weights_sum_to_one():
    assert sum(CONFIDENCE_WEIGHTS.values()) == pytest.approx(1.0, abs=0.001)


def test_meta_includes_weights_version():
    _, meta = compute_corroboration([_claim("x.com", 0.7)])
    assert meta["weights_version"] == 3


def test_optional_valuation_bonus_only_when_agreement():
    base_amount = 10_000_000
    base_round = "Series A"
    agree_claims = [
        {
            **_claim(
                "a.com",
                0.78,
                announced_date="2025-01-10",
                amount=base_amount,
                round_type=base_round,
            ),
            "valuation_usd": 100_000_000,
        },
        {
            **_claim(
                "b.com",
                0.78,
                announced_date="2025-01-12",
                amount=base_amount,
                round_type=base_round,
            ),
            "valuation_usd": 105_000_000,
        },
    ]
    disagree_claims = [
        {
            **_claim(
                "a.com",
                0.78,
                announced_date="2025-01-10",
                amount=base_amount,
                round_type=base_round,
            ),
            "valuation_usd": 100_000_000,
        },
        {
            **_claim(
                "b.com",
                0.78,
                announced_date="2025-01-12",
                amount=base_amount,
                round_type=base_round,
            ),
            "valuation_usd": 500_000_000,
        },
    ]
    agree, meta_agree = compute_corroboration(agree_claims)
    disagree, meta_disagree = compute_corroboration(disagree_claims)
    comps_agree = meta_agree.get("components") or {}
    comps_disagree = meta_disagree.get("components") or {}
    assert "optional_valuation_field_agreement" in comps_agree
    assert "optional_valuation_field_agreement" not in comps_disagree
    assert agree >= disagree
