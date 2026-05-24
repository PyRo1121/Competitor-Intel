# Execution checklist (SSOT for progress)

**Status:** Living · **Update this file** as work completes — not scattered todos.  
**Context:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) · **Ops:** [PIPELINE.md](PIPELINE.md) · **Entrypoints:** [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) · **Standards:** [ENGINEERING.md](ENGINEERING.md)

---

## Instructions (humans + AI agents)

1. Work **top to bottom**. Do not start a later phase until the current phase **gate** is checked, unless the user explicitly reprioritizes.
2. When a task is done, change `[ ]` → `[x]` and add `— YYYY-MM-DD` at end of line (optional).
3. If blocked, add one line under the task: `BLOCKED: reason` — do not skip silently.
4. Do **not** duplicate long specs here; link to companion docs for how-to.
5. After any session that completes tasks, **commit this file** with the code changes (when user asks to commit).

### Phase gates (do not skip)

| Gate | Requires |
|------|----------|
| **G0** | S0 complete (repo baseline) |
| **G1** | P0 complete — **7 green dailies** + `make verify` on prod DB |
| **G2** | E1 complete — no prod `scripts/*.py` |
| **G3** | P1 + P2 complete — score + trust fields in DB, policy hooks |
| **G4** | P3 + P4 complete — dashboard + Hermes read path |
| **G5** | P5 + P6 — scoring tuned + freemium caps (when SaaS) |
| **G6** | P7 optional — vectors/RAG |

**Current focus (edit when starting a phase):** `P0`

---

## S0 — Repo baseline — **complete** (G0)

Gate: pipeline-only tree; Hermes shim; docs exist; production naming.

- [x] Remove API, dashboard, py-enterprise from active tree — 2026-05
- [x] Slim `collector_registry` to production daily set — 2026-05
- [x] `docs/PIPELINE.md`, `docs/PRODUCT_BRIEF.md`, `docs/ROADMAP_ENTRYPOINTS.md`, `docs/EXECUTION_CHECKLIST.md` — 2026-05
- [x] `docs/ENGINEERING.md` + `make verify` (was `v1-check`) — 2026-05-24
- [x] `make verify` green on CI test DB (`data/ci_test.db`) — 2026-05-24
- [x] `docs/SCHEDULING.md` trimmed for current pipeline (no dashboard/API refs) — 2026-05-24

**G0:** satisfied. **Crontab install** → P0-A (your machine).

---

## P0 — Artery trust (funding, ingest, cron)

**Product milestone:** You trust funding on real watchlist; false verified funding unacceptable.  
**Detail:** [PIPELINE.md](PIPELINE.md)

### P0-A — Environment & schedule

- [x] `uv sync` from repo root — 2026-05-24
- [x] `.env` from `.env.example`; `CI_DB_PATH` → prod DB path — 2026-05-24
- [x] `HERMES_AGENT_ROOT` default `~/.hermes/hermes-agent` (unset in `.env` OK if path exists) — 2026-05-24
- [x] Hermes cron: `competitor-intel-daily-prod` (`59fc409ed31a`) — 2026-05-24
- [x] Hermes cron: `competitor-intel-grok-refresh` (`bf5c245af6e9`) — 2026-05-24
- [x] `hermes cron status` — gateway running — 2026-05-24
- [x] Legacy bash sweep paused (`82e7afec268b`) — 2026-05-24
- [x] `logs/` ready for manual runs — 2026-05-24
- [x] No bash ops shims (`call_intel.sh`, `healthcheck.sh`, crontab templates removed) — 2026-05-24

### P0-B — Pipeline mechanics

- [x] `make migrate-dedup` or schema init; dedup index present — 2026-05-24
- [ ] `make daily-prod` completes without `--force` (in progress; EDGAR hit `database is locked` once)
- [x] `make rollup-all` (or rollups enabled in daily env) — rollups on daily path
- [x] `make claims-audit-strict` passes on prod DB — 2026-05-24
- [x] `make health-check` passes (SQLite checks) — 2026-05-24
- [ ] No duplicate RSS noise on spot-check (same story not 4×)
- [ ] Funding on 3 watchlist companies matches sources you’d quote

