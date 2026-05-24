# Production roadmap (post deep-dive audit)

**Status:** Living document · **Created:** 2026-05-20 · **Updated:** 2026-05-20 (audit wave 2)  
**Source:** Wave 1 (14 audits) + **Wave 2 (15 audits):** deps, JS stack, AI/LLM, SQLite, API security, resilience, observability, tests, collectors, dashboard UX, config, deploy, docs drift, performance, bugs, Hermes.

**Authority:** Honest “what to do next for a **production-ready, enterprise-grade** launch.”  
**Does not replace:** [ROADMAP.md](ROADMAP.md) track history or [SIGNOFF.md](SIGNOFF.md) engineering exit criteria.

---

## What “enterprise launch ready” means here

Not “tracks 0–5 signed.” Not “works on my laptop.” Means:

| Gate | Requirement |
|------|-------------|
| **Data** | Prod DB filled: rollups, licenses, cap table, strict funding path, dedup index enforced |
| **Ops** | Reboot-safe API + UI + cron; backups; health checks pass; runbook + env template |
| **Trust** | No silent pipeline failures; LLM/agent output cannot inflate confidence without corroboration |
| **Security** | If on WAN: read auth, TLS, redacted payloads; if LAN-only: documented threat model |
| **Quality** | API contract tests on all routers; dashboard smoke in CI; `pip-audit` + lockfile discipline |
| **Docs** | Operator docs match code (PIPELINE defects archived, not copied as current) |
| **Supply chain** | Reproducible `uv`/`bun` locks; no undeclared runtime deps (`discord.py`, Hermes path) |

**Framework verdict (wave 2):** **Do not migrate.** Keep **Bun + Hono + SvelteKit 5 + SQLite + Python collectors**. Fix tooling, auth, data paths, and AI trust boundaries — not React/Postgres/Node unless product strategy changes.

---

## Executive summary

You have a **strong single-operator intelligence pipeline** on SQLite. That is **not** the same as an **enterprise product** ready for investors, WAN exposure, or multi-operator ops without further work.

| Dimension | Readiness (1–10) | One-line truth (wave 2) |
|-----------|------------------|-------------------------|
| Daily ingest + data trust | **7** | Fail-fast good; RSS logic bug + duplicate collectors hurt noise |
| Funding / jobs rollups | **6–7** | Canonical model exists; legacy CLI + keyword side door remain |
| Company dossier depth | **5** | UI exists; prod data empty unless `CI_COMPANY_DATA_ROLLUP=1` |
| API (internal LAN) | **6** | Solid locally; **all GET public**; dossier = 15 queries + full `data_json` |
| API (internet-facing) | **4** | Read auth, TLS, edge rate limits, Zod on writes — all missing |
| Dashboard (product UX) | **5–6** | Dossier strong; **silent errors**, no tests, **broken favicon import** |
| Tests / CI | **5–6** | Signal path strong; **10/13 API routers untested**; no UI tests; healthcheck broken in CI |
| Deploy / ops | **5** | Makefile + backup scripts; **no DEPLOY.md, systemd, prod UI serve** |
| Docs truth | **3–4** | **PIPELINE defect table frozen 2026-05-19**; AGENT_HANDOFF still says Track 0 |
| Supply chain (Python/JS) | **5** | Locks exist; **no `pip-audit`/`bun audit` in CI**; 3 bun.locks; unused/misplaced deps |
| AI / LLM safety | **4** | Grok prompts unsanitized; **confidence inflation** on Hermes apply; embedding model split |
| Observability / SRE | **4** | Pipeline JSON logs only; **no metrics, tracing, run_id, infra alerts** |
| Config / twelve-factor | **4** | **No `.env.example`**; 50+ ad hoc env reads; Hermes path hardcoded |
| Collectors quality | **5** | **RSS `store_signal` precedence bug** stores almost everything; RSS×2 daily |
| Performance @ 100 cos | **7** | SQLite fine for ~1k sig/day; daily wall-clock + missing indexes bite later |

