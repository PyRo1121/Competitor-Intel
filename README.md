# Competitor Intelligence

Private-company intelligence platform: ingest RSS, GitHub, SEC, jobs, and Grok/X signals; roll up funding and hiring claims; expose a REST API and Svelte dossier for due diligence.

## Quick start

```bash
cd ~/Documents/Competitor-Intel
uv sync
export CI_DB_PATH="$PWD/data/competitor_intel.db"

make full-sweep         # on-demand: daily first, then enriched X search + ingest
make daily              # scheduled full pipeline (X fetch only if batch stale)
make intel-gate         # signal quality gate
make api-dev            # API :3000
make dashboard-dev      # UI :5173
```

Hermes: `integrations/hermes/call_intel.sh daily` (see [integrations/hermes/README.md](integrations/hermes/README.md)).

## Toolchain

| Layer | Stack |
|-------|--------|
| Collectors / worker | Python 3.12+ via **uv** |
| API | **Bun** + Hono |
| Dashboard | **Bun** + Svelte 5 |
| Database | SQLite (`data/competitor_intel.db`, override `CI_DB_PATH`) |

## Monorepo

| Path | Role |
|------|------|
| `packages/py-collectors` | Collectors |
| `packages/py-core` | DB, ingest, alerts |
| `packages/py-enterprise` | SQLAlchemy (frozen — not in daily) |
| `apps/worker` | `daily_intel.py`, automation |
| `apps/api`, `apps/dashboard` | Read surface |
| `apps/cli` | `intel.py`, `run_intel.py` |

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documentation

**[docs/README.md](docs/README.md)** — index

| Start here | |
|------------|--|
| [docs/ROADMAP.md](docs/ROADMAP.md) | What to build (single source of truth) |
| [docs/PIPELINE.md](docs/PIPELINE.md) | Data flow and Makefile |
| [docs/HANDBOOK.md](docs/HANDBOOK.md) | Schema and operations |

## Bare-metal health (API must be running)

```bash
make api-dev          # terminal 1
make health-check     # terminal 2 — SQLite + /health + /api/status
```
