"""Daily pipeline fail-fast behavior (P0-5)."""

from __future__ import annotations

import sys

import pytest

from automation.pipeline_runner import _abort_unless_force


@pytest.mark.parametrize(
    "ok,force,expected_abort",
    [
        (True, False, False),
        (False, False, True),
        (False, True, False),
    ],
)
def test_abort_unless_force(ok: bool, force: bool, expected_abort: bool):
    assert _abort_unless_force("step", ok, force) is expected_abort


def test_daily_main_aborts_after_parallel_failure(monkeypatch):
    import daily_intel

    monkeypatch.setattr(sys, "argv", ["daily_intel.py"])
    calls: list[str] = []

    def fake_run_script(script, *args, logger=None, **kwargs):
        calls.append(script)
        if "parallel_collect" in script:
            return False, 0.01
        return True, 0.01

    monkeypatch.setattr(daily_intel, "run_script", fake_run_script)
    monkeypatch.setattr(
        daily_intel,
        "get_daily_sequential",
        lambda: (("collectors/signal_processor.py", ()),),
    )
    monkeypatch.setenv("CI_SKIP_GROK_X", "1")

    assert daily_intel.main() == 1
    assert any("parallel_collect" in c for c in calls)
    assert not any("run_intel" in c for c in calls)
    assert not any("signal_processor" in c for c in calls)


def test_daily_main_aborts_on_quality_gate_failure(monkeypatch):
    import daily_intel

    monkeypatch.setattr(sys, "argv", ["daily_intel.py"])
    calls: list[str] = []

    def fake_run_script(script, *args, logger=None, **kwargs):
        calls.append(script)
        if "intel_quality_gate" in script:
            return False, 0.01
        return True, 0.01

    monkeypatch.setattr(daily_intel, "run_script", fake_run_script)
    monkeypatch.setattr(
        daily_intel,
        "get_daily_sequential",
        lambda: (
            ("collectors/signal_processor.py", ()),
            ("collectors/signal_repair.py", ()),
            ("collectors/intel_quality_gate.py", ()),
            ("collectors/funding_rollup.py", ()),
        ),
    )
    monkeypatch.setenv("CI_SKIP_GROK_X", "1")

    assert daily_intel.main() == 1
    assert "collectors/funding_rollup.py" not in calls


def test_daily_main_dry_run_completes(monkeypatch):
    import daily_intel

    monkeypatch.setattr(sys, "argv", ["daily_intel.py", "--dry-run"])
    calls: list[str] = []

    def fake_run_script(script, *args, logger=None, **kwargs):
        calls.append(script)
        return True, 0.0

    monkeypatch.setattr(daily_intel, "run_script", fake_run_script)
    monkeypatch.setattr(
        daily_intel,
        "get_daily_sequential",
        lambda: (
            ("collectors/signal_processor.py", ()),
            ("collectors/intel_quality_gate.py", ()),
        ),
    )
    monkeypatch.setenv("CI_SKIP_GROK_X", "1")

    assert daily_intel.main() == 0
    assert any("parallel_collect" in c for c in calls)
    assert "run_intel.py" in calls
    assert any("signal_processor" in c for c in calls)
    assert any("intel_quality_gate" in c for c in calls)


def test_daily_sequential_has_repair_before_gate():
    from automation.collector_registry import get_daily_sequential

    scripts = [s for s, _ in get_daily_sequential()]
    assert scripts.index("collectors/signal_repair.py") < scripts.index(
        "collectors/intel_quality_gate.py"
    )
    assert scripts.index("collectors/signal_processor.py") < scripts.index(
        "collectors/signal_repair.py"
    )