**Honest label for tracks 0–5:** Engineering exit criteria met for **one machine**.  
**Honest label for Track 6:** **Production product** — majority of phases still open.

---

## Framework & dependency decisions (wave 2)

| Layer | Current | Change? | Action |
|-------|---------|---------|--------|
| API runtime | Bun + Hono + Zod | **No** | Pin Bun in CI; `bun install` in `apps/api`; add `bun run build` to CI |
| API DB | `bun:sqlite` RW | **No** | Add `query_only` read path (**6-B04**) |
| Dashboard | SvelteKit 2 + Vite 8 + Tailwind 4 | **No** | `adapter-static` + nginx for prod (**6-B02**); fix missing `favicon.svg` |
| Python | uv workspace 3 packages | **No** | Remove unused deps; `pip-audit` + `uv lock --check` in CI |
| py-enterprise | SQLAlchemy stack | **Freeze** | Never on prod daily cron (**6-E05**) |
| Postgres | Removed | **No** | SQLite only per product decision |
| Hermes | External + **import coupling** | **Loosen** | `HERMES_AGENT_ROOT`; optional HTTP ingest (**6-A08**, **6-H04**) |
| Search (aspirational) | sqlite-vec in old ROADMAP | **Defer** | Shipped: Bun + Ollama native semantic (**6-E07**) |

### Supply chain backlog (new IDs)

| ID | Task | Acceptance |
|----|------|------------|
| **6-F01** | CI: `uv lock --check` + `uv run pip-audit` | PR fails on drift or known CVEs |
| **6-F02** | CI: `bun install --frozen` in `apps/api` + `apps/dashboard`; `bun audit` | Reproducible JS installs |
| **6-F03** | Remove unused: `python-dotenv`, `factory-boy`; relocate `structlog`/`tenacity` to enterprise | Cleaner `uv.lock` |
| **6-F04** | Bump httpx/httpcore/h11 after audit; align pre-commit ruff with lock | P1 CVE hygiene |
| **6-F05** | Pin CI Python **3.12** (match `.python-version`) | Repro builds |
| **6-F06** | Optional extra: `discord.py` for worker bot | Document `uv sync --extra discord` |
| **6-F07** | Unify `CI_OLLAMA_HOST` vs `OLLAMA_HOST` in API | One env name in template |

---

## AI / LLM production safety (wave 2 — new phase G)

| ID | Task | Acceptance |
|----|------|------------|
| **6-G01** | **Stop confidence inflation** on Hermes apply (`funding_enricher`, `enrich_queue_apply`) | LLM-sourced claims capped until corroborated |
| **6-G02** | Single embedding model env (`CI_OLLAMA_MODEL`) everywhere; **no zero-vector fallback** in `embeddings.py` | Failed embed = skip write, not `[0.0]*768` |
| **6-G03** | Sanitize DB→Grok prompts (`grok_x_fetcher`, `x_query_builder`) | Max length, strip control chars, fixed system role |
| **6-G04** | Schema-validate Grok/enrich JSON before DB | Invalid batch rejected with metric |
| **6-G05** | Cost guards: default **off** `CI_AUTO_GROK_X` on bare `daily`; off `CI_X_QUERY_AI_EXPAND` in full-sweep; per-query timeout on `x_search` | Document spend; no hung subprocess |
| **6-G06** | Deduplicate Grok JSON parsers + prompt copies | One `parse_llm_json_array()` + shared schema module |
| **6-G07** | Regulatory: relabel SEC Form D (not “license” at 0.88); lower RSS regex license confidence | Dossier licenses tab truthful |
| **6-G08** | Decouple monorepo from `sys.path` import of `~/.hermes/hermes-agent` | `HERMES_AGENT_ROOT` or subprocess/HTTP wrapper (**6-H04**) |

---

## Collector & ingest bugs (fix before prod data trust)

