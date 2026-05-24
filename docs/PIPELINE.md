# Operational pipeline

Single reference for how data moves through Competitor Intel, **what to run**, and **where the product is going** after a full-repo deep dive (collectors, core DB, worker, API, dashboard, enterprise shadow, tests/tooling).

> **Status (2026-05-19):** Tracks **0** and **1** are implemented for a **single-operator** deployment (SQLite + WAL, local cron). `daily_intel.py` **aborts on any step failure** unless `--force`. `intel_quality_gate` runs before rollups. API mutations require `CI_API_KEY` (timing-safe compare); CORS is allowlist-only. CI: `.github/workflows/ci.yml` (`make test-cov`, `intel-gate`, `golden-eval`, `bun test`). Sections below that describe pre–Track 0 breakage are **historical** unless marked current.

Daily orchestration: `apps/worker/automation/collector_registry.py` + `apps/worker/daily_intel.py`.

**Related:** **[ROADMAP.md](ROADMAP.md)** (single source of truth — what to build) · [HANDBOOK.md](HANDBOOK.md) · [SCHEDULING.md](SCHEDULING.md) · [JOBS.md](JOBS.md) · [DATA_AUDIT.md](DATA_AUDIT.md) · [AGENT_HANDOFF.md](AGENT_HANDOFF.md) · [File-by-file audit (40 shards)](audit-file-by-file-2026-05-19.md)

---

## Maturity snapshot (2026-05-19)

| Area | Today | SaaS / small-business bar |
|------|--------|---------------------------|
| Signal layer (processor, repair, gate) | Strong — tests, golden set, gate in daily, abort on failure | Widen coverage gate; substring match cleanup in processor |
| Structured rollups (funding, jobs, company) | Working — daily funding; company opt-in | One funding path; Hermes company enrich; SEC/licenses |
| Collectors (~50 modules) | Ingest works; core paths unit-tested | Contract tests + optional network smoke |
| API (Hono + SQLite) | Read surface + **mutation auth** + CORS allowlist; GET still public | Optional read auth; hosted writable DB |
| Dashboard (Svelte 5) | Good dossier/funding/jobs; legacy pages | Unified design system; tests; fix routing |
| CI / lint / format | **GitHub Actions** — compile, test-cov, intel-gate, golden-eval, API smoke | Pre-commit + broader API/integration tests |
| Docker / deploy | Dev compose only | Prod images, healthchecks, secrets |
| Enterprise package | Shadow RSS behind `CI_ENTERPRISE_RSS` (off by default) | Merge or freeze; no double RSS |
| Multi-tenant / auth | None | Out of scope until Tracks 2–3 |

**Verdict:** Solid **internal intel pipeline** for a single operator and SQLite corpus. **Track 2** (search, dossier depth, hosted product) not started; see [ROADMAP.md](ROADMAP.md).

---

## Top code defects (function-level, from 15-area audit)

> **Historical (2026-03 audit):** Many rows below are fixed or superseded. For launch work and verification gates, use **[ROADMAP_PRODUCTION.md](ROADMAP_PRODUCTION.md)**. Re-validate before acting on a row.

These are confirmed logic/runtime issues, not style nits. Highest impact first.

