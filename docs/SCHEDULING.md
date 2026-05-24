# Scheduling — fresh dashboard, bounded Grok X quota

Goal: **RSS and open-web sources update often**; **Hermes `x_search` runs on a separate, lower-frequency cron** for verification and scoring boosts. The dashboard should show intelligence from the last few hours, not days ago.

## Three tiers

| Tier | Command | Typical cadence | What runs |
|------|---------|-----------------|-----------|
| **Frequent** | `make frequent` or `call_intel.sh frequent` | Every 1–2 hours | RSS, HN, Product Hunt, GitHub, TechCrunch/EDGAR slice → funding/deals extract → website → fanout → `signal_processor` → `funding_rollup` (no duplicate RSS walker — **6-COL02**) |
| **Grok X** | `make grok-refresh` or `call_intel.sh grok-refresh` | ~5×/day (see below) | `fetch_grok_x.py` → `x_signal_collector` → `signal_processor` → fanout |
| **Daily** | `make daily` / `make daily-tiered` / **`make daily-prod`** | 1×/day or after Grok windows | Full parallel collectors; prod cron uses **`daily-prod`** (`CI_SKIP_GROK_X=1`, `CI_STRICT_PIPELINE=1`, `CI_REQUIRE_DEDUP_INDEX=1`) |
| **Full sweep (on-demand)** | `make full-sweep` or `call_intel.sh full-sweep` | When you want everything fresh now | **`daily` first** (RSS/EDgar/etc + labels) → **enriched X queries** from DB → Hermes X fetch/ingest → funding rollup |
| **Repair** | `make intel-repair` | Weekly (Sun 03:00 ET) or pre-gate in daily | `signal_repair.py` — dedupe events, relink companies, backfill amounts before reclassify |

Use **`make daily-tiered`** (sets `CI_SKIP_GROK_X=1`) when Grok already ran via `grok-refresh` so the daily job does not double-call X.

**`make full-sweep`** is the operator “refresh everything” button: unlike `make daily` alone (which only auto-fetches X when `grok_x_results.json` is missing/stale), full sweep runs the **full daily pipeline first** so `export_x_monitor_queries.py --enriched` can build **targeted** X queries from recent `intelligence_events` labels, raw signal titles, and company handles. Optional **`CI_X_QUERY_AI_EXPAND=1`** (on by default in `full-sweep`) asks Hermes/xAI for a few extra query strings on top. Then `grok-refresh` fetches and ingests X; a final **`funding_rollup`** picks up new X funding signals.

Env knobs: `CI_X_QUERY_LOOKBACK_DAYS` (default 7), `CI_X_MAX_DERIVED_QUERIES`, `CI_X_MAX_AI_QUERIES`, `GROK_X_MAX_QUERIES` (default 18 in full-sweep).

SQLite: [SQLITE.md](SQLITE.md). Defaults: `CI_SQLITE_WRITER_LOCK=1`, `CI_PARALLEL_COLLECTORS=4`, `CI_SQLITE_BUSY_TIMEOUT_MS=120000`, `INSERT OR IGNORE` + batch EDGAR writer. If `database is locked` persists, stop other writers (API/dashboard) or set `CI_PARALLEL_COLLECTORS=2`.

## Recommended Eastern (America/New_York) schedule

Cron uses the server’s local timezone. On Omarchy/Linux, set `TZ=America/New_York` in the crontab or use explicit offsets.

### Option A — balanced (recommended)

```cron
# Frequent RSS / open web — dashboard stays <2h stale on weekdays
0 * * * 1-5  TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh frequent >> logs/frequent.log 2>&1

# Weekend: every 2 hours
0 */2 * * 0,6 TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh frequent >> logs/frequent.log 2>&1

# Grok X — 7:00, 9:00, 12:00, 16:30, 18:00 ET (weekdays + weekends)
0 7 * * *   TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh grok-refresh >> logs/grok.log 2>&1
0 9 * * *   TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh grok-refresh >> logs/grok.log 2>&1
0 12 * * *  TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh grok-refresh >> logs/grok.log 2>&1
30 16 * * * TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh grok-refresh >> logs/grok.log 2>&1
0 18 * * *  TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db ./integrations/hermes/call_intel.sh grok-refresh >> logs/grok.log 2>&1

# Full daily (jobs, embeddings, brief) — once at 6:30 AM ET, no duplicate Grok, strict pipeline
30 6 * * *  TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db make daily-prod >> logs/daily.log 2>&1

# Weekly signal repair (optional if daily already runs collectors/signal_repair.py)
0 3 * * 0 TZ=America/New_York cd $HOME/Documents/Competitor-Intel && CI_DB_PATH=$PWD/data/competitor_intel.db make intel-repair >> logs/repair.log 2>&1
```

### Option B — maximum freshness (more CPU)

Same as A, but run **`frequent` every 30 minutes** on weekdays (`*/30 * * * 1-5`). Keep Grok at 5×/day only.

### Hermes production runner

Existing wrapper (quota-aware):

```bash
~/.hermes/scripts/competitor_intel_prod.sh
```

Prefer **`./integrations/hermes/call_intel.sh daily`** or **`make daily-prod`** for the once-daily job. **`integrations/hermes/run_daily_prod.py`** is deprecated (thin wrapper — use `call_intel.sh` / `daily_intel.py`). Add separate cron lines for `frequent` and `grok-refresh` — do not run the full Hermes quota job hourly.

## Environment flags

| Variable | When |
|----------|------|
| `CI_DB_PATH` | Always — `data/competitor_intel.db` |
| `CI_SKIP_GROK_X=1` | `daily` / `daily-tiered` when Grok runs on its own cron |
| `CI_AUTO_GROK_X` / `CI_REQUIRE_GROK_X` | Set by `grok_refresh.py` and default `daily_intel.py` |
| `GROK_X_MAX_QUERIES` | Cap queries per Grok run (default 10) |

## Freshness checks

```bash
curl -s http://localhost:3000/api/status | jq '.freshness, .last24h'
```

Fields:

- `freshness.lastSignalAt` — newest `raw_signals.detected_at`
- `freshness.lastEventAt` — newest `intelligence_events.created_at`
- `freshness.lastXAt` — newest `x_posts.posted_at`

Wire these into the dashboard header next (world-class UX = visible “last updated” + 24h counts).

## Product direction (RSS-first, X for verify)

1. **Ingest breadth** — frequent tier pulls every RSS URL in `sources_registry` plus HN, GitHub, Product Hunt, etc.
2. **Classify fast** — `signal_processor` on every frequent run so the API/events feed updates within the hour.
3. **X as enrichment** — Grok batches confirm rumors, add social proof, and boost confidence on funding/job signals already seen via RSS.
4. **Heavy work daily** — ATS job boards (`job_tracker`), embeddings, investor pass, alerts, and brief generation once per day.

## Related docs

- [HANDBOOK.md](HANDBOOK.md) — pipeline stages
- [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md) — Grok OAuth path
- [AGENT_HANDOFF.md](AGENT_HANDOFF.md) — operator commands
