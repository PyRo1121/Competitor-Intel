#!/usr/bin/env bash
# Thin Hermes shim — sole supported way to invoke Competitor Intel from Hermes agents.
# Do not run collectors or daily_intel from ~/.hermes/agents/competitor_intel/.
set -euo pipefail

MONOREPO="${COMPETITOR_INTEL_ROOT:-$HOME/Documents/Competitor-Intel}"
API_URL="${CI_API_URL:-http://localhost:3000}"
export CI_DB_PATH="${CI_DB_PATH:-$MONOREPO/data/competitor_intel.db}"

mode="${1:-status}"

run_monorepo() {
  cd "$MONOREPO"
  uv run "$@"
}

case "$mode" in
  status)
    curl -sf "$API_URL/api/status" | jq .
    ;;
  daily)
    run_monorepo python apps/worker/daily_intel.py
    ;;
  intel|run_intel)
    run_monorepo python apps/cli/run_intel.py "${@:2}"
    ;;
  cli)
    run_monorepo python apps/cli/intel.py "${@:2}"
    ;;
  companies)
    curl -sf "$API_URL/api/companies?limit=${2:-20}" | jq .
    ;;
  *)
    echo "Usage: $0 {status|daily|intel|cli|companies [limit]}" >&2
    echo "  daily     — full ingest pipeline (apps/worker/daily_intel.py)" >&2
    echo "  intel     — signal processing (apps/cli/run_intel.py)" >&2
    echo "  cli       — intel.py subcommands" >&2
    echo "  status    — API health (requires apps/api on CI_API_URL)" >&2
    exit 1
    ;;
esac
