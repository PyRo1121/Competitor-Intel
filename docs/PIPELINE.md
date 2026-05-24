# Pipeline operations (solo operator)

**Status:** Active north star · **Product:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) · **Checklist:** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) · **Standards:** [ENGINEERING.md](ENGINEERING.md)

## What runs in production

One machine, one SQLite DB, one cron, one daily artifact you trust — then optional Hermes Grok/X on a **separate** cron.

| In production | Removed (git history only) |
|---------------|----------------------------|
| `make daily-prod` → rollups → `make claims-audit-strict` | REST dashboard / public API |
| Hermes / `grok_refresh` / `integrations/hermes/` | SQLAlchemy enterprise duplicate stack |
| `apps/cli` (`intel`, `run_intel`) | Public API auth, WAN deploy |
| `daily_brief` export | Legacy funding extractors, duplicate RSS walkers |
| Slim collector set in `collector_registry.py` | |

## Production readiness checklist

Run on **your** prod DB after a normal week:

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make daily-prod
make rollup-all          # if rollups not inlined in daily env
make claims-audit-strict
```

**Human bar:** Read today’s brief; spot-check 3 watchlist companies; no duplicate RSS noise; funding claims match sources you’d tweet about.

**7 green dailies in a row** completes checklist **P0**. Only then invest in read UI or tweet automation.

## Cron (recommended)

```bash
# Every day — no inline Grok (saves quota; Hermes runs separately)
0 6 * * * cd /path/to/Competitor-Intel && make daily-prod >> logs/daily.log 2>&1

# 5×/day ET — Hermes Grok x_search batch (optional but recommended for X intel)
0 8,11,14,17,20 * * * cd /path/to/Competitor-Intel && make grok-refresh >> logs/grok.log 2>&1
```

Env: copy `.env.example` → `.env`; set `HERMES_AGENT_ROOT` if not using `~/.hermes/hermes-agent`.

## Active collectors (registry only)

**Parallel (daily, no X):** RSS, Hacker News, YC, GitHub signals, TechCrunch funding scrape, ESMA MiCA.

**Weekly (Form D bulk):** `make edgar-form-d-weekly` — SEC Form D quarterly ZIP (US private rounds / Reg D). Not on daily (SQLite writer load).

**Grok (separate cron):** `x_signal_collector.py` via `make grok-refresh`.

**Sequential:** website monitor → URL fanout → jobs tracker → signal processor → repair → quality gate → discovery/promote/rank → funding rollup → optional company/regulatory/cap rollups → daily brief.

Not on daily: Product Hunt, Crunchbase, AngelList, YouTube, momentum/competitor mappers, embeddings, tweet generator, enrichment runner.

On-demand only: `uv run python apps/cli/intel.py <name>` for scripts still in tree with `__main__` but not on the daily schedule.

## Fetch concurrency

Collectors fetch many URLs in parallel (threads); SQLite writes batch under one `writer_lock` per collector to avoid `database is locked`.

| Env | Default | Role |
|-----|---------|------|
| `CI_RSS_FETCH_WORKERS` | 20 | RSS feeds in parallel |
| `CI_HN_FETCH_WORKERS` | 24 | HN story + comment fetches |
| `CI_WEBSITE_FETCH_WORKERS` | 16 | Company homepages |
| `CI_PARALLEL_COLLECTORS` | 3 | Collector **subprocesses** at once (lower = less DB contention) |

## Verification

```bash
uv sync
make verify    # compile, test-cov, intel-gate, golden-eval, claims-audit-strict
make health-check
```

## Related docs

- [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) — vision, trust tiers, freemium, dashboard phases
- [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) — scripts → modules; deleted script registry
- [README.md](README.md) — doc index
- [SCHEDULING.md](SCHEDULING.md) — cron tiers
- [integrations/hermes/README.md](../integrations/hermes/README.md) — Hermes entrypoints
