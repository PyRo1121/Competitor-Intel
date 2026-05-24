"""fetch_x.py must dispatch to existing provider scripts (grok refresh default path)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fetch_x_grok_target_exists():
    script = ROOT / "scripts" / "fetch_grok_x.py"
    assert script.is_file(), "default CI_X_PROVIDER=grok requires scripts/fetch_grok_x.py"


def test_fetch_xurl_target_exists():
    script = ROOT / "scripts" / "fetch_xurl.py"
    assert script.is_file()


def test_fetch_x_dry_dispatch_grok(monkeypatch):
    """fetch_x must invoke fetch_grok_x.py, not a missing path (regression: v1 prune)."""
    monkeypatch.setenv("CI_X_PROVIDER", "grok")
    calls: list[str] = []

    def fake_call(cmd, cwd=None):
        calls.append(cmd[1])
        return 0

    import scripts.fetch_x as fetch_x

    monkeypatch.setattr(fetch_x.subprocess, "call", fake_call)
    assert fetch_x.main() == 0
    assert calls[-1].endswith("fetch_grok_x.py")


def test_fetch_x_dry_dispatch_xurl(monkeypatch):
    monkeypatch.setenv("CI_X_PROVIDER", "xurl")
    calls: list[str] = []

    def fake_call(cmd, cwd=None):
        calls.append(cmd[1])
        return 0

    import scripts.fetch_x as fetch_x

    monkeypatch.setattr(fetch_x.subprocess, "call", fake_call)
    assert fetch_x.main() == 0
    assert calls[-1].endswith("fetch_xurl.py")
