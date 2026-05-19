# Hermes → Competitor Intel (thin client)

Hermes agents should **not** import Python from the old agent tree. Point agents at this monorepo via HTTP or shell.

## Quick calls

```bash
# API health
./call_intel.sh status

# Company list
./call_intel.sh companies 50

# Run daily pipeline (requires venv + deps on host)
./call_intel.sh daily
```

## Configuration

| Env | Default |
|-----|---------|
| `COMPETITOR_INTEL_ROOT` | `~/Documents/Competitor-Intel` |
| `CI_API_URL` | `http://localhost:3000` |
| `CI_DB_PATH` | `$MONOREPO/data/competitor_intel.db` |

Full guide: [docs/architecture/HERMES_INTEGRATION.md](../../docs/architecture/HERMES_INTEGRATION.md)
