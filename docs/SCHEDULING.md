# Scheduling (Hermes cron)

Use **Hermes built-in scheduler** — not system crontab or bash wrappers.  
Docs: [Automate with Cron](https://hermes-agent.nousresearch.com/docs/guides/automate-with-cron) · [Scheduled Tasks](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)

**Ops:** [PIPELINE.md](PIPELINE.md) · **Bridge:** [integrations/hermes/README.md](../integrations/hermes/README.md)

## Gateway (required)

Jobs only fire when the Hermes gateway is running:

```bash
hermes cron status          # scheduler up?
hermes gateway install      # background service (user)
# Linux server: sudo hermes gateway install --system
```

Debug one tick: `hermes cron tick`

## Production jobs (`--no-agent`)

Pipeline runs are **Python scripts** — no LLM, no bash. Hermes executes the script on schedule and can deliver stdout (`--deliver local`).

Hermes only accepts real files under `~/.hermes/scripts/` (filename only; **no symlinks**). After changing cron scripts in the repo, re-install:

```bash
cd ~/Documents/Competitor-Intel
uv run python integrations/hermes/install_hermes_cron_scripts.py
```

Register jobs:

```bash
# Daily 06:00 — strict daily-prod (no inline Grok)
hermes cron create "0 6 * * *" \
  --no-agent \
  --script ci_cron_daily_prod.py \
  --name "competitor-intel-daily-prod" \
  --deliver local

# Grok X — 5×/day example
hermes cron create "0 8,11,14,17,20 * * *" \
  --no-agent \
  --script ci_cron_grok_refresh.py \
  --name "competitor-intel-grok-refresh" \
  --deliver local

# Optional: frequent RSS tier (hourly weekdays)
hermes cron create "0 * * * 1-5" \
  --no-agent \
  --script ci_cron_frequent.py \
  --name "competitor-intel-frequent" \
  --deliver local

# Weekly Sun 05:00 — SEC Form D bulk (private fundraising ZIP; not on daily)
hermes cron create "0 5 * * 0" \
  --no-agent \
  --script ci_cron_edgar_weekly.py \
  --name "competitor-intel-edgar-form-d-weekly" \
  --deliver local
```

Pause legacy bash sweep if still enabled: `hermes cron pause 82e7afec268b` (old `competitor_intel_prod.sh` job).

Test immediately:

```bash
hermes cron list
hermes cron run <job_id>    # runs on next gateway tick
```

## Schedule syntax (Hermes)

| Format | Example |
|--------|---------|
| Interval | `every 2h`, `every 30m` |
| Cron | `0 6 * * *` (minute hour dom month dow) |
| One-shot delay | `30m`, `2h` |

Natural language like “daily at 9am” is **not** supported — use `0 9 * * *`.

## Manual / Hermes chat

From terminal (same as old shell shim):

```bash
uv run python integrations/hermes/call_intel.py daily-prod
uv run python integrations/hermes/call_intel.py grok-refresh
uv run python integrations/hermes/call_intel.py status
```

Or `make daily-prod`, `make grok-refresh` from repo root.

In Hermes chat you can also ask: “create a cron job every day at 6am to run competitor intel daily-prod” — Hermes uses the `cronjob` tool (`/cron add ...`).

## Optional: LLM cron with `--workdir`

If you want Hermes to reason about failures (higher cost):

```bash
hermes cron create "0 6 * * *" \
  --workdir "$CI_ROOT" \
  --name "competitor-intel-daily-agent" \
  --deliver local \
  "Run: uv run python integrations/hermes/call_intel.py daily-prod. Report exit code and log summary. If success, respond [SILENT]."
```

Prefer **`--no-agent`** scripts above for production ingest.

## Logs

Cron output with `--deliver local` goes to Hermes delivery storage; pipeline logs also append under `logs/` when you run manually (`tee logs/daily.log`).

## Freshness (no API)

```bash
export CI_DB_PATH="$CI_ROOT/data/competitor_intel.db"
sqlite3 "$CI_DB_PATH" "SELECT MAX(detected_at) FROM raw_signals;"
```

## Manage jobs

```bash
hermes cron list
hermes cron pause <id>
hermes cron resume <id>
hermes cron edit <id> --schedule "every 4h"
hermes cron remove <id>
```
