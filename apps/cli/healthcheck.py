#!/usr/bin/env python3
"""SQLite health probe for make health-check (replaces scripts/healthcheck.sh)."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ci_paths import db_path, ensure_app_paths

ensure_app_paths()


def _check(name: str, ok: bool) -> bool:
    if ok:
        print(f"ok  {name}")
        return True
    print(f"FAIL {name}", file=sys.stderr)
    return False


def _sqlite_checks(db: Path) -> bool:
    ok = True
    ok &= _check("sqlite db exists", db.is_file())
    if not db.is_file():
        return False
    try:
        conn = sqlite3.connect(db)
        conn.execute("SELECT 1")
        conn.execute("SELECT 1 FROM companies LIMIT 1")
        conn.close()
        ok &= _check("sqlite db readable", True)
        ok &= _check("sqlite companies table", True)
    except sqlite3.Error:
        ok &= _check("sqlite db readable", False)
    return ok


def _api_get(url: str, timeout: int) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _api_checks(api_url: str, timeout: int, max_freshness_hours: str | None) -> bool:
    ok = True
    try:
        health = _api_get(f"{api_url.rstrip('/')}/health", timeout)
        ok &= _check(
            "api /health",
            health.get("status") == "ok" or health.get("ok") is True,
        )
        status = _api_get(f"{api_url.rstrip('/')}/api/status", timeout)
        ok &= _check(
            "api /api/status",
            "queriedAt" in status and isinstance(status.get("counts"), dict),
        )
        if max_freshness_hours and ok:
            from datetime import datetime, timedelta, timezone

            last = (status.get("freshness") or {}).get("lastSignalAt")
            if not last:
                ok &= _check("api signal freshness", False)
            else:
                ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - ts
                ok &= _check(
                    f"api signal freshness (<={max_freshness_hours}h)",
                    age <= timedelta(hours=float(max_freshness_hours)),
                )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        ok &= _check("api /health", False)
    return ok


def main() -> int:
    db = db_path()
    api_url = os.environ.get("CI_API_URL", "http://127.0.0.1:3000")
    dashboard_url = os.environ.get("CI_DASHBOARD_URL", "")
    timeout = int(os.environ.get("CI_HEALTH_API_TIMEOUT_SEC", "30"))
    require_api = os.environ.get("CI_HEALTH_REQUIRE_API", "0") == "1"
    max_fresh = os.environ.get("CI_HEALTH_FRESHNESS_MAX_HOURS")

    ok = _sqlite_checks(db)
    if require_api:
        ok &= _api_checks(api_url, timeout, max_fresh)
    if dashboard_url:
        try:
            urllib.request.urlopen(dashboard_url, timeout=timeout)
            ok &= _check("dashboard reachable", True)
        except (urllib.error.URLError, TimeoutError):
            ok &= _check("dashboard reachable", False)

    if not ok:
        print("healthcheck: one or more checks failed", file=sys.stderr)
        return 1
    print("healthcheck: all passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
