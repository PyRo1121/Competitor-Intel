# Competitor Intelligence

Standalone competitive intelligence platform: ingest RSS, GitHub, SEC, Product Hunt, and structured X signals; score companies; expose REST API and Svelte dashboard.

## Toolchain

| Stack | Tool | Notes |
|-------|------|-------|
| Python | [uv](https://docs.astral.sh/uv/) | Workspace with 3 packages under `packages/` |
| API | [Bun](https://bun.sh/) | `apps/api` — Hono + TypeScript |
| Dashboard | Bun | `apps/dashboard` — Svelte 5 + Vite |

## Quick start

```bash
cd ~/Documents/Competitor-Intel

# Python workspace (creates .venv + uv.lock)
uv sync

# Optional: copy existing DB from Hermes agent tree
# cp ~/.hermes/agents/competitor_intel/competitor_intel.db data/

export CI_DB_PATH="$PWD/data/competitor_intel.db"

# Daily pipeline
uv run python apps/worker/daily_intel.py

# Signal processing / reports
uv run python apps/cli/run_intel.py

# Enterprise CLI
uv run competitor-intel --help

# API (port 3000)
cd apps/api && bun install && bun run dev

# Dashboard (port 5173)
cd apps/dashboard && bun install && bun run dev
```

## Makefile shortcuts

```bash
make sync          # uv sync
make daily         # daily_intel pipeline
make api-dev       # bun API dev server
make dashboard-dev # bun Vite dev server
make compile       # python compileall via uv
make test          # pytest via uv
```

## Database

Default: `data/competitor_intel.db` (gitignored). Override with `CI_DB_PATH`.

Regenerate: init schema then run `make daily` — collectors backfill over time.

## Monorepo layout

| Path | Role |
|------|------|
| `packages/py-core` | `db`, `utils`, `alerts`, `ci_paths` |
| `packages/py-collectors` | `collectors` package (operational ingest) |
| `packages/py-enterprise` | `competitor_intel` SQLAlchemy package |
| `apps/api` | Bun read API |
| `apps/dashboard` | Svelte dashboard |
| `apps/worker` | Daily pipeline scripts |
| `apps/cli` | Operational CLI scripts |

See [docs/architecture/MONOREPO.md](docs/architecture/MONOREPO.md).

## Hermes integration

HTTP or CLI only — no embedded imports. See [docs/architecture/HERMES_INTEGRATION.md](docs/architecture/HERMES_INTEGRATION.md).

## Docs

- [Handbook](docs/HANDBOOK.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Python vs Rust](docs/architecture/PYTHON_VS_RUST.md)

## Docker

```bash
docker compose up api
docker compose --profile worker run worker
```
