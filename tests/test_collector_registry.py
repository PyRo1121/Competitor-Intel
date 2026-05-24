"""Collector registry completeness — every __main__ script must be registered."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "worker"))

from automation.collector_registry import (  # noqa: E402
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


def test_every_collector_entrypoint_is_registered():
    registered = registered_collector_script_paths(include_gated_daily=True)
    entrypoints = _collector_entrypoint_paths()
    unregistered = sorted(entrypoints - registered)
    assert not unregistered, (
        "Add to collector_registry (schedule or INTEL_CLI_COLLECTORS): " + ", ".join(unregistered)
    )
