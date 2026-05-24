# Hermes → Competitor Intel

Hermes agents must **not** import Python from `~/.hermes/agents/competitor_intel/`. Use this monorepo via **`call_intel.sh`** only.

**Reference:** [docs/architecture/HERMES_INTEGRATION.md](../../docs/architecture/HERMES_INTEGRATION.md)

## Environment

| Variable | Default |
|----------|---------|
| `COMPETITOR_INTEL_ROOT` | repo root (auto from script path) |
| `CI_DB_PATH` | `$MONOREPO/data/competitor_intel.db` |
| `CI_DISABLE_HERMES` | unset — `1` no-ops grok modes in CI |
| `CI_SKIP_GROK_X` | unset — skip inline X on daily |
| `CI_X_PROVIDER` | `grok` or `xurl` |

## Commands (`call_intel.sh`)

```bash
export COMPETITOR_INTEL_ROOT=~/Documents/Competitor-Intel
export CI_DB_PATH="$COMPETITOR_INTEL_ROOT/data/competitor_intel.db"

./call_intel.sh status
./call_intel.sh daily-prod
./call_intel.sh frequent
./call_intel.sh grok-refresh
./call_intel.sh full-sweep
./call_intel.sh grok-x-ingest
./call_intel.sh intel
./call_intel.sh cli -- status
./call_intel.sh companies 50
./call_intel.sh grok-x batch --file data/hermes_enrich/grok_x_results.json
```

From repo root: `make daily-prod`, `make grok-refresh`, `make full-sweep`.

## Deprecated (Hermes tree)

| Legacy | Use instead |
|--------|-------------|
| `~/.hermes/.../automation/daily_intel.py` | `call_intel.sh daily-prod` |
| `~/.hermes/.../run_intel.py` | `call_intel.sh intel` |
| `~/.hermes/.../intel.py` | `call_intel.sh cli` |
| Direct `python collectors/*.py` in Hermes | `call_intel.sh daily-prod` |
