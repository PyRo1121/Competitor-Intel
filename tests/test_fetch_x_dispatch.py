"""fetch_x.py must dispatch to an existing script for each CI_X_PROVIDER."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FETCH_X = ROOT / "scripts" / "fetch_x.py"


def test_fetch_x_grok_target_exists():
    result = subprocess.run(
        [sys.executable, str(FETCH_X), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "CI_X_PROVIDER": "grok"},
    )
    assert "can't open file" not in (result.stderr or "")
    assert (ROOT / "scripts" / "fetch_grok_x.py").is_file()


def test_fetch_x_xurl_target_exists():
    assert (ROOT / "scripts" / "fetch_xurl.py").is_file()
