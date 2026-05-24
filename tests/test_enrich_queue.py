"""Tests for Hermes enrich queue export/apply (no LLM in tests)."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

import db.connection as db_connection  # noqa: E402
from db.schema import init_database  # noqa: E402
from scripts.enrich_queue_apply import ALLOWED_TYPES  # noqa: E402


@pytest.mark.operational
def test_apply_rejects_invalid_company_id(tmp_path):
    db_file = tmp_path / "apply.db"
    db_connection._test_db_override = db_file
    init_database()
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO companies (name, slug) VALUES ('RealCo', 'realco')")
    cur.execute(
        """
        INSERT INTO intelligence_events
        (company_id, event_type, source, source_url, confidence, announced_date, created_at, updated_at)
        VALUES (
            NULL, 'General News', 'rss', 'https://ex.com/a', 0.2,
            datetime('now'), datetime('now'), datetime('now')
        )
        """
    )
    eid = cur.lastrowid
    conn.commit()
    conn.close()

    enrich_dir = tmp_path / "hermes_enrich"
    enrich_dir.mkdir()
    (enrich_dir / "enrich_results.jsonl").write_text(
        json.dumps(
            {
                "event_id": eid,
                "event_type": "Partnership",
                "company_id": 99999,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    import subprocess

    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "enrich_queue_apply.py"),
            "--in-dir",
            str(enrich_dir),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "CI_DB_PATH": str(db_file)},
    )
    assert r.returncode == 0

    conn = sqlite3.connect(db_file)
    row = conn.execute(
        "SELECT event_type, company_id, confidence FROM intelligence_events WHERE id = ?",
        (eid,),
    ).fetchone()
    conn.close()
    db_connection._test_db_override = None
    assert row[0] == "General News"
    assert row[1] is None
    assert row[2] == pytest.approx(0.2)


def test_allowed_types_include_funding():
    assert "Funding Round" in ALLOWED_TYPES