| Area | Location | Defect |
|------|----------|--------|
| Signals | `signal_processor.py` | URL-only payloads classified as Unlabeled because gate checks `extract_signal_text(data)` instead of merged fallback text |
| Signals | `signal_repair.py` | `reclassify_misfunded_events` runs **before** `backfill_funding_amounts` — funding rows demoted to General News before amounts are filled from `data_json` |
| Signals | `signal_company_resolver.py` | Substring company match (`nl in blob`) and synthetic `{slug}.com` domains cause false positives |
| Signals | `load_aliases()` | Global alias cache never refreshes after new companies are added |
| Collectors | `hackernews_collector.py` | **Missing `import sqlite3`** — collector fails at import if scheduled |
| Funding | `enhanced_funding_detector.py` | Inserts `funding_rounds` without `cluster_key`; `prune_legacy_rounds()` deletes them |
| Funding | `big_deals_collector.py` | INSERT columns mismatch `funding_events` schema; runtime ALTER TABLE |
| Funding | `funding_rumor_detector.py` | Valuation scaling bug can write trillion-dollar valuations |
| Jobs | `job_aggregator.py` | Global stale deactivation can mark **other companies'** postings inactive on partial runs |
| API | `db.ts` + `alerts.ts` | Read-only SQLite + POST/DELETE alerts = broken writes |
| API | `discovery.ts` | `POST /add-company` INSERT on read-only DB |
| Worker | `daily_intel.py` | Continues pipeline after parallel ingest fails |
| Worker | ~~`automation/daily_intel.py`~~ | **Removed** — use `apps/worker/daily_intel.py` only |
| Enterprise | `website_collector.py` | ORM columns (`website`, `content_hash`) don't match operational `website_snapshots` |
| Enterprise | `SECCollector` | `filing_date` KeyError — date under `metadata` |
| Dashboard | `search/+page.svelte` | `$derived` query with `bind:value` — broken / non-reactive URL search |
| Dashboard | `jobs/[id]`, `funding/[id]` | Detail pages only load in `onMount` — stale data on client navigation |
| Ingest | `ingest.py` | Check-then-insert dedup races under parallel collectors |
| Alerts | `alert_engine.py` | Hardcoded rules; `min_amount` and keyword rules largely ineffective; DB `alert_rules` unused |

**Scale of audit:** 40 parallel file-by-file shards (collectors C01–C20, worker W01–W06, API A01–A04, dashboard D01–D05, enterprise/scripts/Hermes/tests/stack). Full synthesis: [audit-file-by-file-2026-05-19.md](audit-file-by-file-2026-05-19.md). Dependency/modernization notes below.

---

## Layer 1 — Signals (`raw_signals` → `intelligence_events`)

**Goal:** Every ingested signal becomes a labeled, company-linked event with provenance.

```
raw_signals
    → parse_signal_data (JSON + legacy repr)
    → resolve_company_enhanced (domain, GitHub, title, fuzzy)
    → classify_for_storage (keywords only)
    → intelligence_events (unique source_url, description, label)
```

| Module | Role |
|--------|------|
| `collectors/signal_processor.py` | Orchestration, insert, backfill, relink |
| `collectors/signal_company_resolver.py` | Domain / URL / GitHub company linkage |
| `collectors/signal_repair.py` | Dedupe, relink, mis-tagged funding → General News |
| `collectors/intel_quality_gate.py` | CI metrics gate |
| `scripts/eval_golden_set.py` | Golden-set classifier eval (54 headlines) |

### LLM roles (do not conflate)

| Layer | Runtime | Purpose |
|-------|---------|---------|
| Batch labels | `signal_processor` (keywords) | Deterministic `event_type` on ingest |
| Vectors / rerank | Ollama in monorepo | Embeddings + `unified_search` |
| Agent Q&A | Hermes + Grok | Retrieve via API/CLI, reason over context |
| X ingest | Hermes + Grok → `x_signal_collector` | Native X search JSON → `raw_signals` |

There is **no** in-repo Ollama headline classifier. Agent-level label refinement belongs in Hermes, not the worker. See [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md).

### Quality bar

| Dimension | Bar | Verify |
|-----------|-----|--------|
| Coverage | 100% signals → labeled event | `make intel-gate` orphans=0 |
| Linkage | ≤40% null `company_id`; actionable misses ≤5% | `actionable_null_pct` |
| Classification | ≥90% on golden fixture | `make golden-eval` |
| Provenance | `description`, `confidence`, `source_url`, `raw_signal_id` | integration tests |

### Commands

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
uv sync

