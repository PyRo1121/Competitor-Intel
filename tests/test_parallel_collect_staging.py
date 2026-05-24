"""parallel_collect staging merge must not require all collectors to succeed."""

from __future__ import annotations

from unittest.mock import patch

from automation.parallel_collect import run_parallel_collectors


def test_merge_runs_when_some_collectors_fail(monkeypatch):
    monkeypatch.setenv("CI_INGEST_STAGING", "1")
    monkeypatch.setenv("CI_STAGING_RUN_ID", "partial-run")

    scripts = ["collectors/a.py", "collectors/b.py"]
    outcomes = {
        "collectors/a.py": (True, 1.0),
        "collectors/b.py": (False, 0.5),
    }

    def fake_run_script(script, *args, **kwargs):
        return outcomes[script]

    with (
        patch("automation.parallel_collect.run_script", side_effect=fake_run_script),
        patch("automation.parallel_collect.merge_staged_run") as merge,
        patch("automation.parallel_collect.clear_staging_run") as clear,
    ):
        ok, total, _ = run_parallel_collectors(scripts=scripts)

    merge.assert_called_once_with("partial-run")
    clear.assert_called_once_with("partial-run")
    assert ok == 1
    assert total == 2
