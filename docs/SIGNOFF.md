# Track sign-off registry

**Authority:** Each track must pass its sign-off block before the next track starts.  
**Rule:** Check every box with evidence (command output or PR link). Residuals stay listed until closed or explicitly waived.

**Related:** [ROADMAP.md](ROADMAP.md) (task IDs) · [PIPELINE.md](PIPELINE.md) (how to run) · Progress log ROADMAP §12

---

## How to sign off

1. Run the **Verification commands** for that track (all must exit 0 unless noted).
2. Confirm every **Checklist** row (code + behavior matches exit criteria).
3. Record **Date**, **Verifier** (human or agent session id), and any **Residuals** (waived or blocking).
4. Update ROADMAP §12 progress log with the milestone line.

---

## Track 0 — Pipeline & API safety

**Exit criteria (ROADMAP):** Daily job fails on bad ingest; API does not advertise broken mutations; dedup index enforced.

**Scope:** Single-operator SQLite deployment; not hosted multi-tenant.

| ID | Requirement | Evidence |
|----|-------------|----------|
| P0-1 | API RW path for alerts/discovery or read-only surface documented | `apps/api/src/db.ts`, routes |
| P0-2 | Mutation auth (`CI_API_KEY`) + CORS allowlist | `middleware/auth.ts`, `apps/api/test/auth.test.ts` |
| P0-3 | Daily registry excludes direct `funding_collector` / pre-processor event writes | `collector_registry.py`, `run_intel.py` |
| P0-4 | `idx_raw_signals_dedup` + `IntegrityError` on ingest | `db/ingest.py`, `make migrate-dedup` |
| P0-5 | Daily aborts on any step failure unless `--force` | `daily_intel.py`, `tests/test_daily_intel_abort.py` |
| X-01 | `parallel_collect` PYTHONPATH | `run_utils.py` |
| X-03 | HN collector `sqlite3` import | `hackernews_collector.py` |
| X-04 | Jobs stale scope by `company_id` | `jobs/job_aggregator.py` |