make intel-all          # repair + gate + test-cov + golden-eval
make intel-repair       # dedupe, relink, reclassify, amount backfill
make intel-gate         # fail CI if operational truth regresses
make golden-eval        # classifier golden set only (no DB)
make test-cov
```

### Known gaps (signals)

| Issue | Location | Impact |
|-------|----------|--------|
| Gate not in daily sequential | `collector_registry.py` vs `intel_quality_gate.py` | Bad data can ship without failing the job |
| Repair manual only | `Makefile` `intel-repair` | Drift until operator runs repair |
| Duplicate funding → events | `funding_collector` + `big_deals` in `run_intel` **before** `signal_processor` | Duplicate / conflicting `intelligence_events` |
| `raw_signals` dedup index optional | `py-core/db/schema.py`, `ingest.py` | Parallel collectors can race duplicate rows |
| Four copies of amount/heuristics | `signal_processor`, `funding_collector`, `funding_enricher`, `enhanced_funding_detector` | Inconsistent amounts over time |
| Hermes hard path for X | `grok_x_fetcher.py`, `CI_REQUIRE_GROK_X` | Containers/CI fail without `~/.hermes` |
| `general_news_pct` gate | `intel_quality_gate.py` | May fail on real corpus mix (tune threshold or repair) |

**Target daily order (integrity):** parallel ingest → `signal_processor` → **`intel_quality_gate` (fail on breach)** → optional `signal_repair` on schedule → rollups.

---

## Layer 2 — Structured rollups (claims → canonical)

**Goal:** Outlet-level claims merged into corroborated canonical rows. Pattern: **claims per source URL** → **canonical row** → **`corroboration_score`**.

### Funding

```
intelligence_events / raw_signals
        ↓
funding_round_claims → funding_claim_participants → funding_rounds
        ↓
