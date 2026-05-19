#!/usr/bin/env bash
# Example Hermes shim — call Competitor Intel API or CLI without embedding imports.
set -euo pipefail

MONOREPO="${COMPETITOR_INTEL_ROOT:-$HOME/Documents/Competitor-Intel}"
API_URL="${CI_API_URL:-http://localhost:3000}"

mode="${1:-status}"

case "$mode" in
  status)
    curl -sf "$API_URL/api/status" | jq .
    ;;
  daily)
    cd "$MONOREPO"
    export CI_DB_PATH="${CI_DB_PATH:-$MONOREPO/data/competitor_intel.db}"
    uv run python apps/worker/daily_intel.py
    ;;
  companies)
    curl -sf "$API_URL/api/companies?limit=${2:-20}" | jq .
    ;;
  *)
    echo "Usage: $0 {status|daily|companies [limit]}" >&2
    exit 1
    ;;
esac
