# Deploy — single-host production (Track 6 Phase B)

Bare-metal operator setup for API + SQLite + cron. No Docker required for the default path.

## Environment (prod cron)

| Variable | Prod value | Purpose |
|----------|------------|---------|
| `CI_DB_PATH` | `$REPO/data/competitor_intel.db` | SQLite corpus |
| `CI_SKIP_GROK_X` | `1` on `daily` / `daily-prod` | Grok runs on separate `grok-refresh` cron |
| `CI_STRICT_PIPELINE` | `1` | Block legacy `funding_events` writes |
| `CI_REQUIRE_DEDUP_INDEX` | `1` | Fail ingest if dedup index missing |
| `CI_COMPANY_DATA_ROLLUP` | `1` (default-on) | Post-daily company/regulatory/cap rollups |
| `HERMES_AGENT_ROOT` | Optional path to Hermes agent dir | Grok fetch scripts |
| `CI_API_KEY` | Secret | Required for POST/DELETE `/api/*` |
| `CI_API_CORS_ORIGINS` | Dashboard origin(s) | Comma-separated |
| `CI_SQLITE_POST_BACKUP` | `1` (default) | Timestamped backup after successful daily |

Copy from repo root `.env.example` and fill secrets locally (never commit).

## API (systemd example)

```ini
# /etc/systemd/system/ci-api.service
[Unit]
Description=Competitor Intel API
After=network.target

[Service]
Type=simple
User=pyro1121
WorkingDirectory=/home/pyro1121/Documents/Competitor-Intel/apps/api
Environment=CI_DB_PATH=/home/pyro1121/Documents/Competitor-Intel/data/competitor_intel.db
Environment=PORT=3000
Environment=CI_API_KEY=change-me
ExecStart=/home/pyro1121/.local/bin/bun run src/index.ts
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ci-api
curl -s http://127.0.0.1:3000/health | jq .
```

`/health` returns **503** with `missingTables` if schema is behind code — run `make migrate-db` (stop API first if `database is locked`).

## Dashboard (static build)

```bash
cd apps/dashboard
export PUBLIC_CI_API_URL=http://127.0.0.1:3000
bun run build
# Serve build/ via nginx or: bun run preview
```

Set `PUBLIC_CI_API_URL` to the URL the **browser** uses (LAN hostname or reverse proxy), not only loopback.

## Cron (see SCHEDULING.md)

- **Frequent:** hourly RSS/open-web (`call_intel.sh frequent`)
- **Grok:** 5×/day (`call_intel.sh grok-refresh`)
- **Daily:** `make daily-prod` once (6:30 AM ET example)
- **Weekly:** `make intel-repair`; optional `make enrich-all-export` then Hermes then `make enrich-all-apply`

## Verification

```bash
make health-check CI_API_URL=http://127.0.0.1:3000
make claims-audit-strict
make supply-chain    # uv lock --check, pip-audit, bun audit (see Makefile for ollama ignores)
```

Optional stale-signal gate:

```bash
CI_HEALTH_FRESHNESS_MAX_HOURS=48 make health-check
```

## Related

- [SCHEDULING.md](SCHEDULING.md) — tiered crons
- [HANDBOOK.md](HANDBOOK.md) — pipeline
- [SQLITE.md](SQLITE.md) — WAL, backups, locks
