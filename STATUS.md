# Competitor Intel — refactor status

**Updated:** 2026-05-19  
**Canonical repo:** `~/Documents/Competitor-Intel`  
**Legacy (frozen):** `~/.hermes/agents/competitor_intel` — see `MIGRATED.md` (call `call_intel.sh` only)

## Progress (~92% structural refactor)

| Area | Status | Notes |
|------|--------|-------|
| Monorepo layout (`apps/`, `packages/`, `infra/`) | ✅ 100% | Documented in `docs/architecture/MONOREPO.md` |
| uv workspace + lockfile | ✅ 100% | `uv sync` clean; do not overwrite `uv.lock` from Hermes |
| Bun API + dashboard | ✅ 95% | `apps/api`, `apps/dashboard`; aligned with Hermes |
| `ci_paths` / DB path | ✅ 100% | `CI_DB_PATH` → `data/competitor_intel.db` |
| Collectors → `packages/py-collectors` | ✅ 100% | `sources_registry.py` synced; `crunchbase_collector` uses `general_startup` |
| Automation → `apps/worker/automation` | ✅ 100% | Monorepo `parents[3]` / `ci_paths` kept (not Hermes hardcoded paths) |
| Core (`db`, `utils`, `alerts`) → `py-core` | ✅ 100% | Schema via `ci_paths` |
| CLI / worker entrypoints | ✅ 100% | `apps/cli`, `apps/worker/daily_intel.py` |
| Hermes integration shim | ✅ 100% | `integrations/hermes/call_intel.sh` — daily, intel, cli, status |
| Production SQLite migration | ✅ 100% | `data/competitor_intel.db` present (~18 MB) |
| Decommission Hermes agent tree | ✅ 90% | `MIGRATED.md` updated; Hermes repo not committed |
| Enterprise package wired to daily | ⬜ 0% | Roadmap — operational collectors remain primary |
| CI/CD + collector tests | ⬜ 15% | `tests/` present; no pipeline yet |

## Sync summary (2026-05-19 migration pass)

**Synced from Hermes**

- `packages/py-collectors/collectors/sources_registry.py` (expanded feed catalog)
- `crunchbase_collector.py` category → `general_startup` (matches registry aliases)

**Kept monorepo-specific (not overwritten)**

- `continuous_ingest.py` — `ci_paths.ensure_app_paths()`
- `collector_registry.py` — `BASE = parents[3]`
- `enterprise_collect.py` — monorepo `BASE`
- `packages/py-core/db/schema.py`, `ci_paths.py`
- `create_intelligence_events.py`, `daily_brief.py` — `ci_paths` / `EXPORTS_DIR`

**Already identical:** enrichment/, `ollama_client.py`, `momentum_detector.py`, api/, dashboard/, most collectors.

## Quick commands

```bash
cd ~/Documents/Competitor-Intel
export CI_DB_PATH="$PWD/data/competitor_intel.db"
uv sync
uv run python -m compileall -q packages apps/worker apps/cli tests
make daily   # or integrations/hermes/call_intel.sh daily
```

## Remaining gaps

1. Wire enterprise `competitor_intel` SQLAlchemy collectors into `daily_intel.py`
2. GitHub Actions (or similar) for `make compile` + `make test`
3. Point Hermes agent configs at `call_intel.sh` in production cron
