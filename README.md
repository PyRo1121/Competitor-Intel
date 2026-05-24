# Competitor Intelligence

Private-company intelligence pipeline: ingest RSS, GitHub, SEC, jobs, and Hermes Grok/X signals; roll up funding claims; export a daily brief from SQLite.

**v1 focus:** pipeline-first for a solo operator. See [docs/V1_PIPELINE.md](docs/V1_PIPELINE.md).

## Quick start

```bash
cd ~/Documents/Competitor-Intel
uv sync
export CI_DB_PATH="$PWD/data/competitor_intel.db"

make daily-prod          # production cron: strict funding + dedup, no inline Grok
make grok-refresh        # Hermes X batch (separate cron, ~5×/day)
make rollup-all          # company / funding / job rollups when not inlined in daily
make claims-audit-strict
make health-check        # SQLite checks
```

Hermes: `integrations/hermes/call_intel.sh daily` (see [integrations/hermes/README.md](integrations/hermes/README.md)).

CLI: `make cli ARGS="status"` or `uv run python apps/cli/intel.py daily --export`.

## Toolchain

| Layer | Stack |
|-------|--------|
| Collectors / worker | Python 3.12+ via **uv** |
| Database | SQLite (`data/competitor_intel.db`, override `CI_DB_PATH`) |
| Hermes | External agent + `integrations/hermes/` (required for Grok/X) |

## Monorepo

| Path | Role |
|------|------|
| `packages/py-collectors` | Collectors |
| `packages/py-core` | DB, ingest, alerts |
| `apps/worker` | `daily_intel.py`, automation |
| `apps/cli` | `intel.py`, `run_intel.py` |
| `integrations/hermes/` | Hermes HTTP/CLI shim |

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documentation

**[docs/README.md](docs/README.md)** — index

| Start here | |
|------------|--|
| [docs/V1_PIPELINE.md](docs/V1_PIPELINE.md) | **v1 north star** (active) |
| [docs/ROADMAP_PRODUCTION.md](docs/ROADMAP_PRODUCTION.md) | Full audit backlog (v2+) |
| [docs/PIPELINE.md](docs/PIPELINE.md) | Data flow and Makefile |
| [docs/HANDBOOK.md](docs/HANDBOOK.md) | Schema and operations |