### P0-C — Seven green dailies (human gate)

- [ ] Green day 1 — date: ____
- [ ] Green day 2 — date: ____
- [ ] Green day 3 — date: ____
- [ ] Green day 4 — date: ____
- [ ] Green day 5 — date: ____
- [ ] Green day 6 — date: ____
- [ ] Green day 7 — date: ____

### P0-D — Verification commands

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make daily-prod
make rollup-all
make claims-audit-strict
make verify
make health-check
```

**P0 gate:** All P0-A/B/C checked → proceed to **E1** (can overlap E1-01..03 with late P0 if careful).

---

## E1 — Entrypoint consolidation (slice 2a)

**Done when:** Production path uses `apps/worker`, `apps/cli`, `packages/*` only — **no** `scripts/*.py`.  
**Detail:** [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) §3 slice 2a

- [ ] **2a-01** Move `fetch_x` + `fetch_xurl` → `apps/worker/x_refresh/`; `grok_refresh` imports module
- [ ] **2a-02** Move `export_x_monitor_queries`, `grok_x_normalize` into `grok_x_fetcher` (or worker)
- [ ] **2a-03** Move `claims_audit`, `sqlite_health` → `packages/py-core`
- [x] **2a-04** Replace `healthcheck.sh` with Python; `make health-check` unchanged UX — 2026-05-24
- [ ] **2a-05** Move `smoke_hermes_x_pipeline`, `eval_golden_set` under `tests/`
- [ ] **2a-06** Delete empty `scripts/`; update Makefile + Hermes docs (`call_intel.py`)
- [ ] Verify: `rg 'scripts/[a-z_]+\.py' Makefile apps/worker integrations/hermes` → no prod refs
- [ ] Verify: `make daily-prod`, `make grok-refresh`, `make verify` green

**E1 gate:** All 2a-* checked → proceed to **P1**.

---

## P1 — Score v0 + niche flags

**Product milestone:** Companies have `score`; AI/fintech/neobank soft boost; promotion hook exists (threshold TBD).  
**Detail:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — score v0

- [ ] Schema: `companies.score` (or equivalent) populated on daily path
- [ ] Schema: soft niche field(s) — `focus_tags` or `industry_bucket` for ai | fintech | neobank
- [ ] `company_ranker` (or successor) writes score v0 formula (document formula in code comment or `docs/SCORING.md` stub)
- [ ] Placeholder `research_tier` / `pipeline_depth` when score crosses config constant
- [ ] Dashboard-not-required: verify via SQL or `intel.py status`
- [ ] Tests: ranker/score smoke test added or updated

**P1 gate:** Score visible for top 20 companies in DB → **P2**.

---

## P2 — Trust tiers in data & exports

**Product milestone:** `unverified` | `speculative` | `verified` on claims/rounds; brief respects rules.  
**Detail:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — trust model

- [ ] Per-claim (or per-round) `trust_tier` persisted from source weight + corroboration
- [ ] `unverified` never in `daily_brief` export
- [ ] `speculative` allowed with label metadata for downstream UI
- [ ] `verified` requires policy hook (threshold constants in config — values TBD is OK)
- [ ] `make claims-audit-strict` extended or documented for trust violations
- [ ] Brief/daily export spot-check: no unverified funding lines

**P2 gate:** Trust tiers in DB + brief clean → **P3** (read API).

---

## P3 — Read API + initial dashboard

**Product milestone:** Three screens on **live** DB.  
**Detail:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — initial dashboard

### P3-A — Contract & API

- [ ] `packages/contracts/` — OpenAPI or JSON schema for companies, funding, breaking feed
- [ ] `apps/api` restored or created — **read-only** GET, `CI_DB_PATH`, WAL-safe
- [ ] Endpoints: company list (scored), company funding dossier, breaking queue
- [ ] API tests on isolated CI DB
- [ ] CORS/env for local dashboard dev

### P3-B — Dashboard UI

- [ ] `apps/dashboard` restored or created (SvelteKit + Bun)
- [ ] Screen 1: **Breaking** (funding, trust badges)
- [ ] Screen 2: **Companies** (score sort, niche filters)
- [ ] Screen 3: **Company → Funding** (claims, rounds, evidence)
- [ ] `bun run check` + smoke test in CI
- [ ] You open dashboard daily for 7 days (parallel habit gate)

**P3 gate:** All three screens on prod-like data → **P4**.

---

## P4 — Hermes on read API

**Product milestone:** Ask DB questions; draft posts from same rows as dashboard.

- [ ] Hermes tool definitions map to API routes (or documented SQLite read-only tools)
- [ ] Q&A: company funding, recent speculative/verified events
- [ ] Draft pack: top N events + brief excerpt JSON
- [ ] Hermes does **not** write verified funding without DB path
- [x] `call_intel.py` + [SCHEDULING.md](SCHEDULING.md) (Hermes cron) documented — 2026-05-24

**P4 gate:** You use Hermes + dashboard together for 2 weeks → **P5**.

---

## P5 — Scoring tuning

**Product milestone:** Promotion and verify thresholds set from **real** data.  
**Deferred numbers from PRODUCT_BRIEF now get filled here.**

- [ ] Review score distribution on neobank/fintech/AI corpus
- [ ] Set promote-to-research threshold (config file)
- [ ] Set speculative → verified threshold (config file)
- [ ] Document thresholds in `docs/SCORING.md` (create when tuning)
- [ ] Re-run backfill or relink if needed for historical claims
- [ ] Human sign-off: false positive test on 10 known deals

**P5 gate:** Thresholds documented + signed → **P6** (if SaaS) or **E3**.

---

## P6 — Freemium enforcement (when SaaS or public beta)

**Product milestone:** Free 6–10 speculative/week; verified free for all.

- [ ] Entitlement model in DB or API (free vs paid)
- [ ] Verified feed: no paywall
- [ ] Speculative: cap 6–10/week for free tier
- [ ] Paid: full speculative queue
- [ ] Tests for cap logic

---

## E2 — Enrich queues as code (slice 2b, optional)

**Only when you need Hermes enrich export/apply again.**  
**Detail:** [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) §3 slice 2b

- [ ] **2b-01** `enrichment/queue_export.py` + `queue_apply.py` + tests
- [ ] **2b-02** Funding + company queues (replaces deleted scripts)
- [ ] **2b-03** `intel.py enrich export|apply` subcommands

---

## E3 — Publish loop (slice 2c, optional)

**After P4 habit stable.**

- [ ] **2c-01** `apps/worker/publish/draft_builder.py` from brief + signals
- [ ] **2c-02** Human approve flag before any auto-post (if ever)

---

## P7 — Vectors / RAG (optional)

**Not ingest SSOT.** Search + Hermes accelerant only.

- [ ] Embedding model env single SSOT (`CI_OLLAMA_MODEL` or successor)
- [ ] Embed from verified + speculative claims (policy documented)
- [ ] No zero-vector fallback on failure
- [ ] Hermes semantic search tool optional
- [ ] Niche clustering experiment (replaces hard tags debate)

---

## Quick reference — doc map

| Question | Doc |
|----------|-----|
| Why are we building this? | [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) |
| What runs on cron today? | [PIPELINE.md](PIPELINE.md) |
| What got deleted / re-home scripts? | [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) |
| Naming / dead-code rules? | [ENGINEERING.md](ENGINEERING.md) |
| **What do I do next?** | **This file** — first unchecked box |

---

## Session log (optional — append only)

| Date | Agent / human | Completed IDs | Notes |
|------|---------------|---------------|-------|
| 2026-05-19 | Cursor | Linear bootstrap | [Competitor Intel project](https://linear.app/competitor-intel/project/competitor-intel-e52ae7293016) — milestones S0–P7/E2/E3, 86 issues from this checklist |
| 2026-05-19 | Cursor | Linear CI + labels | [docs/LINEAR.md](LINEAR.md), `.github/workflows/linear-sync.yml`, area/workflow labels, agent playbook |
