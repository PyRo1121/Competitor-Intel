"""Tests for shared funding amount parsing."""

from __future__ import annotations

from collectors.funding_parse import parse_amount_usd


def test_parse_amount_usd_billion():
    assert parse_amount_usd("Company raised $2.5 billion") == 2_500_000_000


def test_parse_amount_usd_million():
    assert parse_amount_usd("closes $120M round") == 120_000_000


def test_parse_amount_usd_thousands():
    assert parse_amount_usd("grant of $500K") == 500_000


def test_parse_amount_usd_large_bare_dollar():
    assert parse_amount_usd("deal worth $250,000,000") == 250_000_000


def test_parse_amount_usd_small_bare_ignored():
    assert parse_amount_usd("fee of $50,000") is None


def test_parse_amount_usd_empty():
    assert parse_amount_usd("") is None
