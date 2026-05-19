# Hermes integration (operator guide)

Hermes agents must **not** import Python from `~/.hermes/agents/competitor_intel/` or run collectors there. Use the monorepo via the thin shell shim only.

**Canonical product:** `~/Documents/Competitor-Intel`  
**Shim:** [`integrations/hermes/call_intel.sh`](../integrations/hermes/call_intel.sh)

Full API/CLI reference: [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md).

## Single entry point

```bash
export COMPETITOR_INTEL_ROOT=~/Documents/Competitor-Intel
export CI_DB_PATH="$COMPETITOR_INTEL_ROOT/data/competitor_intel.db"

# Daily ingest + scoring pipeline
~/Documents/Competitor-Intel/integrations/hermes/call_intel.sh daily

# Signal processing / reports only
~/Documents/Competitor-Intel/integrations/hermes/call_intel.sh intel

# API health (API must be running)
~/Documents/Competitor-Intel/integrations/hermes/call_intel.sh status
```

Equivalent from monorepo root:

```bash
cd ~/Documents/Competitor-Intel
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make daily    # same as call_intel.sh daily
make intel    # same as call_intel.sh intel
```

## Deprecated (do not use from Hermes)

| Legacy path | Use instead |
|-------------|-------------|
| `~/.hermes/agents/competitor_intel/run_intel.py` | `call_intel.sh intel` |
| `~/.hermes/agents/competitor_intel/intel.py` | `call_intel.sh cli` |
| `~/.hermes/agents/competitor_intel/automation/daily_intel.py` | `call_intel.sh daily` |
| Direct `python collectors/*.py` in Hermes tree | Monorepo `make daily` or `call_intel.sh daily` |

## Database

Default SQLite: `data/competitor_intel.db` (override with `CI_DB_PATH`).

To copy legacy data once:

```bash
cp ~/.hermes/agents/competitor_intel/competitor_intel.db ~/Documents/Competitor-Intel/data/
```

## Environment

| Variable | Default |
|----------|---------|
| `COMPETITOR_INTEL_ROOT` | `~/Documents/Competitor-Intel` |
| `CI_DB_PATH` | `$COMPETITOR_INTEL_ROOT/data/competitor_intel.db` |
| `CI_API_URL` | `http://localhost:3000` |
