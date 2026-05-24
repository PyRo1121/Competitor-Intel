#!/usr/bin/env bash
# Bare-metal health checks for Competitor Intel (P3-7 — no Docker).
set -euo pipefail

ROOT="${COMPETITOR_INTEL_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
API_URL="${CI_API_URL:-http://127.0.0.1:3000}"
DASHBOARD_URL="${CI_DASHBOARD_URL:-}"
DB_PATH="${CI_DB_PATH:-$ROOT/data/competitor_intel.db}"
API_TIMEOUT_SEC="${CI_HEALTH_API_TIMEOUT_SEC:-30}"
FAIL=0

check() {
  local name="$1"
  shift
  if "$@"; then
    echo "ok  $name"
  else
    echo "FAIL $name" >&2
    FAIL=1
  fi
}

check "sqlite db exists" test -f "$DB_PATH"
check "sqlite db readable" sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null
check "api /health" bash -c "
curl -sf --max-time ${API_TIMEOUT_SEC} '${API_URL}/health' | python3 -c \"
import json, sys
d = json.load(sys.stdin)
assert d.get('status') == 'ok' or d.get('ok') is True, d
\"
"
check "api /api/status" bash -c "
curl -sf --max-time ${API_TIMEOUT_SEC} '${API_URL}/api/status' | python3 -c \"
import json, sys
d = json.load(sys.stdin)
assert 'queriedAt' in d and isinstance(d.get('counts'), dict), d
\"
"

if [[ -n "$DASHBOARD_URL" ]]; then
  check "dashboard reachable" curl -sf --max-time "${API_TIMEOUT_SEC}" -o /dev/null "$DASHBOARD_URL"
fi

if [[ -n "${CI_HEALTH_FRESHNESS_MAX_HOURS:-}" ]]; then
  check "api signal freshness (<=${CI_HEALTH_FRESHNESS_MAX_HOURS}h)" bash -c "
curl -sf --max-time ${API_TIMEOUT_SEC} '${API_URL}/api/status' | python3 -c \"
import json, sys
from datetime import datetime, timezone, timedelta
max_h = float('${CI_HEALTH_FRESHNESS_MAX_HOURS}')
d = json.load(sys.stdin)
last = (d.get('freshness') or {}).get('lastSignalAt')
assert last, {'freshness': d.get('freshness')}
ts = datetime.fromisoformat(last.replace('Z', '+00:00'))
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=timezone.utc)
age = datetime.now(timezone.utc) - ts
assert age <= timedelta(hours=max_h), {'lastSignalAt': last, 'age_hours': age.total_seconds() / 3600}
\"
"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "healthcheck: one or more checks failed" >&2
  exit 1
fi
echo "healthcheck: all passed"
