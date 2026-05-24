"""x_signal_collector must propagate failure to subprocess exit (grok_refresh / parallel)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "packages" / "py-collectors" / "collectors" / "x_signal_collector.py"


def _run_collector(env: dict[str, str]) -> int:
    merged = os.environ.copy()
    merged.update(env)
    proc = subprocess.run(
        [sys.executable, str(COLLECTOR)],
        cwd=str(ROOT),
        env=merged,
        capture_output=True,
        text=True,
    )
    return proc.returncode


def test_exits_nonzero_when_require_grok_and_empty_batch(operational_db, tmp_path):
    batch_file = tmp_path / "grok_x_results.json"
    batch_file.write_text("[]", encoding="utf-8")
    code = _run_collector(
        {
            "CI_DB_PATH": operational_db,
            "GROK_X_RESULTS_PATH": str(batch_file),
            "CI_REQUIRE_GROK_X": "1",
            "CI_AUTO_GROK_X": "0",
        }
    )
    assert code == 1


def test_exits_zero_when_one_post_ingested(operational_db, tmp_path):
    batch_file = tmp_path / "grok_x_results.json"
    batch_file.write_text(
        json.dumps(
            [
                {
                    "query": "test",
                    "results": [
                        {
                            "post_id": "exit-test-1",
                            "text": "Acme Corp raised Series A",
                            "url": "https://x.com/i/status/exit-test-1",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    code = _run_collector(
        {
            "CI_DB_PATH": operational_db,
            "GROK_X_RESULTS_PATH": str(batch_file),
            "CI_REQUIRE_GROK_X": "1",
            "CI_AUTO_GROK_X": "0",
        }
    )
    assert code == 0
