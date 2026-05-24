# Roadmap — entrypoint consolidation (no orphan scripts)

**Status:** Draft · **Depends on:** [PIPELINE.md](PIPELINE.md) (pipeline-only tree)  
**Product context:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md)  
**Checklist (mark 2a-* done here):** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) § E1  
**Audience:** Solo operator → later product; one machine, SQLite, Hermes Grok.

---

## 0. Decision record (read before building)

### What we are optimizing for

| Goal | Implication |
|------|-------------|
| Trustworthy daily intel | Batch pipeline with clear stages, fail-fast, auditable logs |
| Hermes for Grok/X | External agent stays; monorepo exposes **library + worker**, not shell soup |
| Twitter/content later | **Publish loop** is a separate concern from **ingest loop** |
| Professional repo | One orchestrator, one CLI surface, modules with tests — not 15 `scripts/*.py` |

### Scripts deleted in slice 1 (re-home as code, not bash)

These were removed from the tree; **do not restore as `scripts/`**. Implement as importable modules + worker/CLI calls.

| Removed path | Purpose | Target home (slice 2+) | Trigger |
|--------------|---------|------------------------|---------|
| `scripts/enrich_queue_export.py` | Export rows → Hermes JSONL queue | `packages/py-collectors/enrichment/queue_export.py` | Weekly or post-daily hook |
| `scripts/enrich_queue_apply.py` | Apply Hermes JSONL → DB | `packages/py-collectors/enrichment/queue_apply.py` | After agent run |
| `scripts/funding_enrich_export.py` | Funding-specific enrich export | `enrichment/funding_queue.py` | Same |
| `scripts/funding_enrich_apply.py` | Funding enrich apply | `enrichment/funding_queue.py` | Same |
| `scripts/company_enrich_export.py` | Company profile enrich export | `enrichment/company_queue.py` | Same |
| `scripts/company_enrich_apply.py` | Company enrich apply | `enrichment/company_queue.py` | Same |
| `scripts/migrate_ci_db.py` | Test DB migrate | `tests/support/db_fixture.py` only | pytest / CI |
| `scripts/seed_ci_e2e.py` | E2E seed data | `tests/fixtures/seed_e2e.py` | pytest only |
| `scripts/fetch_grok_x.py` | Duplicate Grok fetch wrapper | **Drop** — use `fetch_x` / `grok_x_fetcher` | — |

### Worker modules deleted in slice 1 (product backlog)

| Removed path | Purpose | Target home | Notes |
|--------------|---------|-------------|-------|
| `apps/worker/tweet_generator.py` | Draft posts from brief | `apps/worker/publish/draft_builder.py` | v2 — after ingest trusted |
| `apps/worker/discord_*.py` | Push brief to Discord | `packages/py-core/notifications/discord.py` | Optional channel; not daily default |
| `apps/worker/embed_*.py`, `embeddings.py` | Ollama embeddings | `collectors/enrichment/embedding_generator.py` (already exists) | Wire via registry flag, not standalone scripts |
| `apps/worker/generate_obsidian_notes.py` | Vault export | `apps/worker/export/obsidian.py` | Optional sink |
| `apps/worker/generate_intel_report.py` | Combined report | **Drop** — `daily_brief` is SSOT | — |
| `apps/worker/full_backfill.py` | One-off backfill | `apps/cli/intel.py backfill` subcommand | Rare ops |

---

## 1. Remaining `scripts/` — disposition (slice 2 audit)

| Current | Role | Verdict | Target |
|---------|------|---------|--------|
| `fetch_x.py` | Grok/xurl batch fetch | **Move** | `apps/worker/x_refresh/fetch.py` — called only from `grok_refresh.py` |
| `fetch_xurl.py` | xurl-only fetch | **Merge** | into `fetch.py` behind `CI_X_PROVIDER` |
| `export_x_monitor_queries.py` | Write query JSON + PROMPT | **Move** | `collectors/grok_x_fetcher.export_queries()` or worker method |
| `grok_x_normalize.py` | Normalize Hermes raw JSON | **Move** | `collectors/grok_x_fetcher.normalize_batch()` |
| `claims_audit.py` | Data-quality SQL audit | **Move** | `packages/py-core/qa/claims_audit.py` |
| `sqlite_health.py` | backup / checkpoint / analyze | **Move** | `packages/py-core/db/health.py` |
| `healthcheck.sh` | Operator probe | **Done** | `apps/cli/healthcheck.py` (`make health-check`) |
| `relink_actionable_orphans.py` | Repair orphan signals | **Move** | `collectors/signal_repair.relink_actionable()` |
| `reprocess_raw_signals.py` | Re-run processor | **Move** | `signal_processor` CLI flags `--reprocess` |
| `export_ingest_catalog.py` | Status JSON for ingest | **Move** | `packages/py-core/ingest/catalog.py` |
| `eval_golden_set.py` | Classifier eval | **Keep in dev** | `tests/tools/golden_eval.py` (not production surface) |
| `smoke_hermes_x_pipeline.py` | Manual smoke | **Move** | `tests/integration/test_hermes_x_smoke.py` |

