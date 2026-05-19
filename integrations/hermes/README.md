# Hermes → Competitor Intel (thin client)

Hermes agents should **not** import Python from the old agent tree. Point agents at this monorepo via HTTP or shell. Ingest lands in `raw_signals` through `packages/py-collectors` + `apps/worker` — not a parallel `wave_one` stack.

## Quick calls

```bash
# API health
./call_intel.sh status

# Company list
./call_intel.sh companies 50

# Run daily pipeline (requires venv + deps on host)
./call_intel.sh daily
```

## Configuration

| Env | Default |
|-----|---------|
| `COMPETITOR_INTEL_ROOT` | `~/Documents/Competitor-Intel` |
| `CI_API_URL` | `http://localhost:3000` |
| `CI_DB_PATH` | `$MONOREPO/data/competitor_intel.db` |

Full guide: [docs/HERMES_INTEGRATION.md](../../docs/HERMES_INTEGRATION.md) · [architecture detail](../../docs/architecture/HERMES_INTEGRATION.md)

**Hermes agents:** run only this script (or HTTP API). Do not execute Python under `~/.hermes/agents/competitor_intel/` except the forwarder below.

### Restore pre-split Grok ingest (same as `process_grok_x_results` in-agent)

```bash
# From Hermes execute_code or shell — writes to CI_DB_PATH
./call_intel.sh grok-x company Anthropic --file /tmp/posts.json
./call_intel.sh grok-x query '("raised" OR "Series")' --file /tmp/posts.json
./call_intel.sh grok-x batch --file data/hermes_enrich/grok_x_results.json

# Legacy forwarder (still works from old agent cwd):
~/.hermes/agents/competitor_intel/ingest_grok_x.sh company Anthropic --file /tmp/posts.json
```

## Enrich queue (labels + company linkage)

No local LLM in the monorepo. Export uncertain events, let Grok fix them, apply results:

```bash
cd "$COMPETITOR_INTEL_ROOT"
make enrich-queue-export    # → data/hermes_enrich/enrich_queue.jsonl + companies_catalog.json
make funding-enrich-export  # → funding_enrich_queue.jsonl (per-claim investors/deal fields)
make funding-enrich-apply   # after Hermes writes funding_enrich_results.jsonl
# Hermes: read PROMPT.md, write enrich_results.jsonl
make enrich-queue-apply
```

Also run deterministic relink first:

```bash
make relink-actionable
```

## X / Twitter discovery (Grok via Hermes)

X posts use the **same Hermes path as before the monorepo split**: `tools.x_search_tool`
with **xai-oauth** (SuperGrok / X.com). `make grok-x-fetch` imports Hermes from
`~/.hermes/hermes-agent` — not a separate API-key client and not Ollama.

```bash
# Prereq (once): hermes auth add xai-oauth

make export-x-queries    # PROMPT_X.md + query list
make grok-x-fetch        # Hermes x_search → grok_x_results.json
make grok-x-ingest       # persist + url fanout + funding
make smoke-hermes-x      # 1 live x_search query + ingest
```

`make daily` sets `CI_AUTO_GROK_X=1` and calls Hermes fetch when the batch file is missing.

You can still paste Hermes session JSON: `make grok-x-normalize INPUT=...` then ingest.
Or: `./call_intel.sh grok-x batch --file data/hermes_enrich/grok_x_results.json`

`signal_url_fanout` promotes outbound article URLs from X/HN into `raw_signals` (`source=article`) for funding extraction on the primary source.
