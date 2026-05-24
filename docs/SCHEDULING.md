# Scheduling

Goal: **RSS and open-web sources update often**; **Hermes `x_search` runs on a separate cron** so `daily-prod` does not burn Grok quota inline.

**Ops SSOT:** [PIPELINE.md](PIPELINE.md) · **Checklist:** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) (P0-A = install crontab on your machine)

## Tiers

| Tier | Command | Typical cadence | What runs |
|------|---------|-----------------|-----------|
| **Frequent** | `make frequent` or `call_intel.sh frequent` | Every 1–2 h (optional) | RSS, HN, YC, GitHub, TechCrunch/EDGAR slice → website → fanout → `signal_processor` → funding rollup (no X) |
| **Grok X** | `make grok-refresh` or `call_intel.sh grok-refresh` | ~5×/day | `grok_refresh.py` → X fetch/ingest → processor/fanout as configured |
| **Daily (prod)** | **`make daily-prod`** | 1×/day | Full parallel ingest **without** inline Grok (`CI_SKIP_GROK_X=1`, strict pipeline, dedup index) → sequential rollups → `daily_brief` |
| **Full sweep** | `make full-sweep` | On demand | Daily pipeline + enriched X query export + `grok-refresh` + rollup |
| **Repair** | `make intel-repair` | Weekly (optional) | `signal_repair.py` |

Use **`make daily-tiered`** when Grok already ran via `grok-refresh` so the daily job does not double-call X.

SQLite: [SQLITE.md](SQLITE.md). Defaults: `CI_SQLITE_WRITER_LOCK=1`, `CI_PARALLEL_COLLECTORS=4`, `CI_SQLITE_BUSY_TIMEOUT_MS=120000`. If `database is locked`, stop other writers or set `CI_PARALLEL_COLLECTORS=2`.

## Minimal production crontab

Matches [PIPELINE.md](PIPELINE.md) — adjust paths and timezone.

```cron
# Daily ingest (no inline Grok)
0 6 * * * cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db make daily-prod >> logs/daily.log 2>&1

# Grok X — example: 8:00, 11:00, 14:00, 17:00, 20:00 local
0 8,11,14,17,20 * * * cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db make grok-refresh >> logs/grok.log 2>&1
```

Optional: `make frequent` hourly on weekdays if you want fresher RSS without waiting for daily.

## Eastern (America/New_York) example

```cron
0 6 * * *   TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db make daily-prod >> logs/daily.log 2>&1
0 8,11,14,17,20 * * * TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db make grok-refresh >> logs/grok.log 2>&1
```

Hermes wrapper (quota-aware): `~/.hermes/scripts/competitor_intel_prod.sh` or `./integrations/hermes/call_intel.sh daily` / `grok-refresh`. Do not run full Grok quota jobs hourly.

## Environment flags

| Variable | When |
|----------|------|
| `CI_DB_PATH` | Always — `data/competitor_intel.db` |
| `CI_SKIP_GROK_X=1` | `daily-prod` / `daily-tiered` when Grok runs on its own cron |
| `GROK_X_MAX_QUERIES` | Cap queries per Grok run |

## Freshness checks (no API required)

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
sqlite3 "$CI_DB_PATH" "SELECT MAX(detected_at) FROM raw_signals;"
sqlite3 "$CI_DB_PATH" "SELECT MAX(created_at) FROM intelligence_events;"
```

## Related docs

- [PIPELINE.md](PIPELINE.md) — collectors and verification
- [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md) — Grok boundaries
- [integrations/hermes/README.md](../integrations/hermes/README.md) — `call_intel.sh`