| ID | Severity | Task | Acceptance |
|----|----------|------|------------|
| **6-COL01** | **P0** | Fix RSS `store_signal` boolean precedence (`rss_collector.py`) | High-signal filter actually filters |
| **6-COL02** | **P0** | One RSS walker on daily: drop `multi_source` **or** `rss_collector` from parallel list | Single catalog pass per day |
| **6-COL03** | **P1** | `crunchbase_collector` → Crunchbase News URL only (not all `general_startup`) | No quadruple-fetch |
| **6-COL04** | **P1** | `big_deals_collector`: fix `lead_investor` column or retire | CLI `intel deals` does not SQL-error |
| **6-COL05** | **P1** | `technology_stack`: UNIQUE or delete-before-insert | No unbounded duplicate rows |
| **6-COL06** | **P2** | `investor_collector` return int; persist or drop `momentum_detector` from daily | Metrics not `None` |
| **6-COL07** | **P2** | `angellist` URL matches `sources_registry` | Feed not empty |
| **6-COL08** | **P2** | `rss_collector`: one connection per thread or sequential fetch (not shared cursor) | No concurrent cursor corruption |

---

## Observability & SRE (wave 2)

| ID | Task | Acceptance |
|----|------|------------|
| **6-O01** | Fix healthcheck + add `/ready` with `SELECT 1` + optional staleness | `make health-check` green on live stack |
| **6-O02** | `CI_RUN_ID` UUID on daily; in every `pipeline_step` log line | One ID greps full daily |
| **6-O03** | Pipeline failure → Discord/webhook when cron exit ≠ 0 | Operator alerted |
| **6-O04** | JSON logging on Python stdout (level, run_id, step_id) | Aggregator-parseable |
| **6-O05** | API middleware: request_id + duration_ms JSON | Correlate UI errors |
| **6-O06** | Post-daily cron: checkpoint + backup + alert on failure | Matches **6-B05** |
| **6-O07** | `make config-check` — required env for mode `daily`/`api` | Fail fast with message |
| **6-O08** | Optional: Prometheus `/metrics` or document deferral | Explicit ops choice |

---

## Config & operator SSOT (wave 2)

| ID | Task | Acceptance |
|----|------|------------|
| **6-CFG01** | Restore root `.env.example` (full `CI_*` catalog) | New operator bootstrap (**6-A08**) |
| **6-CFG02** | `docs/CONFIG.md` — single env table | Linked from [README.md](README.md) |
| **6-CFG03** | `HERMES_AGENT_ROOT` in `grok_x_fetcher.py` | Non-`~/.hermes` hosts work |
| **6-CFG04** | `call_intel.sh` git-root detection (not `$HOME/Documents/...`) | Portable clone path |
| **6-CFG05** | Gitignore `data/hermes_enrich/*.json`, enrich outputs | No accidental PII commit |
| **6-CFG06** | Pre-commit secret scanner (gitleaks/detect-secrets) | Blocks credential commits |

---

## What the signed tracks actually mean

| Track | Signed means | Does NOT mean |
|-------|--------------|---------------|
| 0–1 | Pipeline won’t silently corrupt on one operator DB | Multi-tenant SaaS; no duplicate funding path in CLI |
| 2 | Search + dossier MVP works locally | sqlite-vec shipped (actual: Bun + Ollama cosine) |
| 3 | CI runs core pytest + lint on PRs | Full `make lint` every job; dashboard E2E |
| 4 | SQLite hardening, rate limits, regulatory rollup plumbing | Hosted billing, RBAC, cap table **verified on prod** |
| 5 | Cap table + license **tabs in code** | Rollups run daily without `CI_COMPANY_DATA_ROLLUP=1` |

---

## Recommended program: Track 6 — Production product

Work in **phases**. Do not start Phase D (public exposure) until A + B + F are green on prod DB.

### Phase A — Data you can trust on prod DB (2–4 weeks)

