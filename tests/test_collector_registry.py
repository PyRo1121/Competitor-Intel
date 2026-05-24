"""Collector registry completeness — every __main__ script must be registered."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from automation.collector_registry import (
    DAILY_NO_X_PARALLEL_COLLECTORS,
    GROK_COLLECTORS,
    INTEL_CLI_COLLECTORS,
    PARALLEL_COLLECTORS,
    _company_data_rollup_enabled,
    registered_collector_script_paths,
)

COLLECTORS_ROOT = ROOT / "packages" / "py-collectors" / "collectors"
_MAIN_RE = re.compile(r'if __name__\s*==\s*["\']__main__["\']')


def _collector_entrypoint_paths() -> frozenset[str]:
    paths: list[str] = []
    for py_file in sorted(COLLECTORS_ROOT.rglob("*.py")):
        if py_file.name == "__init__.py":
            continue
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if _MAIN_RE.search(text):
            rel = py_file.relative_to(ROOT / "packages" / "py-collectors")
            paths.append(str(rel).replace("\\", "/"))
    return frozenset(paths)


def test_intel_cli_paths_exist():
    base = ROOT / "packages" / "py-collectors"
    missing = [p for p in INTEL_CLI_COLLECTORS.values() if not (base / p).is_file()]
    assert not missing, f"INTEL_CLI_COLLECTORS points at missing files: {missing}"


def test_daily_no_x_parallel_is_parallel_minus_x():
    assert (
        tuple(s for s in PARALLEL_COLLECTORS if s != "collectors/x_signal_collector.py")
        == DAILY_NO_X_PARALLEL_COLLECTORS
    )


def test_x_signal_only_on_grok_cron_not_daily_no_x():
    assert "collectors/x_signal_collector.py" in PARALLEL_COLLECTORS
    assert "collectors/x_signal_collector.py" not in DAILY_NO_X_PARALLEL_COLLECTORS
    assert GROK_COLLECTORS == ("collectors/x_signal_collector.py",)


def test_parallel_collectors_single_rss_walker():
    rss = [p for p in PARALLEL_COLLECTORS if "rss" in p or "multi_source" in p]
    assert rss == ["collectors/rss_collector.py"]


def test_company_data_rollup_default_on_when_unset(monkeypatch):
    monkeypatch.delenv("CI_COMPANY_DATA_ROLLUP", raising=False)
    monkeypatch.delenv("CI_PHASE_B_COMPANY", raising=False)
    assert _company_data_rollup_enabled() is True


def test_company_data_rollup_opt_out(monkeypatch):
    monkeypatch.setenv("CI_COMPANY_DATA_ROLLUP", "0")
    assert _company_data_rollup_enabled() is False


def _resolve_registry_script(path: str) -> Path:
    if path.startswith("collectors/"):
        return ROOT / "packages" / "py-collectors" / path
    return ROOT / path


def test_scheduled_collector_paths_exist():
    """Every registry path must exist; legacy __main__ scripts may stay off-schedule."""
    registered = registered_collector_script_paths(include_gated_daily=True)
    missing = [p for p in sorted(registered) if not _resolve_registry_script(p).is_file()]
    assert not missing, f"Registry points at missing files: {missing}"
