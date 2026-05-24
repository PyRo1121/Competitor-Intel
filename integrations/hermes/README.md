# Hermes → Competitor Intel

Hermes agents must **not** import Python from `~/.hermes/agents/competitor_intel/`. Use this monorepo via **Python** only (no `.sh` shim).

**Scheduling:** [docs/SCHEDULING.md](../../docs/SCHEDULING.md) — `hermes cron create` + `integrations/hermes/cron_*.py`  
**Architecture:** [docs/architecture/HERMES_INTEGRATION.md](../../docs/architecture/HERMES_INTEGRATION.md)

## Environment

| Variable | Default |
|----------|---------|
| `COMPETITOR_INTEL_ROOT` | repo root (auto from script path) |
| `CI_DB_PATH` | `$MONOREPO/data/competitor_intel.db` |
| `CI_DISABLE_HERMES` | unset — `1` no-ops grok modes in CI |
| `CI_SKIP_GROK_X` | unset — skip inline X on daily |

## Commands (`call_intel.py`)

```bash
export COMPETITOR_INTEL_ROOT=~/Documents/Competitor-Intel
export CI_DB_PATH="$COMPETITOR_INTEL_ROOT/data/competitor_intel.db"

uv run python integrations/hermes/call_intel.py status
uv run python integrations/hermes/call_intel.py daily-prod
uv run python integrations/hermes/call_intel.py frequent
uv run python integrations/hermes/call_intel.py grok-refresh
uv run python integrations/hermes/call_intel.py full-sweep
uv run python integrations/hermes/call_intel.py grok-x-ingest
uv run python integrations/hermes/call_intel.py intel
uv run python integrations/hermes/call_intel.py cli -- status
uv run python integrations/hermes/call_intel.py companies 50
uv run python integrations/hermes/call_intel.py grok-x batch --file data/hermes_enrich/grok_x_results.json
```

From repo root: `make daily-prod`, `make grok-refresh`, `make full-sweep`.

## Hermes cron scripts (`--no-agent`)

| Script | Role |
|--------|------|
| `cron_daily_prod.py` | `daily_intel.py` strict prod flags |
| `cron_grok_refresh.py` | `grok_refresh.py` |
| `cron_frequent.py` | `frequent_intel.py` |

Install into `~/.hermes/scripts/` then `hermes cron create` — see [SCHEDULING.md](../../docs/SCHEDULING.md):

```bash
uv run python integrations/hermes/install_hermes_cron_scripts.py
```

## Deprecated (Hermes tree)

| Legacy | Use instead |
|--------|-------------|
| `call_intel.sh` | `call_intel.py` |
| `~/.hermes/.../automation/daily_intel.py` | `call_intel.py daily-prod` |
| System crontab + bash | `hermes cron create` |
| `~/.hermes/.../run_intel.py` | `call_intel.py intel` |
| Direct `python collectors/*.py` in Hermes | `call_intel.py daily-prod` |