**Goal:** Dossier tabs show real data for your watchlist after `make daily-tiered` + rollups.

| ID | Task | Acceptance criteria |
|----|------|---------------------|
| **6-A01** | Default-on `CI_COMPANY_DATA_ROLLUP` after daily gate (or document+cron `make rollup-all`) | Weekly: `company_details` count rises; claims-audit passes |
| **6-A02** | Ingest SEC Form D bulk + ESMA into `raw_signals` | `sec_edgar` rows in DB; regulatory rollup produces license claims |
| **6-A03** | Run `make cap-table-rollup` on prod; decouple cap/regulatory from company flag if needed | `cap_table_holdings` > 0 where `round_participants` exist |
| **6-A04** | Single funding write path: `CI_STRICT_PIPELINE=1` in prod cron env | CLI `intel funding|deals` blocked; no new `funding_events` rows |
| **6-A05** | Dedupe RSS: one walker (**6-COL02**) | No duplicate articles from same feed URL |
| **6-A06** | Fix signal dedup policy (canonical URL vs `#rs` suffix) | Document policy; test: same article → one event or explicit multi-signal |
| **6-A07** | Hermes tiered crons per `docs/SCHEDULING.md` | `frequent` without X; `grok-refresh` 5×/day; `daily-tiered` with `CI_SKIP_GROK_X=1` |
| **6-A08** | `HERMES_AGENT_ROOT` env + restore `.env.example` | Fetch works without hardcoded `~/.hermes` |
| **6-A09** | Enrich export→apply runbook or `make enrich-all` wrapper | Operator doc; optional weekly cron |
| **6-A10** | Migrate Obsidian/Discord off `funding_events` to `funding_rounds` | No new writes to legacy table |
| **6-A11** | `make migrate-dedup`; fail `init_database` if dedup index cannot be created | No ingest race without `idx_raw_signals_dedup` |
| **6-A12** | Default `make daily` uses `CI_SKIP_GROK_X=1` or rename footgun | Plain `daily` does not require Grok on headless hosts |

### Phase B — Runnable stack on one host (1–2 weeks)

| ID | Task | Acceptance criteria |
|----|------|---------------------|
| **6-B01** | `docs/DEPLOY.md`: env table, systemd units for API | `systemctl start ci-api` → `/health` OK |
| **6-B02** | Dashboard prod build + serve (`adapter-static` + nginx) | `PUBLIC_CI_API_URL` matches browser origin; fix `favicon.svg` |
| **6-B03** | Fix `scripts/healthcheck.sh` (`/api/status` has no `"ok"`) | `make health-check` passes (**6-O01**) |
| **6-B04** | API `query_only` / readonly connection for GET server | GET cannot INSERT; matches `docs/SQLITE.md` |
| **6-B05** | Post-daily cron: `sqlite-checkpoint` + `sqlite-backup` | Timestamped backup under `data/backups/` |
| **6-B06** | Daily: subprocess timeouts + overlap guard (`CI_STEP_TIMEOUT_SEC`) | Second daily aborts with clear log; hung step killed |
| **6-B07** | `make enterprise-check` → rename/doc: operational bar, not py-enterprise | New operators not confused |
| **6-B08** | Single embedding stage (remove duplicate `run_intel` + sequential embed) | One Ollama pass per daily |
| **6-B09** | Extend health-check: dashboard URL + optional data freshness | Fails if API up but signals stale > N hours |
| **6-B10** | API/deploy gate: fail `/health` if required tables missing | No 500 on dossier after code upgrade without migrate |

### Phase C — Product surface (2–3 weeks)

