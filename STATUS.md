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
| CI/CD + collector tests | 🟡 85% | Local `make test-cov` + `make phase-a-eval`; no GHA (by choice) |
| Phase A pipeline (processor, API semantic, migrations) | ✅ 100% | `make phase-a-gate` PASS; golden 54 @ ≥90%; keyword classify only (no `signal_llm_router`); see `docs/PHASE_A_WORLD_CLASS.md` |
| Phase B funding (claims → rounds → investors) | 🟡 70% | Schema + `funding_enricher` / aggregator wired; `make phase-b-funding` + daily step; investor parsing still thin on many claims |
| Phase B jobs (claims → postings → skills) | 🟡 75% | Greenhouse/Lever/Ashby ingest; `make phase-b-jobs`; granular API at `/api/jobs/*` |
| Hermes Grok X ingest | ✅ 100% | OAuth `x_search`; `grok_x_fetcher.py`, `smoke-hermes-x`, `daily_intel` auto-fetch flags |

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
make phase-a-repair && make phase-a-gate && make test-cov && make phase-a-eval
```

## Phase A (2026-05-19)

- 1139 signals → 1198 events, 0 orphans, 0 unprocessed, 0 dup `raw_signal_id`
- ~36% `company_id` null (industry/creator news; `actionable_null_pct` = 0%)
- 146 mis-tagged Funding rows reclassified to General News
- Classifier: inflected keywords, partnership/acquisition verbs, margin tie-break

## Phase B (2026-05-19)

- Three-layer model: `funding_round_claims` → `funding_rounds` → `round_participants` / `investor_firms`
- `scripts/phase_b_populate_funding.py` runs in daily pipeline after `signal_processor`
- Docs: `docs/PHASE_B.md`; tests: `tests/test_funding_corroboration.py`, `tests/test_funding_enricher.py`

## Discovery pipeline (2026-05-19)

- `candidate_discovery` → `auto_promote` → `company_ranker` in daily + frequent + `intel.py discover|promote|rank`
- API: `/api/discovery/candidates`, `/api/scoring`, companies `sort=score`, status `pendingCandidates`
- Dashboard: `/discovery`, home top-attention strip
- Tests: `tests/test_discovery_pipeline.py`
- `phase_b_populate_company` removed from default daily (use `make phase-b-company` only)

## Remaining gaps (non-blocking)

1. Enterprise SQLAlchemy collectors optional wire to daily
2. Hermes production cron → `integrations/hermes/call_intel.sh`
3. Phase B depth: richer investor parsing, optional company web enrichment
