# File-by-file audit (2026-05-19)

**Goal:** Investor-grade private-company intelligence — maximum signal density, low latency, auditable provenance, a dossier UI people trust for investment research.

**Method:** 40 parallel deep dives (function-level where noted). Cross-checked against `docs/PIPELINE.md`, `docs/HANDBOOK.md`, `docs/ARCHITECTURE.md`.

**How to use:** Census evidence for findings. **Implementation backlog and tracks:** [ROADMAP.md](ROADMAP.md) (single source of truth). IDs P0–P4 and X-## live there.

---

## Executive summary

| Area | Verdict | Top blockers for investor product |
|------|---------|-----------------------------------|
| **Daily pipeline** | Broken in places | `parallel_collect` subprocess can't import `automation.*` (no PYTHONPATH); continues after failures; extraction before processor duplicates events |
| **Signal layer** | Strong tests, logic bugs | Unlabeled URL-only signals; repair before backfill; alias cache stale; `is_duplicate` dead on hot path |
| **Funding** | Three parallel write paths | `funding_collector` / `big_deals` / `enhanced_funding_detector` vs processor + rollup; rumor valuation scaling bug |
| **Company data rollup** | Rich claims model, aggregation gaps | Profile fields dropped at aggregate; no `/api/profile/claims`; team tab lacks corroboration badges |
| **Jobs** | Global stale deactivation bug | Partial company runs deactivate other companies' postings |
| **API** | Rich read surface, unsafe writes | `query_only` + POST alerts/discovery; open CORS; semantic search spawns Python (45s) |
| **Dashboard** | Good shell, incomplete data wiring | Search page broken (`$derived` + `bind`); detail routes stale on client nav; verified funding KPI missing |
| **Tests** | ~24/74 collectors directly tested | Zero API/dashboard tests; coverage gate only 5 Python modules |
| **Enterprise** | Shadow stack | Schema drift, broken website collector, Alembic with zero revisions |

---

## Collector shards (C01–C20)

