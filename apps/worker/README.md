# Worker app

Daily intelligence pipeline and batch scripts.

## Entry point

```bash
# From monorepo root
export PYTHONPATH="packages/py-collectors:packages/py-core:apps/worker:apps/cli:packages/py-enterprise/src"
export CI_DB_PATH="$PWD/data/competitor_intel.db"

python apps/worker/daily_intel.py
```

## Layout

| Path | Purpose |
|------|---------|
| `daily_intel.py` | Main daily orchestrator |
| `automation/` | parallel_collect, collector_registry, run_utils |
| `run_intel.py` | (in apps/cli) signal processing |
| `*.py` | Reports, embeddings, Discord helpers |

## Notes

Scripts still reference some legacy `~/.hermes/...` paths — set `CI_DB_PATH` or follow import-path follow-ups in the migration report.
