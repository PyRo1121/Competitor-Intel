"""parallel_collect staging merge must not drop data on partial collector failure."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.operational
def test_partial_collector_failure_still_merges_staging(monkeypatch, tmp_path):
    monkeypatch.setenv("CI_INGEST_STAGING", "1")
    monkeypatch.setenv("CI_STAGING_RUN_ID", "partial-merge-run")
    monkeypatch.setattr("db.staging.MONOREPO_ROOT", tmp_path)

    run_id = "partial-merge-run"
    run_dir = tmp_path / "data" / "staging" / "raw_signals" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "rss_collector.jsonl").write_text(
        '{"source":"partial_test","url":"https://example.com/partial",'
        '"company_id":null,"detected_at":"2026-05-24T12:00:00",'
        '"dedup_key":"partial_key","data":{"title":"staged"}}\n',
        encoding="utf-8",
    )

    def fake_run(script: str, *args, **kwargs):
        if "fail" in script:
            return False, 0.01
        return True, 0.01

    with (
        patch("automation.parallel_collect.run_script", side_effect=fake_run),
        patch("automation.parallel_collect.merge_staged_run") as merge_mock,
    ):
        from automation.parallel_collect import run_parallel_collectors

        ok, total, _ = run_parallel_collectors(
            scripts=["collectors/ok_collector.py", "collectors/fail_collector.py"],
        )

    merge_mock.assert_called_once_with(run_id)
    assert ok < total