| Shard | Status | Critical findings (summary) |
|-------|--------|------------------------------|
| C01 `signal_processor.py` | done | Unlabeled gate uses `extract_signal_text` not merged text; `is_duplicate` unused; alias cache never refreshes; `created_at` = signal time not ingest time |
| C02 `signal_company_resolver.py` | done | Substring `nl in blob` false positives; synthetic `{slug}.com` domains; `x_handle` not indexed; match scores not persisted |
| C03 repair + gate | done | **Repair order:** reclassify before backfill (PIPELINE defect); gate not in daily; money-keyword mismatch vs repair |
| C04 fanout + entity_extract | done | Fanout backlog (400 rows, no SQL filter on `url_fanout_done`); permissive deal relevance; entity regex recall limits |
| C05 funding collectors (4) | done | `big_deals` schema mismatch + wrong columns; rumor trillion-$ bug; `enhanced_funding` marks all signals processed=1; duplicate event paths |
| C06 `funding_rollup.py` | done | Thin shim; double daily run with `enrichment_runner`; investor_firms not fed by `investor_collector` |
| C07 funding enrichment (4) | done | `sync_round_participants` twice on update; Hermes apply requires int `claim_id`; four-way amount parsing duplication |
| C08 `company_data/*` | done | **7 profile keys aggregated** — SEC/YC/API fields dropped; no profile claims API; corroboration heuristic weaker than funding |
| C09 rollup + enricher + valuation | done | Legacy `company_enricher` writes `company_details` without provenance; conflicts with claims pipeline; valuation OK but intel-event path untested |
| C10 `jobs/*` | done | **Global stale deactivation** on partial runs (`job_aggregator.py:295-306); sequential ATS probe latency; no job tests for rollup shims |
| C11 RSS + registry | done | 150 enabled feeds; `trust_tier` stripped in `as_rss_dict()`; stores almost all entries not only high-signal |
| C12 multi_source + continuous | done | Dedup key mismatch vs RSS (duplicate rows); `continuous_ingest` legacy, not in parallel registry |
| C13 GitHub stack | done | `commits_last_30d` always 0–1; `star_growth_30d` hardcoded 0; `ON CONFLICT` on tech_stack without UNIQUE — duplicate rows every run |
| C14 HN/PH/CB/AL/YC | done | **`hackernews_collector.py` missing `import sqlite3`** — import-time crash if scheduled |
| C15 X/Grok/ollama | done | Hardcoded `~/.hermes/hermes-agent`; sequential fetch latency; `ollama_client.py` unused on X path |
| C16 website/edgar/tech | done | `website_collector` ORM columns wrong vs operational schema; SEC `filing_date` KeyError; tech_stack duplicate inserts |
| C17 discovery/rank/promote | done | `investor_collector` return value bug; promotion lacks fuzzy dedup; `company_discovery` not daily |
| C18 mapper/momentum/reactive | done | Momentum scores never persisted; `reactive_enrichment` / `enhanced_signal_collector` not in registry |
| C19 rollup/embed/confidence | done | Triple Ollama embed per search query; `enrichment_runner.generate_stats` cursor bug; zero tests for reranker/confidence_sync |
| C20 ESMA/YouTube/utils | done | ESMA drops unmatched CASPs at ingest; YouTube weak company linkage; `enrichment/utils.py` is HTTP re-export only |

---

## Core DB + worker (W01–W06)

| Shard | Status | Critical findings (summary) |
|-------|--------|------------------------------|
| W01 `schema.py` | done | `alerts_sent` FK to `intelligence_events` not in SCHEMA; `idx_raw_signals_dedup` too coarse globally |
| W02 migrations/ingest | done | Dedup race without `IntegrityError` handling; `alerts_sent` no UNIQUE(event_id, channel) |
| W03 alerts/http | done | Hardcoded `ALERT_RULES`; DB `alert_rules` unused by Python; `structlog.getLogger` bug in 4 collectors |
| W04 daily_intel worker | done | No fail-fast; zero-vector embeddings on Ollama failure; double daily brief + triple embed paths |
| W05 automation | done | **`parallel_collect` broken** (ModuleNotFoundError); ~~stale `automation/daily_intel.py`~~ removed; fanout after `run_intel` extraction |
| W06 run_intel + intel.py | done | `collectors/` paths wrong (should be `packages/py-collectors/collectors/`); documented `grok-x-ingest` missing from shim |

---

## API shards (A01–A04)

| Shard | Status | Critical findings (summary) |
|-------|--------|------------------------------|
| A01 core API | done | Already on `bun:sqlite` + `query_only`; POST alerts/discovery fail; open CORS; `/api/health` doc wrong |
| A02 companies | done | ~14 sequential queries per dossier; `verified_raised_usd` not shown; search links use id not slug |
| A03 funding/jobs/events | done | Round detail over-includes all company claims; job detail missing per-claim `skills` |
| A04 other routes | done | `events`/`signals` count ignores filters; discovery POST on read-only DB |

---

## Dashboard shards (D01–D05)

| Shard | Status | Critical findings (summary) |
|-------|--------|------------------------------|
| D01 layout/home/api | done | TanStack Query barely used; nested `<a>` on home; `apiReachable` wrong on network error; error + skeleton together |
| D02 companies | done | Tabs not in URL; funding tab ignores `sources`/`participants`; `verified_raised_usd` unused; team tab no corroboration badges |
| D03 funding/jobs pages | done | Detail routes: `onMount` only → stale on param change; jobs/funding list vs detail design split (ci-* vs slate) |
| D04 search/discovery/etc | done | **Search: `$derived` + `bind:value` breaks inline search**; settings hardcoded 87/43/10 sources |
| D05 components/lib | done | Dual design system (ci-* vs slate/emerald); `CorroborationBadge`/`SourceTierPill` legacy Tailwind; `DarkModeToggle` orphan |

---

## Enterprise + scripts + Hermes (E01, E02, S01, H01, T01, R01)

| Shard | Status | Critical findings (summary) |
|-------|--------|------------------------------|
| E01 enterprise collectors | done | `website_collector` broken vs operational `website_snapshots`; SEC `filing_date`; structlog bug |
| E02 enterprise core/models | done | Alembic scaffold, zero versions; dual scoring/alerts/ingest; freeze per P4-2 |
| S01 scripts + CLI | done | `reprocess` double-reset dangerous; Hermes JSON ids must be int; `intel.py` collector paths stale |
| H01 Hermes integration | done | HTTP-only partial; `grok-x-ingest` doc mismatch; batch ingest skips fanout/funding |
| T01 tests map | done | ~50/74 collectors untested; zero API/dashboard tests |
| R01 stack | done | See [Stack modernization](#stack-modernization) below |

---

## Stack modernization (R01 — opinionated)

**Principle:** One operator, one SQLite corpus, fast read API, provenance-first dossier. Do not rewrite collectors in Rust or move to Postgres until you need multi-tenant SaaS.

### Keep (already aligned with bleeding edge)

| Layer | Choice | Why |
|-------|--------|-----|
| Read API | **Bun + Hono 4** (already `bun:sqlite`) | Native SQLite, sub-ms routing; PIPELINE doc still mentions `better-sqlite3` — code is ahead of docs |
| Collectors | **Python 3.12+**, sync **httpx** pool, **feedparser 6**, **curl-cffi** for brittle sites | Right tool for I/O-bound ingest; Rust not justified at ~74 modules |
| Dashboard | **SvelteKit 2 + Svelte 5 + Tailwind 4** | Best fit for tabbed dossier; expand TanStack Query, don't migrate to React |
| Embeddings (default) | **Ollama `nomic-embed-text`** via HTTP (`embedding_generator`) | Offline-first; fix worker path that writes zero vectors on failure |
| DB (now) | **SQLite WAL + readonly API** | Until hosted multi-tenant product |

### Change soon (highest ROI)

| Priority | Change | Investor impact |
|----------|--------|------------------|
| P0 | Fix `run_utils` PYTHONPATH + fail-fast daily | Pipeline actually runs |
| P0 | Single funding→events path; wire gate in daily | Trustworthy funding data |
| P0 | API: remove/fix writes on read-only DB; add auth + CORS allowlist | Safe external deploy |
| P0 | Fix `hackernews` import; jobs stale deactivation scoped by company | Data integrity |
| P1 | **sqlite-vec** (or sidecar) for semantic search — remove 45s Python subprocess from API hot path | Search latency |
| P1 | TanStack Query + `load()` prefetch on all dossier/list routes; fix search page `$state` | UX + shareable URLs |
| P1 | Surface `verified_raised_usd`, claim sources/participants on company funding tab | Due diligence |
| P1 | Expand `company_data` aggregate keys; profile claims API | Complete private-company profiles |
| P2 | CI-only provenance components; drop slate from funding/jobs detail | Visual trust |
| P2 | CI: ruff, pytest, `bun test` API smoke, widen coverage include | Regression safety |
| P3 | Optional cloud re-embed tier (Voyage/OpenAI) for weekly quality pass only — not per-RSS item | Better vectors without abandoning Ollama |

### Defer (until SaaS)

| Item | When |
|------|------|
| Postgres + pgvector | Multi-writer API, tenancy, managed backups |
| FastAPI | Only if you need one Python runtime + public OpenAPI SDK |
| Rust collectors | Only at ingest volume where Python profiling proves need |
| Next.js / React | No dossier advantage over current Svelte investment |

### Architecture target (12 months)

```mermaid
flowchart TB
  subgraph ingest [Python collectors - httpx/feedparser]
    RSS[RSS 150 feeds]
    X[Hermes Grok x_search]
    SEC[Form D bulk + signals]
    RSS --> RS[raw_signals]
    X --> RS
    SEC --> RS
  end
  subgraph layer1 [Layer 1 - single path]
    RS --> SP[signal_processor]
    SP --> IE[intelligence_events]
    SP --> Gate[intel_quality_gate]
  end
  subgraph layer2 [Layer 2 - rollups]
    IE --> FR[funding_rollup claims]
    IE --> JR[job_rollup]
    IE --> CD[company_data_rollup]
  end
  subgraph read [Bun Hono read-only]
  IE --> API[/api/companies slug dossier]
    FR --> API
    API --> UI[Svelte 5 dossier]
    Vec[(sqlite-vec semantic)]
    API --> Vec
  end
  subgraph enrich [Hermes batch]
    IE --> EQ[enrich_queue export/apply]
    FR --> FQ[funding_enrich export/apply]
  end
```

---

## Cross-cutting defect register (new / consolidated)

| ID | Severity | Finding | Fix direction |
|----|----------|---------|---------------|
| X-01 | P0 | `parallel_collect` import failure | `run_utils`: set PYTHONPATH to include `apps/worker` |
| X-02 | P0 | Daily continues after parallel/extraction failure | Abort or `--force` flag |
| X-03 | P0 | `hackernews_collector` NameError on import | Add `import sqlite3` |
| X-04 | P0 | Jobs global stale deactivation | Scope UPDATE by `company_id` in processed set |
| X-05 | P1 | Signal processor unlabeled URL-only bug | Gate on merged `text` after fallback |
| X-06 | P1 | Repair before backfill order | Swap steps in `signal_repair.run()` |
| X-07 | P1 | API semantic search subprocess | sqlite-vec + in-process search in Bun |
| X-08 | P1 | Search page broken bind | `$state` query + submit; slug links in results |
| X-09 | P1 | Company dossier ignores funding sources/participants | UI: render API fields; link to `/funding/:id` |
| X-10 | P2 | ~50 collectors untested | Contract tests with respx; priority ingest paths |
| X-11 | P2 | Enterprise shadow on same DB | Freeze; port or separate DB file |
| X-12 | P2 | Dual design system in dashboard | Migrate detail pages to `ci-*`; unify provenance badges on tokens |
| X-13 | P3 | `intel.py` / root `run_intel` wrong paths | Point at `packages/py-collectors/collectors/` |
| X-14 | P3 | Hermes `grok-x-ingest` doc vs shim | Add alias or fix docs to `make grok-x-ingest` |

---

## Test coverage map (T01)

- **Operational tests:** 30 files under `tests/` — strong on signal processor, funding corroboration, job claims, DB/dedup, enrich queue.
- **Collectors with direct imports:** ~24 / 74 modules.
- **Collectors with zero direct tests:** ~50 (most ingest scripts).
- **API:** 0 automated tests (`apps/api` has 20 TS files).
- **Dashboard:** 0 tests (`bun run check` only).
- **Makefile coverage gate:** only 5 modules at 80% (`migrations`, `connection`, `signal_processor`, `signal_company_resolver`, `utils.http`).

**Recommended layout:**

```
tests/
  unit/collectors/          # parser, classify, no DB
  operational/               # @pytest.mark.operational + operational_db
  integration/               # multi-step pipelines
  enterprise/                # @pytest.mark.enterprise
apps/api/test/               # vitest + hono.request
apps/dashboard/src/test/     # vitest + optional Playwright
```

---

## Product path (investor dossier)

What “maximum information on private companies” requires in the product (not just collectors):

1. **Single timeline** — one canonical event stream with provenance (fix duplicate writers first).
2. **Funding with investors** — claims + participants on company page, not only round-level badge.
3. **Verified vs total raised** — show `verified_raised_usd` and corroboration on KPIs (API already computes it).
4. **Team + licenses + products** — wire `company_data_rollup` into tabs; fix aggregate field drops.
5. **Jobs + hiring velocity** — fix stale bug; show corroboration on job cards.
6. **Regulatory (MiCA, Form D)** — enable rollup + surface licenses on dossier.
7. **Fast search** — FTS5 + sqlite-vec; no subprocess on `/api/search`.
8. **Freshness + health** — single status query via TanStack on layout/home (dedupe polls).

Open to change: framework swaps above are recommendations; implementation follows [ROADMAP.md](ROADMAP.md) Tracks 0 → 2.

---

## How this doc stays current

1. After each track milestone, check off items in `docs/ROADMAP.md` and note shard status here if needed.
2. Run `make intel-gate` + `make claims-audit` before releases.
3. Re-run targeted shards after major refactors (processor, rollup, API dossier).
4. Do not add `scripts/phase_*` or duplicate rollup entrypoints.

**Audit method:** 40 parallel read-only agents (function-level review) + dependency research + `docs/PIPELINE.md` cross-check. Re-run quarterly or before hosted launch.
