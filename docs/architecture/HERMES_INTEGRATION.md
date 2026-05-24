# Hermes integration

Hermes is an **external** agent runtime. This monorepo is invoked only via `integrations/hermes/` — no imports from `~/.hermes/hermes-agent` in daily code paths.

## Entrypoints

| Command | What runs |
|---------|-----------|
| `./call_intel.sh daily-prod` | `apps/worker/daily_intel.py` (strict, no inline Grok) |
| `./call_intel.sh grok-refresh` | `apps/worker/grok_refresh.py` → `scripts/fetch_x.py` |
| `./call_intel.sh status` | `apps/cli/intel.py status` (SQLite counts) |
| `./call_intel.sh grok-x` | `integrations/hermes/ingest_grok_x.py` |

Set `COMPETITOR_INTEL_ROOT` to the repo path and `HERMES_AGENT_ROOT` (or default `~/.hermes/hermes-agent`) for Grok fetch credentials.

## Grok / X data path

1. `export_x_monitor_queries.py` → `data/hermes_enrich/x_monitor_queries.json`
2. Hermes / `fetch_x.py` → `data/hermes_enrich/grok_x_results.json`
3. `x_signal_collector.py` + `signal_url_fanout` + `funding_rollup`

Use `CI_SKIP_GROK_X=1` on daily cron; run Grok on a separate schedule (see [SCHEDULING.md](../SCHEDULING.md)).

## Env

| Variable | Purpose |
|----------|---------|
| `CI_DB_PATH` | SQLite file |
| `CI_SKIP_GROK_X` | Skip inline X on daily |
| `CI_DISABLE_HERMES` | No-op grok modes in CI |
| `GROK_X_RESULTS_PATH` | Batch JSON for ingest |

Full catalog: `.env.example`.
