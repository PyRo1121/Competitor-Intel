"""Sector-agnostic entity extraction from headlines."""

from collectors.candidate_discovery import compute_attention_score
from collectors.entity_extract import (
    extract_entities_from_text,
    hype_keyword_hits,
    is_plausible_company_name,
    text_has_hype,
)


def test_extract_funding_headline():
    text = "Acme Robotics raises $40M Series B led by Sequoia"
    names = extract_entities_from_text(text)
    assert any("Acme" in n for n in names)


def test_hype_and_plausible():
    assert text_has_hype("startup closes seed round")
    assert hype_keyword_hits("raised funding launch") >= 2
    assert is_plausible_company_name("Acme Labs")
    assert not is_plausible_company_name("the")


def test_attention_score_weights_volume():
    stats = {
        "signal_ids": list(range(20)),
        "sources": {"rss", "hackernews", "sec_edgar"},
        "hype_hits": 4,
    }
    score, breakdown = compute_attention_score(stats)
    assert score > 0.5
    assert breakdown["signal_volume"] > 0.9
