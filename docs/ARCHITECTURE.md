# Competitor Intel — architecture

Canonical repo: `~/Documents/Competitor-Intel/`. Implementation plan: [ROADMAP.md](ROADMAP.md). Operations: [HANDBOOK.md](HANDBOOK.md).

## Monorepo layout

```
Competitor-Intel/
├── apps/
│   ├── worker/              # daily_intel.py, frequent_intel.py, reports
│   └── cli/                 # intel.py, run_intel.py
├── packages/
│   ├── py-core/             # db, utils, alerts, ci_paths
│   └── py-collectors/       # collectors/ (operational ingest)
├── integrations/hermes/     # call_intel.sh — only Hermes entry
├── scripts/                 # enrich export/apply, golden eval, Grok helpers
├── infra/scripts/           # dedupe, migrations
├── docs/                    # see docs/README.md
├── data/                    # competitor_intel.db (gitignored)
└── tests/
```

### Toolchain

| Stack | Tool |
|-------|------|
| Python | `uv sync` — workspace: py-core, py-collectors |

```bash
uv run python apps/worker/daily_intel.py
uv run python apps/cli/run_intel.py
make cli ARGS="status"
```

Path resolution: `packages/py-core/ci_paths.py` (`CI_DB_PATH` overrides DB file).

### Root symlinks (legacy subprocess paths)

```
collectors   → packages/py-collectors/collectors
automation   → apps/worker/automation
intel.py     → apps/cli/intel.py
run_intel.py → apps/cli/run_intel.py
```

Remove symlinks when `collector_registry.py` uses only monorepo-native paths (ROADMAP X-13).

**Canonical daily entry:** `apps/worker/daily_intel.py` only. Do **not** use `apps/worker/automation/daily_intel.py` (removed — was a stale duplicate).

## Data flow

```
Sources (RSS, GitHub, SEC, X via Grok, jobs, …)
  → raw_signals (dedup via insert_raw_signal_dedup)
  → signal_processor → intelligence_events
  → rollups (funding_rounds, job_postings, profile claims)
  → CLI brief export (`apps/worker/daily_brief.py`, `apps/cli/intel.py`)
```

Layer rules and defect backlog: [PIPELINE.md](PIPELINE.md), [ROADMAP.md](ROADMAP.md).

`signal_type` is usually a URL hash. Categories live in `data_json` (`kind`, `category`, `channel_company`).

## Parallel collection

Independent collectors: `apps/worker/automation/parallel_collect.py` (thread pool). Processor, rollups, and enrichment stay sequential after ingest.

## HTTP layer

Shared sync `httpx.Client`: `packages/py-core/utils/http.py`. RSS, multi-source, and GitHub collectors use this pool.

## Ingest API

Prefer `db/ingest.insert_raw_signal_dedup()` for all new signals. Use `dedup_key=` for scoped keys (e.g. RSS per-company rows).

## Feed catalog

Canonical list: `packages/py-collectors/collectors/sources_registry.py` (`FeedSource`: `enabled`, `trust_tier`, `category`).

Collectors wired to registry: `rss_collector.py`, `multi_source_collector.py`. Others use `utils.http` + dedup ingest.

## Stack choices (summary)

Full rationale: [ROADMAP.md § Stack decisions](ROADMAP.md#stack-decisions-r01--opinionated).

| Layer | Choice | Notes |
|-------|--------|-------|
| Read API | Bun + Hono + `bun:sqlite` | Read-only in prod until P0-1 |
| Collectors | Python httpx / feedparser | ~74 modules; I/O-bound |
| Dashboard | SvelteKit 2 + Svelte 5 | Expand TanStack Query |
| Embeddings | Ollama `nomic-embed-text` | Fix zero-vector on failure (Track 0) |
| Search (target) | FTS5 + sqlite-vec in API | Remove Python subprocess (Track 2) |
| Database | SQLite WAL | Single-file production store ([SQLITE.md](SQLITE.md)) |

**Defer:** Rust collectors, FastAPI rewrite, React/Next.js, merging enterprise stack into daily.

## Hermes & X

X is **not** scraped via REST here. Grok (Hermes) runs native X search; Python persists JSON only.

- Operator commands: [integrations/hermes/README.md](../integrations/hermes/README.md)
- Technical model: [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md)

## Related

- [docs/README.md](README.md) — documentation index
- [PIPELINE.md](PIPELINE.md) — layers and commands
- [ROADMAP.md](ROADMAP.md) — build plan
