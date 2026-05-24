# Agent handoff

Paste this when starting a new session in `~/Documents/Competitor-Intel`.

## Authority

| Doc | Role |
|-----|------|
| [ROADMAP.md](ROADMAP.md) | **What to build** — tracks, backlog IDs, progress log |
| [PIPELINE.md](PIPELINE.md) | How data flows, commands |
| [HANDBOOK.md](HANDBOOK.md) | Schema, feeds, conventions |
| [README.md](README.md) | Doc index |

Evidence: [audit-file-by-file-2026-05-19.md](audit-file-by-file-2026-05-19.md).

## Workspace

- **Edit only:** `~/Documents/Competitor-Intel`
- **Do not edit:** `~/.hermes/agents/competitor_intel/` — see [MIGRATED.md](../MIGRATED.md)

## Product

Private-company intel: collectors → SQLite → rollups → Bun API → Svelte dashboard. Hermes is a **consumer** via `integrations/hermes/call_intel.sh`, not the codebase host.

## Entrypoints

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make daily                                    # apps/worker/daily_intel.py
make intel-all                                # repair + gate + tests
integrations/hermes/call_intel.sh daily       # same pipeline from Hermes
```

## Layout

| Path | Role |
|------|------|
| `packages/py-collectors/collectors/` | Ingest + rollups |
| `packages/py-core/` | `db/`, `utils/http.py`, `ci_paths.py` |
| `apps/worker/daily_intel.py` | **Only** daily orchestrator |
| `apps/worker/automation/` | `collector_registry.py`, `parallel_collect.py` |
| `apps/cli/` | `intel.py`, `run_intel.py` |
| `apps/api/`, `apps/dashboard/` | Bun apps |
| `data/competitor_intel.db` | Production DB (`CI_DB_PATH`) |

Root symlinks: `collectors`, `automation`, `intel.py`, `run_intel.py` — legacy subprocess paths.

## Toolchain

- Python: `uv sync` only (no pip)
- JS: Bun in `apps/api` and `apps/dashboard`

## Conventions

- Ingest: `insert_raw_signal_dedup`
- HTTP: `utils.http`
- X: Hermes Grok → `x_signal_collector` (no X API keys in repo)
- Ollama: embeddings + rerank only — not headline classification

## Verify

```bash
uv sync
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make compile
make test
make intel-gate
```

## Current priority

**Track 0** in [ROADMAP.md](ROADMAP.md): pipeline fail-fast, dedup, single funding→events path, API safety. Do not start Track 2 UI polish before Track 0.

## Out of scope unless asked

- Enterprise package in daily (`py-enterprise` frozen)
- Commits under `~/.hermes/`
- New top-level markdown plans (update ROADMAP instead)
