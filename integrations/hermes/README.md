# Hermes → Competitor Intel

Hermes agents must **not** import Python from `~/.hermes/agents/competitor_intel/`. Use this monorepo via **`call_intel.sh`** or the HTTP API only.

**Technical reference:** [docs/architecture/HERMES_INTEGRATION.md](../../docs/architecture/HERMES_INTEGRATION.md)

## Environment

| Variable | Default |
|----------|---------|
| `COMPETITOR_INTEL_ROOT` | `~/Documents/Competitor-Intel` |
| `CI_DB_PATH` | `$MONOREPO/data/competitor_intel.db` |
| `CI_API_URL` | `http://localhost:3000` |
| `CI_DISABLE_HERMES` | unset — set to `1` in CI to no-op `grok-refresh`, `grok-x`, `grok-x-fetch` |
| `CI_SKIP_GROK_X` | unset — same effect for daily (`daily_intel.py`) and Hermes shim |
| `CI_X_PROVIDER` | `grok` (default) or `xurl` — X fetch backend for `grok-refresh` / `fetch_x.py` |
| `XURL_SEARCH_N` | Posts per search query when `CI_X_PROVIDER=xurl` (default `10`) |
| `XURL_MAX_QUERIES` | Query cap for xurl batch fetch (default `10`) |

## Commands (`call_intel.sh`)

```bash
export COMPETITOR_INTEL_ROOT=~/Documents/Competitor-Intel
export CI_DB_PATH="$COMPETITOR_INTEL_ROOT/data/competitor_intel.db"

./call_intel.sh status          # API health
./call_intel.sh full-sweep      # on-demand: daily first, enriched X queries, then X ingest
./call_intel.sh daily           # full pipeline (apps/worker/daily_intel.py)
./call_intel.sh frequent        # RSS / open-web tier
./call_intel.sh grok-refresh    # Grok X batch only (~5×/day cron)
./call_intel.sh grok-x-ingest   # ingest grok_x_results.json + fanout + funding rollup
./call_intel.sh intel           # signal processing (apps/cli/run_intel.py)
./call_intel.sh cli -- <args>   # apps/cli/intel.py subcommands
./call_intel.sh companies 50
./call_intel.sh grok-x batch --file data/hermes_enrich/grok_x_results.json
```

From monorepo root: `make full-sweep` (on-demand everything fresh), `make daily`, `make intel`, `make grok-refresh`.

## Deprecated (Hermes tree)

| Legacy | Use instead |
|--------|-------------|
| `~/.hermes/.../automation/daily_intel.py` | `call_intel.sh daily` |
| `~/.hermes/.../run_intel.py` | `call_intel.sh intel` |
| `~/.hermes/.../intel.py` | `call_intel.sh cli` |
| Direct `python collectors/*.py` in Hermes | `call_intel.sh daily` |

See [MIGRATED.md](../../MIGRATED.md).

## Enrich queues (Grok batch)

```bash
cd "$COMPETITOR_INTEL_ROOT"
make relink-actionable
make enrich-queue-export      # → data/hermes_enrich/enrich_queue.jsonl
# Hermes writes enrich_results.jsonl
make enrich-queue-apply

make funding-enrich-export
make funding-enrich-apply     # after funding_enrich_results.jsonl
```

Prompts: `data/hermes_enrich/PROMPT_X.md`, `PROMPT_FUNDING.md`.

## X ingest (Hermes subscription — default)

**Canonical path** (see [docs/architecture/HERMES_INTEGRATION.md](../../docs/architecture/HERMES_INTEGRATION.md)): X search goes through **Hermes + xAI OAuth** (`x_search`), same as interactive Hermes. Uses your **SuperGrok / Hermes subscription** — not a separate X Developer pay-per-use account.

Prerequisite (once):

```bash
hermes auth add xai-oauth
```

Batch/cron (monorepo — no separate X dev portal billing):

```bash
make export-x-queries
make grok-x-fetch-smoke          # CI_X_PROVIDER=grok (default)
make grok-x-ingest
make grok-refresh                # or ./call_intel.sh grok-refresh
```

Interactive Hermes agent: use the **`xurl` skill** for post/reply/DM when you want hands-on X API commands inside chat; batch ingest above uses **`x_search`** via `grok_x_fetcher.py` (subscription).

### Optional: direct `xurl` CLI (`CI_X_PROVIDER=xurl`)

Separate from Hermes subscription — requires your own [developer.x.com](https://developer.x.com/en/portal/dashboard) app and **X API credits**. Use only if you want REST-speed search without Grok, or dedicated posting automation outside `x_search`.

```bash
make x-check                     # needs xurl + ~/.xurl OAuth
CI_X_PROVIDER=xurl make x-fetch  # bills X API, not xAI subscription
```

Does **not** change Hermes model config. Default remains `CI_X_PROVIDER=grok`.

`make daily` can set `CI_AUTO_GROK_X=1` when the batch file is missing. Scheduling: [docs/SCHEDULING.md](../../docs/SCHEDULING.md).

## Database

Copy legacy DB once:

```bash
cp ~/.hermes/agents/competitor_intel/competitor_intel.db ~/Documents/Competitor-Intel/data/
```
