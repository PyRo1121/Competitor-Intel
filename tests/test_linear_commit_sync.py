"""Tests for Linear commit message parsing (no API calls)."""

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "linear_commit_sync.py"
_spec = importlib.util.spec_from_file_location("linear_commit_sync", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

parse_close_identifiers = _mod.parse_close_identifiers


def test_fixes_single():
    assert parse_close_identifiers("fixes COM-12") == ["COM-12"]


def test_closes_multiple():
    assert parse_close_identifiers("Closes COM-1, COM-2") == ["COM-1", "COM-2"]


def test_subject_done_marker():
    msg = "COM-99: healthcheck moved to Python [done]"
    assert parse_close_identifiers(msg) == ["COM-99"]


def test_reference_only_no_close():
    assert parse_close_identifiers("COM-99: refactor collectors") == []


def test_merge_commit_style():
    body = "feat: pipeline\n\nfixes COM-19"
    assert parse_close_identifiers(body) == ["COM-19"]