**End state:** `scripts/` directory **empty or deleted**; `Makefile` targets call `uv run python -m apps.worker...` or `intel.py` only.

---

## 2. Orchestration model (cron vs “always on”)

### Recommended (batch cron)

```text
systemd timer / cron
    → make daily-prod          → daily_intel.py (batch, exit)
    → make grok-refresh        → grok_refresh.py (batch, exit)
    → make frequent            → frequent_intel.py (batch, exit)
```

Three **batch jobs**, three schedules. Professional and debuggable.

### Optional slice 3: single supervisor (if you want one long-lived process)

```text
ci-supervisor (systemd service, always on)
    ├── scheduler: RSS/frequent every 1h
    ├── scheduler: grok every 4h
    ├── scheduler: daily-prod 06:00
    └── overlap lock + health HTTP :9090/healthz
```

Same work as cron; difference is **one binary** and internal queue. Cost: harder to reason about failures, must handle SIGTERM cleanly. **Defer until `make verify` and 7 green dailies pass.**

### Not recommended now

| Idea | Why |
|------|-----|
| Always-on RSS poll loop | Duplicates `frequent_intel`; burns CPU; harder to test |
| Replace all cron with supervisor | Ops complexity before product fit |
| New microservices | Solo operator; SQLite SSOT |

---

## 3. Phased delivery

### Slice 2a — Entrypoint consolidation (1–2 weeks)

**Done when:** `make daily-prod`, `make grok-refresh`, `make health-check`, `make claims-audit-strict` invoke **only** `apps/worker/*`, `apps/cli/intel.py`, or `python -m packages...` — zero production `scripts/*.py`.

| ID | Task | Acceptance |
|----|------|------------|
| **2a-01** | Move `fetch_x` + `fetch_xurl` → `apps/worker/x_refresh/` | `grok_refresh` imports module; delete `scripts/fetch_*.py` |
| **2a-02** | Move `export_x_monitor_queries`, `grok_x_normalize` into `grok_x_fetcher` | Hermes path documented; one import path |
| **2a-03** | Move `claims_audit`, `sqlite_health` into `py-core` | `make claims-audit` / `sqlite-backup` unchanged |
| **2a-04** | Replace `healthcheck.sh` with Python | **Done** — `apps/cli/healthcheck.py` |
| **2a-05** | Move smoke + golden eval under `tests/` | Not in operator docs |
| **2a-06** | Delete empty `scripts/`; update Makefile + Hermes shim | `rg 'scripts/' Makefile` → only comments or none |

### Slice 2b — Enrich as pipeline code (when you need Hermes apply again)

**Done when:** export/apply are importable; optional `CI_ENRICH_AFTER_DAILY=1` runs export → (manual/agent) → apply documented.

| ID | Task | Acceptance |
|----|------|------------|
| **2b-01** | Implement `enrichment/queue_export.py` + `queue_apply.py` | Unit tests with temp JSONL |
| **2b-02** | Wire `funding` + `company` queues (from deleted scripts) | Same schema as before delete |
| **2b-03** | `intel.py enrich export|apply` subcommands | No standalone scripts |

### Slice 2c — Publish loop (Twitter — after 7 green dailies)

| ID | Task | Acceptance |
|----|------|------------|
| **2c-01** | `publish/draft_builder.py` from brief + top signals | Markdown/JSON drafts, no auto-post |
| **2c-02** | Optional scheduler (cron or supervisor job) | Posts only after human approve flag in DB |

---

## 4. Verification (slice 2)

```bash
uv sync
make verify
make health-check
# No production dependency on scripts/
rg 'scripts/[a-z_]+\.py' Makefile apps/worker integrations/hermes --glob '!tests/**'
```

---

## 5. Doc hygiene (parallel)

| Action | Files |
|--------|-------|
| Keep as SSOT | `PIPELINE.md`, `ENGINEERING.md`, this file, `SCHEDULING.md`, `SQLITE.md` |
| Trim stale refs | `SCHEDULING.md` if it mentions deleted apps |
| Do not resurrect | `ROADMAP.md`, legacy doc shards, `HANDBOOK.md` (git history only) |

---

## 6. Single CLI surface (target)

```bash
uv run python -m apps.cli.intel daily-prod    # or: make daily-prod → same
uv run python -m apps.cli.intel grok-refresh
uv run python -m apps.cli.intel health
uv run python -m apps.cli.intel audit claims --strict
uv run python -m apps.cli.intel enrich export  # slice 2b
```

`integrations/hermes/call_intel.py` is the Hermes bridge; schedule via `hermes cron` + `cron_*.py` ([SCHEDULING.md](SCHEDULING.md)).
