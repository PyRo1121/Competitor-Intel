# Architecture

Pipeline-only monorepo: Python collectors write SQLite; worker orchestrates daily ingest; Hermes supplies Grok/X batches.

## Layout

```
Competitor-Intel/
├── packages/py-core/          # DB schema, ingest, alerts (alert_engine optional)
├── packages/py-collectors/    # Collectors + rollups
├── apps/worker/               # daily_intel.py, grok_refresh.py, daily_brief.py
├── apps/worker/automation/    # collector_registry, parallel_collect, run_utils
├── apps/cli/                  # intel.py, run_intel.py (thin schema gate)
├── integrations/hermes/       # call_intel.py, cron_*.py, ingest_grok_x.py
├── scripts/                   # claims_audit, Grok/X helpers (migrate to packages in E1)
├── tests/
└── data/                      # SQLite + generated exports (gitignored)
```

Symlinks at repo root: `collectors` → `packages/py-collectors/collectors`, `automation` → `apps/worker/automation`, `intel.py`, `run_intel.py`.

## Daily flow

1. `parallel_collect.py` — RSS/open-web ingest (`CI_SKIP_GROK_X=1` on `daily-prod`)
2. `run_intel.py` — schema check only (extraction scripts empty; use `signal_processor` in sequential)
3. Sequential steps from `collector_registry.get_daily_sequential()` — processor, rollups, `daily_brief --export`
4. Separate cron: `grok_refresh.py` → `x_refresh/fetch.py` → `x_signal_collector`

**Canonical entry:** `apps/worker/daily_intel.py` only.

## Toolchain

| Tool | Role |
|------|------|
| uv | Python 3.12 workspace (`py-core`, `py-collectors`) |
| SQLite | `CI_DB_PATH` (default `data/competitor_intel.db`) |
| Hermes agent | External; `call_intel.py` + `hermes cron` ([SCHEDULING.md](SCHEDULING.md)) |