round_participants + participant_source_attributions
```

| Command | Module |
|---------|--------|
| `make funding-rollup` | `collectors/funding_rollup.py` |
| `make funding-enrich-export` / `apply` | Hermes queue for thin investor fields |

**API:** `/api/funding`, `/api/funding/claims`, `/api/funding/rounds/:id`, `/api/funding/investors`

**Code:** `funding_enricher.py`, `funding_aggregator.py`, `funding_investors.py`, `funding_source_trust.py`

### Jobs

| Command | Module |
|---------|--------|
| `make job-rollup` | `collectors/job_rollup.py` |

Pipeline: `collectors/job_tracker.py` → `run_job_pipeline`. See [JOBS.md](JOBS.md).

**API:** `/api/jobs/*`

### Company data (profile, team, products, licenses)

| Domain | Claims | Canonical |
|--------|--------|-----------|
| Profile | `company_profile_claims` | `company_details` |
| Leadership | `team_member_claims` | `team_members` |
| Products | `product_claims` | `products` |
| Regulatory | `license_claims` | `regulatory_licenses` |

| Command | Module |
|---------|--------|
| `make company-data-rollup` | `collectors/company_data_rollup.py` |
| `make rollup-all` | funding + jobs + company |

**Daily opt-in:** `CI_COMPANY_DATA_ROLLUP=1` or `make daily-deep`.

**API:** `/api/team`, `/api/products`, `/api/licenses` (+ `/claims`) — `companyEntities` in `funding.ts`.

**Code:** `packages/py-collectors/collectors/enrichment/company_data/`

### Corroboration

- Per-claim: `source_tier`, `source_weight`, `is_official`
- Per-entity: `report_count`, domain diversity → `corroboration_score`
- Discovery: `team_members` with `corroboration_score ≥ 0.35` only

### Audit

```bash
make claims-audit
```

### Known gaps (rollups)

| Issue | Impact |
|-------|--------|
| Unregistered scripts (`funding_rumor_detector`, `reactive_enrichment`, `enhanced_funding_detector`) | Dead or divergent behavior |
| `job_tracker.py` vs `job_rollup.py` duplicate entrypoints | Confusing ops |
| Three funding layers (`intelligence_events`, `funding_events`, `funding_rounds`) | Unclear ownership |
| Team claims sparse without press/SEC text in events | Empty team tabs |
| Hermes company enrich | `make company-enrich-export` / `apply` (mirror funding) |
| ATS brute-force slug probes | Rate limits / slow at scale |

---

## Daily sequence (current vs target)

### Current (`get_daily_sequential`)

1. Parallel ingest (`PARALLEL_COLLECTORS`)
2. `run_intel.py` extraction: **`funding_collector`**, **`big_deals_collector`** ← dedup risk
3. `website_monitor` → `signal_url_fanout` → jobs stack → **`signal_processor`**
4. discovery → promote → rank → **`funding_rollup`**
5. optional **`company_data_rollup`** (`CI_COMPANY_DATA_ROLLUP`)
6. enrichment, embeddings, alerts, brief

**Problems:** continues after failed parallel batch (`apps/worker/daily_intel.py`); `parallel_collect` PYTHONPATH (ROADMAP X-01).

### Target (integrity-first)

1. Parallel ingest (enforce `idx_raw_signals_dedup` on prod DB)
2. `signal_processor` only for event creation from RSS/X/etc.
3. **`intel_quality_gate`** — exit non-zero on failure
4. `funding_rollup` → optional `company_data_rollup`
5. Rest of tail unchanged
6. Remove or gate `funding_collector` / `big_deals` event inserts if redundant with processor

Frequent tier: keep ending at `funding_rollup` (no full tail).

---

## Application layer (API + dashboard)

### API (`apps/api`)

- **Stack:** Bun, Hono, Zod (partial), `better-sqlite3`, `PRAGMA query_only = ON`
- **Critical:** `POST/DELETE /api/alerts` cannot work on read-only connection — fix or remove writes
- **Security:** open CORS, no auth — required before any non-localhost deploy
- **Tests:** none
- **Lint:** `eslint` script without config in repo

### Dashboard (`apps/dashboard`)

- **Stack:** Svelte 5, TanStack Query (partial), terminal `ci-*` design system
- **Issues:** search page `any`, slug vs id links, settings placeholders, legacy slate pages, no tests
- **Missing:** team/products dossier tabs with corroboration (API exists)

---

## Worker, core DB, alerts

| Issue | Location |
|-------|----------|
| `alerts_sent` no unique `(event_id, channel)` | `schema.py`, `alert_engine.py` |
| `alert_rules` table unused in Python path | `alert_engine.py` vs API |
| `insert_raw_signal_dedup` no `IntegrityError` handling | `ingest.py` |
| `enterprise_collect` double RSS when `CI_ENTERPRISE_RSS=1` | `daily_intel.py` |
| Env flags fragmented | `CI_*` vs `utils/config.py` |
| No pytest for `alert_engine` or `daily_intel` ordering | `tests/` |

**Canonical daily entrypoint:** `apps/worker/daily_intel.py` only.

---

## Enterprise shadow (optional)

`packages/py-enterprise/` duplicates operational collectors (RSS, SEC, jobs, reports). **Not** the daily path.

| Control | Purpose |
|---------|---------|
| `CI_ENTERPRISE_RSS=1` | Shadow SQLAlchemy RSS (avoid with operational RSS) |
| `make enterprise-rss` | Dry-run |

**Decision needed:** freeze package, port collectors into `py-collectors`, or delete. Alembic at repo root is incomplete (`alembic.ini` without `versions/`).

---

## Engineering platform (tests, lint, CI)

### What exists

| Tool | Config | Enforced |
|------|--------|----------|
| pytest | `pyproject.toml` | `make test`, `make test-cov` |
| coverage 80% | 5 modules only | `make test-cov` |
| ruff | `[tool.ruff]` | **No** |
| mypy | dev dep | **No** `[tool.mypy]` |
| pre-commit | dev dep | **No** `.pre-commit-config.yaml` |
| pip-audit | dev dep | **No** |
| svelte-check | dashboard | `make dashboard-check` |
| GitHub Actions | — | **None** |

### What to add (Track 3)

```text
.github/workflows/ci.yml
  uv sync → ruff check → make test → make test-cov → make golden-eval
  → cd apps/api && bun test (new)
  → cd apps/dashboard && bun run check
  → optional pip-audit / bun audit

.pre-commit-config.yaml
  ruff, ruff-format, trailing-whitespace

Makefile
  lint: ruff + api eslint + dashboard check
```

---

## Backlog & tracks

Prioritized backlog (P0–P4, X-01–X-14), implementation tracks, and checklists: **[ROADMAP.md](ROADMAP.md)**.

---

## Roadmap — path forward

**Implementation plan, tracks, checklists, and unified backlog (P0–P4, X-01–X-14):** see **[ROADMAP.md](ROADMAP.md)** — single source of truth. This file keeps operational detail (layers, commands, defect tables for reference).

---

## Hermes enrichment (not local LLM)

| Step | Command |
|------|---------|
| Event labels / `company_id` | `make enrich-queue-export` → `enrich-queue-apply` |
| Funding investors & deal fields | `make funding-enrich-export` → `funding-enrich-apply` |
| Company profile / product claims | `make company-enrich-export` → `company-enrich-apply` |
| Deterministic relink | `make relink-actionable` |
| X batch | `make grok-refresh` / `call_intel.sh grok-x-ingest` |
| On-demand full refresh | `make full-sweep` — full `daily` first, enriched X queries, then X ingest |

---

## Makefile quick reference

| Target | What |
|--------|------|
| `full-sweep` | Daily (`CI_SKIP_GROK_X`) → enriched queries → grok-refresh → funding rollup |
| `intel-repair` / `intel-gate` / `intel-all` | Signal layer |
| `golden-eval` | Classifier golden set |
| `funding-rollup` / `job-rollup` / `company-data-rollup` | Structured rollups |
| `rollup-all` | All three rollups |
| `claims-audit` | Claim/canonical counts |
| `daily-deep` | Daily + company rollup |
| `test` / `test-cov` / `test-all` | Python tests |
| `dashboard-check` | svelte-check |
| `compile` | Python bytecode sanity |

Legacy aliases `phase-a-*` and `phase-b-*` still point at the same targets.

---

## How this doc stays current

1. Check off work in **[ROADMAP.md](ROADMAP.md)**; update **Maturity snapshot** here when a track completes.
2. Run `make intel-gate` + `make claims-audit` before releases.
3. Put new collectors only in `collector_registry.py` + `docs/HANDBOOK.md` feed table.
4. Do not add `scripts/phase_*` or duplicate rollup entrypoints — extend `collectors/*_rollup.py`.

## Dependency & stack modernization (May 2026)

| Layer | Current | Notes |
|-------|---------|--------|
| Python | `>=3.11`, lock on 3.14.x | Align CI/docs with chosen runtime |
| Bun API | `better-sqlite3` + `query_only` | Bun 1.2+ has native `bun:sqlite` — evaluate migration for read-heavy API |
| Hono | 4.x | No auth middleware yet — add before public deploy |
| Svelte / Kit | Svelte 5, partial TanStack Query | Prefer accessor pattern + SSR prefetch per TanStack v5 docs |
| httpx | `>=0.28.1`, locked at floor in `uv.lock` | Bump floor after `pip-audit`; watch CVE-2025-43859 (h11) |
| feedparser | 6.0.12 | Stay on 6.0.x; monitor advisories |
| SQLAlchemy | Enterprise only (`2.0.49` resolved) | Operational path stays raw SQLite + migrations |
| Dev tools | ruff/mypy/pre-commit/pip-audit declared, not enforced | Track 3 wires these |

**Install graph:** Root workspace always pulls `competitor-intel` (enterprise) even when only running collectors — heavier than operational docs imply. Consider optional extras: `operational` vs `enterprise`.

---

## Audit evidence

40-shard file-by-file census (2026-05-19): [audit-file-by-file-2026-05-19.md](audit-file-by-file-2026-05-19.md). Backlog derived from it lives in [ROADMAP.md](ROADMAP.md).
