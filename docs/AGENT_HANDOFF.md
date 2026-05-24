# Agent handoff

Paste this when starting a new session in `~/Documents/Competitor-Intel`.

## Authority

| Doc | Role |
|-----|------|
| [V1_PIPELINE.md](V1_PIPELINE.md) | **Active north star** — pipeline-first solo operator |
| [ROADMAP.md](ROADMAP.md) | What to build — tracks, backlog IDs |
| [PIPELINE.md](PIPELINE.md) | How data flows, commands |
| [HANDBOOK.md](HANDBOOK.md) | Schema, feeds, conventions |
| [README.md](../README.md) | Doc index |

## Workspace

- **Edit only:** `~/Documents/Competitor-Intel`
- **Do not edit:** `~/.hermes/agents/competitor_intel/` — see [MIGRATED.md](../MIGRATED.md)

## Product

Private-company intel: collectors → SQLite → rollups → CLI brief export. Hermes is a **consumer** via `integrations/hermes/call_intel.sh`, not the codebase host.

Bun API, Svelte dashboard, and `py-enterprise` were **removed** (v1 pipeline-only). See git history for v2 read-surface restore.

## Entrypoints

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make daily-prod                               # apps/worker/daily_intel.py (strict)
make grok-refresh                             # X batch (separate cron)
integrations/hermes/call_intel.sh daily       # same pipeline from Hermes
make cli ARGS="status"                        # apps/cli/intel.py
```

## Layout

| Path | Role |
|------|------|
| `packages/py-collectors/collectors/` | Ingest + rollups |
| `packages/py-core/` | `db/`, `utils/http.py`, `ci_paths.py` |
| `apps/worker/daily_intel.py` | **Only** daily orchestrator |
| `apps/worker/automation/` | `collector_registry.py`, `parallel_collect.py` |
| `apps/cli/` | `intel.py`, `run_intel.py` |
| `data/competitor_intel.db` | Production DB (`CI_DB_PATH`) |

Root symlinks: `collectors`, `automation`, `intel.py`, `run_intel.py` — legacy subprocess paths.

## Toolchain

- Python: `uv sync` only (no pip); workspace: `py-core`, `py-collectors`

## Conventions

- Ingest: `insert_raw_signal_dedup`
- HTTP: `utils.http`
- X: Hermes Grok → `x_signal_collector` (no X API keys in repo)
- Ollama: embeddings + rerank only — not headline classification

## Verify

```bash
uv sync
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make v1-check
```

## Current priority

**v1** in [V1_PIPELINE.md](V1_PIPELINE.md): green `make daily-prod` week, then optional v2 read UI from git history.

## Out of scope unless asked

- Commits under `~/.hermes/`
- New top-level markdown plans (update ROADMAP instead)
- Restoring deleted API/dashboard without explicit ask
