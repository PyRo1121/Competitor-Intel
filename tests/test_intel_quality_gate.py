"""Tests for intel_quality_gate metrics (no production DB required)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.intel_quality_gate import (  # noqa: E402
    check_metrics,
    collect_metrics,
)
from db.schema import init_database  # noqa: E402


def _seed_healthy_db(path: Path) -> None:
    """Minimal DB that should pass all gate thresholds."""
    import db.connection as db_connection

    db_connection._test_db_override = path
    init_database()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('TrackedCo', 'trackedco')")
    cid = cur.lastrowid
    payload = json.dumps(
        {
            "title": "TrackedCo launches new API for developers",
            "url": "https://example.com/trackedco-api",
        }
    )
    cur.execute(
        """
        INSERT INTO raw_signals (company_id, source, signal_type, data_json, processed)
        VALUES (?, 'rss', 'news', ?, 1)
        """,
        (cid, payload),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, confidence,
         description, announced_date, created_at)
        VALUES (?, 'Product Launch', 'rss', 'https://example.com/trackedco-api',
                ?, 0.8, 'TrackedCo launches new API', datetime('now'), datetime('now'))
        """,
        (cid, sid),
    )
    conn.commit()
    conn.close()
    db_connection._test_db_override = None


@pytest.mark.operational
def test_collect_metrics_healthy_db(tmp_path):
    db_file = tmp_path / "gate_ok.db"
    _seed_healthy_db(db_file)
    conn = sqlite3.connect(db_file)
    metrics = collect_metrics(conn)
    conn.close()

    assert metrics["orphans"] == 0
    assert metrics["unprocessed"] == 0
    assert metrics["dup_raw_signal_id"] == 0
    assert metrics["actionable_null_pct"] == 0.0
    assert check_metrics(metrics) == []


@pytest.mark.operational
def test_check_metrics_fails_on_orphans():
    failed = check_metrics(
        {
            "orphans": 3,
            "unprocessed": 0,
            "null_company_pct": 10.0,
            "general_news_pct": 20.0,
            "dup_raw_signal_id": 0,
            "pct_funding_no_amount": 0.0,
            "actionable_null_pct": 0.0,
        }
    )
    assert any("orphans=" in f for f in failed)


@pytest.mark.operational
def test_actionable_null_detects_missed_company_name(tmp_path):
    """Null company_id when headline names a tracked company should fail gate."""
    db_file = tmp_path / "gate_actionable.db"
    import db.connection as db_connection

    db_connection._test_db_override = db_file
    init_database()
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('MissedCorp', 'missedcorp')")
    cur.execute(
        """
        INSERT INTO raw_signals (source, signal_type, data_json, processed)
        VALUES ('rss', 'news', ?, 1)
        """,
        (
            json.dumps(
                {
                    "title": "MissedCorp partners with BigTech on payments",
                    "url": "https://example.com/missed",
                }
            ),
        ),
    )
    sid = cur.lastrowid
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, raw_signal_id, confidence,
         description, announced_date, created_at)
        VALUES (NULL, 'Partnership', 'rss', 'https://example.com/missed', ?,
                0.7, 'MissedCorp partners with BigTech on payments',
                datetime('now'), datetime('now'))
        """,
        (sid,),
    )
    conn.commit()
    metrics = collect_metrics(conn)
    conn.close()
    db_connection._test_db_override = None

    assert metrics["actionable_null_pct"] > 5.0
    failed = check_metrics(metrics)
    assert any("actionable_null_pct" in f for f in failed)


@pytest.mark.operational
def test_check_metrics_fails_unprocessed_and_dupes():
    failed = check_metrics(
        {
            "orphans": 0,
            "unprocessed": 2,
            "null_company_pct": 10.0,
            "general_news_pct": 20.0,
            "dup_raw_signal_id": 1,
            "pct_funding_no_amount": 0.0,
            "actionable_null_pct": 0.0,
        }
    )
    assert any("unprocessed=" in f for f in failed)
    assert any("dup_raw_signal_id=" in f for f in failed)


@pytest.mark.operational
def test_check_metrics_fails_funding_without_amount(tmp_path):
    db_file = tmp_path / "gate_funding.db"
    import db.connection as db_connection

    db_connection._test_db_override = db_file
    init_database()
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, amount_usd, source, source_url, description,
         announced_date, created_at)
        VALUES (NULL, 'Funding Round', 0, 'rss', 'https://ex.com/f',
                'Startup raised $40 million', datetime('now'), datetime('now'))
        """
    )
    conn.commit()
    metrics = collect_metrics(conn)
    conn.close()
    db_connection._test_db_override = None

    assert metrics["pct_funding_no_amount"] == 100.0
    failed = check_metrics(metrics)
    assert any("pct_funding_no_amount" in f for f in failed)


@pytest.mark.operational
def test_collect_metrics_orphan_and_unprocessed(tmp_path):
    db_file = tmp_path / "gate_orphan.db"
    import db.connection as db_connection

    db_connection._test_db_override = db_file
    init_database()
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO raw_signals (source, signal_type, data_json, processed)
        VALUES ('rss', 'news', '{}', 0)
        """
    )
    conn.commit()
    metrics = collect_metrics(conn)
    conn.close()
    db_connection._test_db_override = None

    assert metrics["orphans"] == 1
    assert metrics["unprocessed"] == 1
