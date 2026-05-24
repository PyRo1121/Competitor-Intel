#!/usr/bin/env bash
# Thin Hermes shim — sole supported way to invoke Competitor Intel from Hermes agents.
# Do not run collectors or daily_intel from ~/.hermes/agents/competitor_intel/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONOREPO="${COMPETITOR_INTEL_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
API_URL="${CI_API_URL:-http://localhost:3000}"
export CI_DB_PATH="${CI_DB_PATH:-$MONOREPO/data/competitor_intel.db}"

# Hermes / Grok X paths are opt-in. Set CI_DISABLE_HERMES=1 or CI_SKIP_GROK_X=1 in CI.
_hermes_disabled() {
  case "${CI_DISABLE_HERMES:-}${CI_SKIP_GROK_X:-}" in
    1|true|yes|TRUE|YES) return 0 ;;
    *) return 1 ;;
  esac
}

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
    CI_SKIP_GROK_X=1 run_monorepo python apps/worker/daily_intel.py
    ;;
  daily-prod|daily_prod)
    CI_SKIP_GROK_X=1 CI_STRICT_PIPELINE=1 CI_REQUIRE_DEDUP_INDEX=1 run_monorepo python apps/worker/daily_intel.py
    ;;
  frequent)
    run_monorepo python apps/worker/frequent_intel.py
    ;;
  grok-x-ingest|grok_x_ingest)
    cd "$MONOREPO"
    make grok-x-ingest
    ;;
  grok-refresh|grok_refresh)
    if _hermes_disabled; then
      echo "Hermes/Grok skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)" >&2
      exit 0
    fi
    run_monorepo python apps/worker/grok_refresh.py
    ;;
  full-sweep)
    cd "$MONOREPO"
    make full-sweep
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
  grok-x|grok-ingest)
    if _hermes_disabled; then
      echo "Hermes/Grok skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)" >&2
      exit 0
    fi
    run_monorepo python integrations/hermes/ingest_grok_x.py "${@:2}"
    ;;
  grok-x-fetch)
    if _hermes_disabled; then
      echo "Hermes/Grok skipped (CI_DISABLE_HERMES or CI_SKIP_GROK_X)" >&2
      exit 0
    fi
    run_monorepo python scripts/fetch_x.py "${@:2}"
    ;;
  x-fetch)
    run_monorepo python scripts/fetch_xurl.py "${@:2}"
    ;;
  x-check)
    run_monorepo python scripts/fetch_xurl.py --check
    ;;
  export-x-queries)
    run_monorepo python scripts/export_x_monitor_queries.py
    ;;
  *)
    echo "Usage: $0 {status|daily|daily-prod|frequent|full-sweep|grok-refresh|grok-x-ingest|intel|cli|companies|grok-x|grok-x-fetch|x-fetch|x-check|export-x-queries ...}" >&2
    echo "  daily            — full ingest (CI_SKIP_GROK_X=1)" >&2
    echo "  daily-prod       — prod cron: strict pipeline + dedup index required" >&2
    echo "  frequent         — RSS/open-web hourly tier (no Grok X)" >&2
    echo "  full-sweep       — on-demand: daily first, enriched X queries, then X ingest" >&2
    echo "  grok-refresh     — X fetch + ingest + reprocess (~5×/day; CI_X_PROVIDER=xurl|grok)" >&2
    echo "  grok-x-ingest    — ingest grok_x_results.json + fanout + funding rollup (make grok-x-ingest)" >&2
    echo "  intel            — signal processing (apps/cli/run_intel.py)" >&2
    echo "  grok-x-fetch     — X fetch → grok_x_results.json (CI_X_PROVIDER=xurl|grok)" >&2
    echo "  x-fetch          — xurl only (official X API CLI)" >&2
    echo "  x-check          — verify xurl install + auth" >&2
    echo "  grok-x           — ingest Grok X JSON (see ingest_grok_x.py --help)" >&2
    echo "  export-x-queries — write PROMPT_X.md + query list for Hermes" >&2
    echo "  cli              — intel.py subcommands" >&2
    echo "  status           — API health (requires apps/api on CI_API_URL)" >&2
    exit 1
    ;;
esac
