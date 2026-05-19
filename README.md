# Competitor Intelligence

Standalone competitive intelligence platform: ingest RSS, GitHub, SEC, Product Hunt, and structured X signals; score companies; expose REST API and Svelte dashboard.

Migrated from the Hermes agent tree into a product monorepo at `~/Documents/Competitor-Intel`.

## Quick start

```bash
cd ~/Documents/Competitor-Intel

# Python env (editable enterprise package + PYTHONPATH for operational code)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

export PYTHONPATH="packages/py-collectors:packages/py-core:apps/worker:apps/cli:${PYTHONPATH}"
export CI_DB_PATH="$PWD/data/competitor_intel.db"

# Initialize empty DB (first run) — or copy existing DB into data/
mkdir -p data
python -c "from db.schema import init_db; init_db()" 2>/dev/null || \
  python packages/py-core/db/schema.py

# Daily pipeline
python apps/worker/daily_intel.py

# API (port 3000)
cd apps/api && bun install && bun run dev

# Dashboard
cd apps/dashboard && bun install && bun run dev
```

## Database

The SQLite file is **not** committed. Default path: `data/competitor_intel.db` (override with `CI_DB_PATH`).

To migrate data from the Hermes copy:

```bash
cp ~/.hermes/agents/competitor_intel/competitor_intel.db ~/Documents/Competitor-Intel/data/
```

To regenerate from scratch: run `apps/worker/daily_intel.py` after schema init (collectors backfill over time).

## Monorepo layout

| Path | Role |
|------|------|
| `apps/api` | Hono + Bun read API over SQLite |
| `apps/dashboard` | Svelte 5 dashboard |
| `apps/worker` | Daily pipeline (`daily_intel.py`, automation/) |
| `apps/cli` | `intel.py`, `run_intel.py` operational CLI |
| `packages/py-collectors` | RSS, GitHub, SEC, enrichment collectors |
| `packages/py-core` | `db/`, `utils/`, `alerts/`, shared Python |
| `packages/py-enterprise` | SQLAlchemy `competitor_intel` package (future) |
| `integrations/hermes` | Thin HTTP/CLI client for Hermes agents |
| `docs/` | Handbook, architecture, integration guides |

See [docs/architecture/MONOREPO.md](docs/architecture/MONOREPO.md).

## Hermes integration

Hermes agents call Competitor Intel via HTTP or CLI — no embedded Python imports. See [docs/architecture/HERMES_INTEGRATION.md](docs/architecture/HERMES_INTEGRATION.md).

## Docs

- [Handbook](docs/HANDBOOK.md) — operational guide for agents
- [Architecture](docs/ARCHITECTURE.md) — data flow and dual-stack notes
- [Python vs Rust](docs/architecture/PYTHON_VS_RUST.md) — backend technology decision

## Docker (stub)

```bash
docker compose up api worker
```

See `docker-compose.yml` for services and volume mounts.
