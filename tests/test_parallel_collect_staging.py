"""parallel_collect staging merge and env cleanup."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from db.staging import clear_staging_run, list_staging_files


@pytest.mark.operational
def test_parallel_collect_merges_partial_staging(operational_db, monkeypatch, tmp_path):
    monkeypatch.setattr("db.staging.MONOREPO_ROOT", tmp_path)
    run_id = "partial-run"
    run_dir = tmp_path / "data" / "staging" / "raw_signals" / run_id
    run_dir.mkdir(parents=True)
    record = {
        "source": "partial_ok",
        "url": "https://example.com/partial-1",
        "company_id": None,
        "detected_at": "2026-05-24T12:00:00",
        "dedup_key": "partial_key_1",
        "data": {"url": "https://example.com/partial-1", "title": "partial"},
    }
    (run_dir / "rss_collector.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    calls: list[str] = []

    def fake_run_script(script, *args, cwd=None, logger=None, extra_env=None, **kwargs):
        calls.append(script)
        return script.endswith("rss_collector.py"), 0.01

    monkeypatch.setenv("CI_INGEST_STAGING", "1")
    monkeypatch.setenv("CI_STAGING_RUN_ID", run_id)
    monkeypatch.setenv("CI_SQLITE_WRITER_LOCK", "0")

    from automation.parallel_collect import run_parallel_collectors

    with patch("automation.parallel_collect.run_script", fake_run_script):
        ok, total, _ = run_parallel_collectors(
            scripts=["collectors/rss_collector.py", "collectors/yc_collector.py"]
        )

    assert ok == 1
    assert total == 2
    assert len(list_staging_files(run_id)) == 0
    from db.connection import get_conn

    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE source = 'partial_ok'").fetchone()[0]
    conn.close()
    assert n == 1
    clear_staging_run(run_id)


@pytest.mark.operational
def test_parallel_collect_clears_staging_env_after_run(monkeypatch, tmp_path):
    monkeypatch.setattr("db.staging.MONOREPO_ROOT", tmp_path)

    def fake_run_script(script, *args, **kwargs):
        return True, 0.0

    monkeypatch.setenv("CI_INGEST_STAGING", "1")

    from automation.parallel_collect import run_parallel_collectors

    with patch("automation.parallel_collect.run_script", fake_run_script):
        run_parallel_collectors(scripts=["collectors/rss_collector.py"])

    assert os.environ.get("CI_INGEST_STAGING") == "0"
    assert "CI_STAGING_RUN_ID" not in os.environ
    assert "CI_STAGING_SLOT" not in os.environ
