# v1 — Pipeline-first (solo operator)

**Status:** Active north star · **Supersedes** “build all of Track 6 at once” for day-to-day work.

## What v1 is

One machine, one SQLite DB, one cron, one daily artifact you trust — then optional Hermes Grok/X on a **separate** cron.

| In v1 | Out of v1 (removed) |
|-------|---------------------|
| `make daily-prod` → rollups → `make claims-audit-strict` | Bun API (`apps/api`), Svelte dashboard (`apps/dashboard`) |
| Hermes / `grok_refresh` / `integrations/hermes/` | SQLAlchemy `packages/py-enterprise` stack |
| `apps/cli` (`intel`, `run_intel`) | Public API auth, WAN deploy (Track 6 Phase D) |
| `daily_brief` export | Legacy funding extractors, duplicate RSS walkers |
| Slim collector set in `collector_registry.py` | |

The read surface and py-enterprise packages were **deleted** (not archived). Restore from git history if needed for v2.

## v1 done checklist

Run on **your** prod DB after a normal week:

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make daily-prod
make rollup-all          # if rollups not inlined in daily env
make claims-audit-strict
```

**Human bar:** Read today’s brief; spot-check 3 watchlist companies; no duplicate RSS noise; funding claims match sources you’d tweet about.

**7 green dailies in a row** = v1 complete. Only then invest in read UI or tweet automation.

## Cron (recommended)

```bash
# Every day — no inline Grok (saves quota; Hermes runs separately)
0 6 * * * cd /path/to/Competitor-Intel && make daily-prod >> logs/daily.log 2>&1

# 5×/day ET — Hermes Grok x_search batch (optional but recommended for X intel)
0 8,11,14,17,20 * * * cd /path/to/Competitor-Intel && make grok-refresh >> logs/grok.log 2>&1
```

Env: copy `.env.example` → `.env`; set `HERMES_AGENT_ROOT` if not using `~/.hermes/hermes-agent`.

## Active collectors (registry only)

**Parallel (daily, no X):** RSS, Hacker News, YC, GitHub signals, TechCrunch/EDGAR, SEC EDGAR, ESMA MiCA.

**Grok (separate cron):** `x_signal_collector.py` via `make grok-refresh`.

**Sequential:** website monitor → URL fanout → jobs tracker → signal processor → repair → quality gate → discovery/promote/rank → funding rollup → optional company/regulatory/cap rollups → daily brief.

Not on daily: Product Hunt, Crunchbase, AngelList, YouTube, momentum/competitor mappers, embeddings, tweet generator, enrichment runner.

On-demand only: `uv run python apps/cli/intel.py <name>` for scripts still in tree with `__main__` but not on the daily schedule.

## Verification

```bash
uv sync
make v1-check    # compile, test-cov, intel-gate, golden-eval, claims-audit-strict
make health-check
```

## Related docs

- [ROADMAP_PRODUCTION.md](ROADMAP_PRODUCTION.md) — full audit backlog (v2+)
- [PIPELINE.md](PIPELINE.md) — data flow
- [integrations/hermes/README.md](../integrations/hermes/README.md) — Hermes entrypoints
