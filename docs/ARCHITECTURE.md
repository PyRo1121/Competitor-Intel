# Competitor Intel Architecture

> **Monorepo (May 2026):** Canonical root is `~/Documents/Competitor-Intel/`. Paths below use legacy names; map `collectors/` → `packages/py-collectors/`, `automation/` → `apps/worker/automation/`, `api/` → `apps/api/`.

## Dual stack (May 2026)

| Layer | Path | Storage | Status |
|-------|------|---------|--------|
| Operational | `collectors/`, `automation/` | SQLite `competitor_intel.db` | Production daily pipeline |
| Enterprise | `src/competitor_intel/` | Same DB path via `CI_DB_PATH` | SQLAlchemy collectors; optional CLI |

Daily production flow uses **Version A** (`automation/daily_intel.py`). Enterprise package is wired incrementally via `automation/enterprise_collect.py` → `python -m competitor_intel.cli collect -c rss`.

## Data flow

```
Sources (RSS, GitHub, SEC, …)
  → raw_signals (dedup: UNIQUE source + signal_type)
  → signal_processor_v2 → intelligence_events
  → enrichment / alerts / briefs
```

`signal_type` is typically a URL hash (`url_dedup_key`). Human-readable categories live in `data_json` (`kind`, `category`, `channel_company`).

## Parallel collection

Independent collectors run in `automation/parallel_collect.py` (thread pool, max 6 workers) after `run_intel.py`. Processor and enrichment stay sequential.

## HTTP layer

Shared sync `httpx.Client` with connection pooling: `utils/http.py`. High-traffic collectors (RSS, multi-source, GitHub) use this instead of `requests`.

## Migration path (enterprise)

1. Run operational collectors until parity on ingest metrics.
2. Point enterprise `CI_DB_PATH` at the same SQLite file as `db/connection.DB_PATH`.
3. Enable one collector via `enterprise_collect.py` / CLI; compare row counts.
4. Port remaining sources to `src/competitor_intel/collectors/` behind `PipelineRunner`.
5. Retire duplicate scripts in `collectors/` per source.

## Ingest API

Prefer `db/ingest.insert_raw_signal_dedup()` for all new signals. Use `dedup_key=` for scoped keys (e.g. RSS per-company rows).

## Data source catalog

Canonical feed list: `collectors/sources_registry.py` (`FeedSource` records with `enabled`, `trust_tier`, `category`).

| Category | Enabled feeds | Examples |
|----------|---------------|----------|
| news | 13 | TechCrunch, VentureBeat, The Verge, Tech.eu |
| ai | 5 | OpenAI, DeepMind, Google AI, Hugging Face |
| vc | 2 | Lightspeed, Y Combinator Blog |
| funding | 1 | Crunchbase News |
| community | 3 | Hacker News, HN Show, HN high-signal |
| products | 1 | Product Hunt |
| newsletter | 3 | Stratechery, Lenny's, Elad Gil |
| regulatory | 1 | EU Digital Strategy |
| sec | 1 | SEC current filings Atom |

Disabled entries in the registry document broken URLs (e.g. Sequoia `/blog/rss/` 404, a16z feed 404) — do not re-enable without HTTP verification.

Collectors wired to the registry: `rss_collector.py`, `multi_source_collector.py`. Other collectors use `utils.http` + `insert_raw_signal_dedup`.

## X and Grok

X/Twitter is **not** scraped via REST from this host. **Grok 4.3** (Hermes agent) runs native X search; Python collectors only persist structured JSON.

### Flow

```
Hermes/Grok agent
  ├─ Per-company: x_monitor.get_x_query_prompt("@handle", days=2)
  ├─ Discovery: sources_registry.X_MONITOR_QUERIES (8 templates)
  └─ Returns JSON post arrays
        │
        ├─ x_monitor.process_grok_x_results(company, posts)
        │     ├─ db/ingest.insert_x_post → x_posts (tracked companies only)
        │     └─ x_signal_collector.store_x_signal → raw_signals (dedup)
        │
        ├─ x_monitor.process_grok_query_results(query, posts)
        │     └─ x_signal_collector.store_grok_batch
        │
        └─ Batch file (optional): GROK_X_RESULTS_PATH → x_signal_collector.run()
              └─ signal_processor_v2 → intelligence_events
```

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GROK_X_RESULTS_PATH` | No | Path to JSON batch file for unattended ingest via `x_signal_collector.run()`. Format: `[{"query": "...", "results": [{...}]}]` or `{"batches": [...]}`. |

No API keys for X are stored in this repo — Grok access is external to the collector process.

### Grok post JSON schema

Each post object should include:

| Field | Type | Notes |
|-------|------|-------|
| `post_id` | string | Preferred dedup key → `signal_type` = `x_post:{id}` |
| `text` | string | Full post body |
| `url` | string | Canonical X URL |
| `posted_at` | ISO datetime | Optional |
| `likes`, `retweets`, `replies` | number | Engagement |
| `is_founder_post` | bool | Optional |
| `sentiment` | float | -1..1, optional |
| `companies` / `companies_detected` | list | Grok hints; merged with DB extraction |

### Company linking (`x_signal_collector`)

On ingest, `companies_detected` is built from:

1. Grok-provided company names
2. `@mention` → `companies.x_handle` lookup (author included)
3. Substring match against all `companies.name` / slug / handle via `rss_collector.extract_company_mentions`

`company_id` is set when an explicit company is passed (per-handle ingest) or the first resolved name matches the DB. Category is inferred (`funding`, `product_launch`, `hiring`, `acquisition`, `social_momentum`) unless Grok sets `category`.

### Dedup and payload

- `source` = `x`
- `signal_type` = `x_post:{post_id}` or URL hash (`url_dedup_key`)
- `data_json` includes: `query`, `text`, `author`, engagement counts, `mentions`, `urls`, `companies_detected`, `grok_companies`, `category`, `kind`, `channel` (`grok_x_search`)

### Modules

1. `collectors/x_monitor.py` — prompts, `process_grok_x_results()`, `process_grok_query_results()`
2. `collectors/x_signal_collector.py` — `store_x_signal()`, `store_grok_batch()`, `run()` / `GROK_X_RESULTS_PATH`
3. `collectors/sources_registry.py` — `X_MONITOR_QUERIES` templates for parallel discovery