### Verification commands

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"   # or CI test DB
make migrate-dedup
uv run pytest tests/test_daily_intel_abort.py tests/test_collector_registry.py -q
cd apps/api && CI_API_KEY=test-key CI_API_CORS_ORIGINS=http://localhost:5173 bun test
```

### Sign-off

| Field | Value |
|-------|--------|
| **Status** | **SIGNED** |
| **Date** | 2026-05-19 |
| **Verifier** | Multi-agent audit + enterprise hardening session |
| **Gate command** | `make enterprise-check` (includes API smoke) |

**Residuals (waived for T0 scope, not blockers for T1):**

- GET `/api/*` remains public (local LAN dossier use).
- Legacy CLI collectors can still write events unless `CI_STRICT_PIPELINE=1`.
- ROADMAP §6 unified backlog table is stale; use this file + ROADMAP §5 checkboxes instead.

---

## Track 1 — Data integrity & rollups

**Exit criteria (ROADMAP):** One funding→events path in daily; gate runs in daily; repair scheduled; rollups trustworthy.

| ID | Requirement | Evidence |
|----|-------------|----------|
| P1-1 | `intel_quality_gate` after processor in daily | `collector_registry.py` order |
| P1-2 | `signal_repair` before gate in daily | registry + `SCHEDULING.md` |
| P1-3 | Shared `funding_parse.py` | module + call sites |
| P1-4 | All collector `__main__` registered | `test_collector_registry.py` |
| P1-5 | `big_deals` schema via migrations | `migrations.py` |
| P1-6 | Alerts dedup + `alert_rules` | `alert_engine.py`, reserve-before-send |
| P1-8 | Hermes via env; off in CI | `integrations/hermes/` |
| X-05 | Classify on merged text | `signal_processor.py` |
| X-06 | Repair order: amounts before reclassify | `signal_repair.py` |
| — | `fuzzy_match_company` word boundaries | `signal_processor.py` + tests |
| — | Strict claims audit for CI | `scripts/claims_audit.py`, `make claims-audit-strict` |

### Verification commands

```bash
make intel-all          # repair + gate + test-cov + golden-eval
make claims-audit-strict
uv run pytest tests/test_signal_processor_behavior.py tests/test_alert_engine.py -q
```

### Sign-off

| Field | Value |
|-------|--------|
| **Status** | **SIGNED** |
| **Date** | 2026-05-19 |
| **Verifier** | Track 1 completion + audit remediation session |
| **Gate command** | `make enterprise-check` |
| **Prod rollup snapshot** | funding_rounds=313, claims=885, company_details=59 (§12 log) |

**Residuals (Track 2+ or env-only):**

- `signal_company_resolver` blob match still substring-based (separate from `fuzzy_match_company`).
- `big_deals_collector` / `funding_rumor_detector` not behind `CI_STRICT_PIPELINE`.
- Hermes/Grok AI ingest optional; not required for green bar.

---

## Track 2 — Investor product surface

**Exit criteria (ROADMAP):** Search works; dossier shows provenance; no placeholder settings; fast semantic search.

**Status:** **SIGNED** (2026-05-20)

| ID | Requirement | Signed | Evidence |
|----|-------------|--------|----------|
| P2-1 | API contract tests (Vitest + `hono.request`) | [x] | `apps/api/test/routes.test.ts` + `auth.test.ts` |
| P2-2 | Search: `$state` + URL sync; slug links | [x] | `search/+page.svelte`, search API returns `slug` |
| P2-3 | Settings: real counts from `/api/status` | [x] | `ingestCatalog` on status + `data/ingest_catalog.json` |
| P2-4 | Migrate legacy `slate-*` → `ci-*` | [x] | funding/jobs detail → `ci-page` |
| P2-5 | TanStack Query on lists + dossier | [x] | companies/funding/jobs lists; detail `[id]` routes |
| P2-6 | Hermes company enrich export/apply | [x] | `scripts/company_enrich_*.py`, `make company-enrich-*` |
| P2-7 | Dossier team/products + corroboration badges | [x] | products tab; hash tabs; `CorroborationBadge` tokens |
| P2-8 | `fields_provenance` on funding tab | [x] | dossier funding sources/investors; profile provenance hint |
| X-07 | Native semantic search in Bun | [x] | `nativeSemanticSearch.ts`; `CI_SEMANTIC_PYTHON=1` fallback |
| X-09 | Verified raised + participants on company page | [x] | `verified_raised_usd` KPI; funding tab columns |
| X-12 | Unify provenance on design tokens | [x] | `CorroborationBadge.svelte` |

### Verification commands

```bash
make track2-verify
cd apps/api && bun test
cd apps/dashboard && bun run check
```

### Sign-off

| Field | Value |
|-------|--------|
| **Status** | **SIGNED** |
| **Date** | 2026-05-20 |
| **Verifier** | Track 2 completion session |
| **Gate command** | `make track2-verify` |

**Residuals:** Prod `intel-gate` may fail on orphan backlog; `bun test` alert insert can `SQLITE_BUSY` if DB is locked. Search/settings/events/signals pages still use some `slate-*` utilities (cosmetic). Playwright E2E not added.

---

## Track 3 — Engineering platform

**Exit criteria (ROADMAP):** PRs cannot merge red; lint + tests + golden eval required.

| ID | Requirement | Signed | Evidence |
|----|-------------|--------|----------|
| P3-1 | GitHub Actions: pytest, intel-gate, API test, lint | [x] | `.github/workflows/ci.yml`; `make track3-verify` locally |
| P3-2 | `make lint` all linters | [x] | `make lint` (2026-05-20) |
| P3-3 | JS lint/format (Oxfmt + Oxlint) | [x] | root `package.json`, [docs/LINTING.md](LINTING.md) |
| P3-4 | Widen coverage gate | [x] | rollup/gate/repair in `pyproject.toml` + tests |
| P3-5 | Collector contract tests | [x] | `tests/test_collector_contracts.py` |
| P3-6 | `daily_intel` dry-run | [x] | `--dry-run`, `test_daily_main_dry_run_completes` |
| P3-7 | Bare-metal healthchecks | [x] | `scripts/healthcheck.sh`, `make health-check` (no Docker) |
| P3-8 | Fix `pyrightconfig.json` paths | [x] | removed; ty SSOT per [docs/LINTING.md](LINTING.md) |

### Sign-off

| Field | Value |
|-------|--------|
| **Status** | **SIGNED** (bare-metal ops; no container images) |
| **Verifier** | Track 3 completion (2026-05-20) |
| **Gate command** | `make track3-verify` and `make lint` |

---

## Track 4 — Hosted product

### Sign-off

| Field | Value |
|-------|--------|
| **Status** | **SIGNED** (SQLite-only foundation; multi-tenant billing deferred) |
| **Gate command** | `make lint` · `make test-cov` · `make regulatory-license-rollup` · `cd apps/api && bun test` |
| **Docs** | [TRACK4_ENTERPRISE.md](TRACK4_ENTERPRISE.md) |
| **Remaining** | Cap table ingest, optional org/RBAC product, billing |

---

## Track 5 — Investor dossier depth

### Sign-off

| Field | Value |
|-------|--------|
| **Status** | _in progress_ — P5-1–P5-3 implemented; verify on prod DB |
| **Gate command** | `make lint` · `make cap-table-rollup` · `uv run pytest tests/test_cap_table_rollup.py -q` · `cd apps/api && bun test` · `cd apps/dashboard && bun run check` |
| **Docs** | [TRACK5_DOSSIER_DEPTH.md](TRACK5_DOSSIER_DEPTH.md) |

---

## Quick reference: current green bar

```bash
make enterprise-check   # T0/T1 operational bar today
make daily              # production ingest (after T0 sign-off)
```

Track 0–5 sign-off means **engineering criteria met**, not a shipped multi-user product. For deploy, data fill, and UX gates see [ROADMAP_PRODUCTION.md](ROADMAP_PRODUCTION.md) (Track 6).