| ID | Task | Acceptance criteria |
|----|------|---------------------|
| **6-C01** | API tests: all routers (funding, jobs, events, signals, discovery, data-audit, dossier) | Each router ≥1 contract test on isolated DB (**6-E06**) |
| **6-C02** | Dashboard Vitest + Playwright smoke | CI: home → company → funding tab passes |
| **6-C03** | Error surfaces on signals/events/search/settings/companies list | Failed fetch shows `ci-alert-error`, not blank |
| **6-C04** | Search: mode selector (keyword / auto / semantic) | URL `?q=&mode=`; semantic capped; no unbounded `uv` in prod |
| **6-C05** | Migrate slate-* pages to `ci-*` | Grep `slate-` zero on user-facing routes |
| **6-C06** | Events: `source_url` links; company links by slug | N1 partial on dossier |
| **6-C07** | Profile panel on dossier (`company_details` + profile-claims API) | Overview shows HQ, YC batch, legal name when present |
| **6-C08** | Team tab: corroboration badges; fix empty-state copy | Matches products/licenses tabs |
| **6-C09** | Overview KPIs: products, licenses counts from `summary` | Header grid shows non-zero when data exists |
| **6-C10** | Remove or wire Settings notification checkboxes | No fake controls |
| **6-C11** | `claims-audit-strict` in CI or weekly cron | Fails on actionable-null regression |
| **6-C12** | Add `src/routes/+error.svelte` + optional `hooks.server.ts` security headers | Uncaught errors show operator-friendly page |

### Phase D — Safe external exposure (only if needed)

| ID | Task | Acceptance criteria |
|----|------|---------------------|
| **6-D01** | Read auth on `/api/*` (`CI_API_READ_KEY` or proxy) | 401 without key when env set |
| **6-D02** | TLS reverse proxy; API bind loopback | No plain HTTP on `0.0.0.0` |
| **6-D03** | Edge rate limit (not only in-memory Bun map) | Survives restart + multi-instance |
| **6-D04** | Truncate/redact `data_json` on public GET routes | No raw payload dump |
| **6-D05** | Zod on `POST /api/discovery` + body size limits | Invalid body → 400 |
| **6-D06** | Separate read/write API keys | Leaked read key cannot mutate |
| **6-D07** | Security regression suite in `apps/api/test/` | Unauthorized GET sweep automated |
| **6-D08** | Threat model + `docs/DEPLOY.md` exposure decision | Signed ops choice documented |

### Phase E — Engineering debt (parallel / ongoing)

| ID | Task | Acceptance criteria |
|----|------|---------------------|
| **6-E01** | Schema SSOT: merge `migrations.py` into `schema.py` or version ledger | Fresh install reproducible (**6-DB01**) |
| **6-E02** | Collector contract tests (top 10 ingestors, respx) | RSS, HN, EDGAR, GitHub, crunchbase mocked |
| **6-E03** | `intel_quality_gate` profiles (`strict` vs `nightly`) | Prod corpus does not false-fail daily |
| **6-E04** | Fix PIPELINE.md / AGENT_HANDOFF / ARCHITECTURE stale sections | Archive defect table or date-stamp; **6-E04** |
| **6-E05** | Deprecate or archive `packages/py-enterprise` (ADR) | No accidental `CI_ENTERPRISE_RSS` on prod |
| **6-E06** | Expand API test DB isolation (per-test temp DB) | No SQLITE_BUSY flake in auth test |
| **6-E07** | Semantic search: cap latency; sqlite-vec or FTS primary path | p95 search < 2s on prod-size DB |
| **6-E08** | Jobs: stale-claims deactivation + API detail `skills` on posting | X-04 regression test |
| **6-E09** | Funding: remove `extract_from_signals` raw keyword side door | Claims only from classified events |
| **6-E10** | Daily integration test with mocked `run_script` step order | Registry change breaks test |
| **6-E11** | Resilience: `writer_lock` once per batch commit; RSS thread-safe DB | No partial corrupt ingest |
| **6-E12** | Indexes: `raw_signals(company_id, detected_at)`, `intelligence_events(company_id, created_at)` | Ranker/trending fast at 100+ companies |
| **6-E13** | Split company dossier API or strip `data_json` from list endpoints | Dossier load < 500ms p95 on LAN |

