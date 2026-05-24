"""Enterprise SQLite guard (Track 4 P4-2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from utils.enterprise_guard import (
    assert_enterprise_sqlite_safe,
    is_default_prod_sqlite,
)


def test_is_default_when_ci_db_path_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CI_DB_PATH", raising=False)
    # Guard compares resolved path to DEFAULT_DB_PATH from ci_paths
    assert is_default_prod_sqlite() is True


def test_not_default_when_ci_db_path_points_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    other = tmp_path / "shadow.db"
    other.touch()
    monkeypatch.setenv("CI_DB_PATH", str(other))
    assert is_default_prod_sqlite() is False


def test_assert_blocks_default_prod_without_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI_DB_PATH", raising=False)
    monkeypatch.delenv("CI_ENTERPRISE_ALLOW_PROD", raising=False)
    with pytest.raises(SystemExit) as exc:
        assert_enterprise_sqlite_safe(context="test")
    assert exc.value.code == 1


def test_assert_allows_non_default_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CI_DB_PATH", str(tmp_path / "copy.db"))
    monkeypatch.delenv("CI_ENTERPRISE_ALLOW_PROD", raising=False)
    assert_enterprise_sqlite_safe(context="test")


def test_assert_allows_override_on_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CI_DB_PATH", raising=False)
    monkeypatch.setenv("CI_ENTERPRISE_ALLOW_PROD", "1")
    assert_enterprise_sqlite_safe(context="test")
