"""Tests for Linear commit message parsing (no API calls)."""

from integrations.linear.commit_sync import parse_close_identifiers


def test_fixes_single():
    assert parse_close_identifiers("fixes COM-12") == ["COM-12"]


def test_closes_multiple():
    assert parse_close_identifiers("Closes COM-1, COM-2") == ["COM-1", "COM-2"]


def test_subject_done_marker():
    msg = "COM-99: healthcheck moved to Python [done]"
    assert parse_close_identifiers(msg) == ["COM-99"]


def test_reference_only_no_close():
    assert parse_close_identifiers("COM-99: refactor collectors") == []
