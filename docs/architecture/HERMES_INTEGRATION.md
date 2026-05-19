# Hermes integration

Competitor Intel is a **standalone product**. Hermes agents must not import Python modules from this repo directly. Use the HTTP API or the `competitor-intel` CLI.

## Integration model

```
Hermes agent (Grok / Claude / etc.)
    │
    ├─► HTTP  GET/POST  →  apps/api  (port 3000)
    │
    └─► Shell competitor-intel / intel.py  →  apps/cli + apps/worker
```

## HTTP API (preferred)

Base URL (local): `http://localhost:3000`

| Endpoint | Use |
|----------|-----|
| `GET /api/status` | Health + row counts |
| `GET /api/companies` | Company list |
| `GET /api/companies/:slug` | Company profile |
| `GET /api/signals` | Raw signals |
| `GET /api/events` | Intelligence events |
| `GET /api/trending` | Momentum |
| `POST /api/jobs/...` | Trigger jobs (if enabled) |

Example:

```bash
curl -s http://localhost:3000/api/status | jq .
```

Set `CI_DB_PATH` on the API process so it reads the same SQLite file as workers.

## CLI (batch / cron)

From monorepo root with venv and PYTHONPATH:

```bash
export PYTHONPATH="packages/py-collectors:packages/py-core:apps/worker:apps/cli:packages/py-enterprise/src"
export CI_DB_PATH="$PWD/data/competitor_intel.db"

# Full daily pipeline
python apps/worker/daily_intel.py

# Signal processing only
python apps/cli/run_intel.py

# Enterprise CLI (when wired)
competitor-intel collect -c rss
```

See [integrations/hermes/call_intel.sh](../../integrations/hermes/call_intel.sh).

## X / Grok signals

X/Twitter is **not** scraped via REST from this host. Hermes/Grok runs native X search; Python only persists structured JSON via:

- `collectors/x_monitor.py` — prompt templates
- `collectors/x_signal_collector.py` — deduped `raw_signals` inserts

Agent workflow:

1. Hermes calls Grok with `get_x_query_prompt(...)`.
2. Agent returns JSON post arrays to a small ingest script or future `POST /api/ingest/x` endpoint.
3. Worker processes signals on next `run_intel.py` pass.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `CI_DB_PATH` | Shared SQLite path |
| `CI_API_URL` | Hermes shim default API base |
| `DISCORD_WEBHOOK_URL` | Optional alerts |

## Shim location

Hermes-side thin client: `integrations/hermes/` (example shell script only). Copy or symlink into your Hermes agent config; do not embed the monorepo.

## Migration note

Legacy path: `~/.hermes/agents/competitor_intel/` (frozen; see `MIGRATED.md`).

New path: `~/Documents/Competitor-Intel/`.

### Deprecated in Hermes tree

Do not run from `~/.hermes/agents/competitor_intel/`:

- `run_intel.py`, `intel.py`, `automation/daily_intel.py`
- Any `python collectors/*.py` with Hermes `sys.path` hacks

Use [`integrations/hermes/call_intel.sh`](../../integrations/hermes/call_intel.sh) or monorepo `make daily` / `make intel`. Operator summary: [docs/HERMES_INTEGRATION.md](../HERMES_INTEGRATION.md).