### Phase H — Hermes integration hardening

| ID | Task | Acceptance criteria |
|----|------|---------------------|
| **6-H01** | Document tiered cron as **only** prod daily default | `SCHEDULING.md` + DEPLOY |
| **6-H02** | `make enrich-all` + queue depth in `/api/status` | Operator sees pending enrich lines |
| **6-H03** | Per-query try/continue in `fetch_batches` | One bad Grok query does not abort batch |
| **6-H04** | Optional `POST /api/ingest/x` (auth) | File handoff not required for enterprise |
| **6-H05** | Deprecate `integrations/hermes/run_daily_prod.py` | Single entry: `call_intel.sh` |

---

## North-star coverage (N1–N8)

| # | Capability | Today | Track 6 closes |
|---|------------|-------|----------------|
| N1 | Event timeline + source URLs | Partial (events list weak) | 6-C06, 6-C01 |
| N2 | Funding + corroboration | Strong on dossier | 6-A04, 6-C01, 6-G01 |
| N3 | Verified vs total raised | On dossier KPIs | Keep; document threshold 0.45 |
| N4 | Team/products/licenses | UI shells; data sparse | 6-A01–A02, 6-C07–C08, 6-COL01 |
| N5 | Jobs + hiring velocity | Jobs pipeline OK; velocity UI weak | 6-C11 optional widget |
| N6 | Regulatory on dossier | Tab exists; ~1 license in prod | 6-A02, 6-G07 |
| N7 | Fast search | Keyword OK; semantic heavy | 6-C04, 6-E07, 6-G02 |
| N8 | Pipeline health in UI | FreshnessBanner + status | 6-B09, 6-C09, 6-O01 |

---

## Top launch blockers (wave 2 ranked)

1. **Healthcheck lies** — `make health-check` fails on `/api/status` grep (**6-B03** / **6-O01**)
2. **No `.env.example` + hardcoded Hermes path** — containers/new hosts break (**6-A08**, **6-CFG01**)
3. **Public GET API** — full corpus leak on port 3000 (**6-D01**)
4. **RSS `store_signal` bug + double RSS** — noise and wasted ingest (**6-COL01**, **6-COL02**)
5. **Dedup index may be missing on prod** — parallel ingest races (**6-A11**)
6. **Default `make daily` requires Grok** — headless cron aborts (**6-A12**)
7. **LLM confidence inflation on enrich apply** — trust violation (**6-G01**)
8. **Embedding model split + zero vectors** — broken semantic search (**6-G02**)
9. **PIPELINE.md defect table stale** — operators follow wrong runbook (**6-E04**)
10. **No deploy/systemd/prod dashboard** — reboot kills product (**6-B01**, **6-B02**)

---

## Explicitly deferred (not Track 6 unless you decide)

- Multi-tenant billing / org RBAC
- Postgres / second database engine
- Full sqlite-vec migration (optional **6-E07**)
- Playwright visual regression suite
- Rust collectors / **React rewrite** (wave 2: not recommended)
- Prometheus mandatory (optional **6-O08**)

---

## Verification gates (use these to claim “production ready”)

```bash
# Operational bar (today)
make enterprise-check
make daily-prod            # prod cron: tiered + CI_STRICT_PIPELINE + dedup index
make daily                 # dev: tiered (CI_SKIP_GROK_X=1); use daily-with-grok for inline X
make rollup-all
make cap-table-rollup
make claims-audit-strict

# Product bar (Track 6 minimum)
make health-check CI_API_URL=http://127.0.0.1:3000   # after 6-B03 fix
make lint
make test-api
cd apps/dashboard && bun run check && bun test   # after 6-C02

# Supply chain (after 6-F01/F02)
uv lock --check
uv run pip-audit
cd apps/api && bun audit
```

**Enterprise launch checklist:**

