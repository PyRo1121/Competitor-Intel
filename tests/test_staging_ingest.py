"""Staging JSONL ingest → single SQLite merge."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ci_paths import MONOREPO_ROOT
from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup
from db.staging import clear_staging_run, list_staging_files, merge_staged_run


@pytest.mark.operational
def test_insert_routes_to_staging(operational_db, monkeypatch, tmp_path):
    monkeypatch.setattr("db.staging.MONOREPO_ROOT", tmp_path)
    run_id = "route-run"
    monkeypatch.setenv("CI_INGEST_STAGING", "1")
    monkeypatch.setenv("CI_STAGING_RUN_ID", run_id)
    monkeypatch.setenv("CI_STAGING_SLOT", "route")

    conn = get_conn()
    cur = conn.cursor()
    ok = insert_raw_signal_dedup(
        cur,
        "staging_route",
        "https://example.com/route-1",
        {"title": "via staging"},
        dedup_key="route_key_1",
    )
    conn.close()
    assert ok is True
    assert len(list_staging_files(run_id)) == 1
    clear_staging_run(run_id)


@pytest.mark.operational
def test_yc_collector_skips_writer_lock_when_staging(monkeypatch):
    """JSONL staging must not hold POSIX writer_lock (blocks ingest_staging merge)."""
    monkeypatch.setenv("CI_INGEST_STAGING", "1")
    monkeypatch.setenv("CI_STAGING_RUN_ID", "yc-lock-test")
    monkeypatch.setenv("CI_STAGING_SLOT", "yc_collector")
    with patch("collectors.yc_collector.writer_lock") as flock:
        with patch("collectors.yc_collector.safe_request") as req:
            req.return_value.json.return_value = []
            from collectors.yc_collector import run_yc_collector  # noqa: PLC0415

            run_yc_collector()
    flock.assert_not_called()


@pytest.mark.operational
def test_staging_merge_inserts(operational_db, monkeypatch, tmp_path):
    monkeypatch.setenv("CI_SQLITE_WRITER_LOCK", "0")
    monkeypatch.setattr("db.staging.MONOREPO_ROOT", tmp_path)
    run_id = "merge-run"
    run_dir = tmp_path / "data" / "staging" / "raw_signals" / run_id
    run_dir.mkdir(parents=True)
    record = {
        "source": "staging_test",
        "url": "https://example.com/staged-1",
        "company_id": None,
        "detected_at": "2026-05-24T12:00:00",
        "dedup_key": "staged_key_1",
        "data": {"url": "https://example.com/staged-1", "title": "staged"},
    }
    (run_dir / "unit.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

    summary = merge_staged_run(run_id)
    assert summary["inserted"] == 1

    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM raw_signals WHERE source = 'staging_test'"
    ).fetchone()[0]
    conn.close()
    assert n == 1
    clear_staging_run(run_id)