- [ ] Phase A + **6-COL01–02** + **6-A11–12** on prod DB
- [ ] Phase B + **6-CFG01** + **6-O01–O03**
- [ ] Phase F (**6-F01–07**) in CI
- [ ] Phase G (**6-G01–G04**) minimum before trusting dossier LLM fields
- [ ] Phase C smoke green
- [ ] Phase D (if WAN): read auth + TLS + **6-D08** signed
- [ ] **6-E04** docs truth pass

---

## Quick wins (this week)

1. Fix `healthcheck.sh` `/api/status` assertion (**6-B03**).
2. Fix RSS `store_signal` parentheses (**6-COL02**).
3. Restore `.env.example` (**6-CFG01**).
4. Set prod cron: `CI_SKIP_GROK_X=1`, `CI_STRICT_PIPELINE=1`, `CI_COMPANY_DATA_ROLLUP=1`.
5. Run `make migrate-dedup` + rollups on prod DB.
6. Banner on `PIPELINE.md` defect table: “Historical — see ROADMAP_PRODUCTION.md”.

---

## Related docs

| Doc | Role |
|-----|------|
| [ROADMAP.md](ROADMAP.md) | Historical track checkboxes |
| [SIGNOFF.md](SIGNOFF.md) | Per-track engineering sign-off |
| [PIPELINE.md](PIPELINE.md) | Commands (**defect tables need refresh**) |
| [TRACK5_DOSSIER_DEPTH.md](TRACK5_DOSSIER_DEPTH.md) | P5-1–P5-3 notes |
| [SCHEDULING.md](SCHEDULING.md) | Cron tiers |
| [SQLITE.md](SQLITE.md) | WAL, backup, API read profile |
| [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md) | Intended Hermes boundary |

---

## Audit index

### Wave 1 (2026-05-20)

| Focus | Key takeaway |
|-------|----------------|
| API | Public GET; healthcheck broken; semantic DoS |
| Dashboard | No tests; silent errors; slate pages |
| Worker | Default daily needs Grok; no timeouts |
| Signals | Duplicate events by design; dedup dead on hot path |
| Funding | Legacy CLI writers; double rollup |
| Company data | Rollup opt-in; licenses empty in prod |
| Jobs | X-04 fixed; claims stale gap |
| Collectors | RSS duplicated; 27 collectors untested |
| DB | Split schema; no migration ledger |
| Hermes | Hardcoded `~/.hermes`; enrich manual |
| Tests/CI | 7 modules in cov gate; no dashboard tests |
| Security | Read auth missing for WAN |
| Docs | Track 2 “not started” while signed |
| Deploy | No systemd; no prod dashboard serve |
| py-enterprise | Keep frozen; do not merge ORM daily |

### Wave 2 (2026-05-20) — enterprise / launch

| Focus | Key takeaway |
|-------|----------------|
| Python deps | httpx at floor; pip-audit not in CI; unused dotenv/factory-boy |
| Bun/TS deps | 3 bun.locks; API lock not in CI; no framework change |
| AI/LLM | Confidence inflation; prompt injection surface; embedding model drift |
| SQLite | API never migrates; missing hot indexes; split schema |
| API security | P0 public GET; discovery 500 leaks errors |
| Resilience | Per-row writer_lock; RSS shared cursor; silent dashboard catches |
| Observability | No run_id, metrics, pipeline failure alerts |
| Tests | 10/13 routers untested; shared ci_test.db flake |
| Collectors | RSS precedence bug; crunchbase wrong feeds |
| Dashboard UX | Broken favicon; +error.svelte missing |
| Config | No .env.example; 50+ scattered env vars |
| Deploy | No DEPLOY.md/systemd |
| Docs drift | PIPELINE defects stale; AGENT_HANDOFF Track 0 |
| Performance | OK @ 100 cos / 1k sig; index gaps for scale |
| Bugs sweep | Top 10 ranked launch blockers consolidated above |
| Hermes | sys.path import violates HTTP-only story |

Update this document when phase gates are met, not when individual PRs merge.
