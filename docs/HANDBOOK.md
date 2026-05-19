# Competitor Intelligence — Technical Handbook

**For AI agents taking over this project.** Read this entire document before making any changes.

## 1. Project Overview

This is a private company intelligence platform that automatically discovers, monitors, scores, and alerts on AI startups and tech companies. It ingests data from 99 RSS feeds, 60 X/Twitter queries, and 8 direct collectors, processes signals into structured intelligence events, scores companies on a 12-factor VC model, detects trending momentum, maps competitor relationships, and exposes everything via a REST API and Svelte dashboard.

**Runtime**: Python 3.14 for collectors/pipeline, Bun for API/dashboard
**Database**: SQLite at `data/competitor_intel.db` (override with `CI_DB_PATH`)
**Location**: `~/Documents/Competitor-Intel/` (monorepo). Hermes calls via `integrations/hermes/call_intel.sh` only.

## 2. Two Architecture Versions

The project has **two parallel architectures**. This is critical to understand.

### Version A: Operational monorepo packages (DAILY)
- Collectors: `packages/py-collectors/collectors/`
- SQLite + ingest: `packages/py-core/db/` (`get_conn`, `insert_raw_signal_dedup`)
- Worker orchestration: `apps/worker/automation/` (`collector_registry.py`, `daily_intel.py`)
- **This is what runs daily.**

### Version B: Enterprise `packages/py-enterprise/` (NOT WIRED)
- Python package with `core/`, `db/`, `collectors/`, `reports/` subpackages
- SQLAlchemy 2.0 ORM with 28 models
- Alembic migrations
- Pydantic settings
- **Not wired to daily pipeline.** Exists as enterprise architecture foundation.

**Rule**: Add new pipeline code under `packages/py-collectors/` and `packages/py-core/`. Enterprise SQLAlchemy (`packages/py-enterprise/`) stays optional until wired.

## 3. Database Schema (30 Tables)

### Core Tables
| Table | Rows | Purpose |
|-------|------|---------|
| `companies` | 86 | Tracked companies (name, slug, website, x_handle, github_org, industry, status, score) |
| `company_details` | 4 | Enriched data (founded_year, headquarters, team_size, business_model, tech_stack, description_long, traction, moat) |
| `raw_signals` | 1,139 | Unprocessed signals (company_id, source, signal_type, data_json, detected_at, processed) |
| `intelligence_events` | 227 | Processed events (company_id, event_type, amount_usd, valuation_usd, lead_investor, counterparty, is_rumor, confidence, source, source_url, description, created_at) |

### Funding & Team
| Table | Rows | Purpose |
|-------|------|---------|
| `funding_rounds` | 3 | Funding events (company_id, round_type, amount_usd, valuation_usd, lead_investor, announced_date) |
| `team_members` | 0 | Team data (company_id, name, role, linkedin, twitter, joined_date) — EMPTY, needs collection |
| `products` | 0 | Product catalog — EMPTY |

### GitHub & Tech
| Table | Rows | Purpose |
|-------|------|---------|
| `github_metrics` | 5 | Latest metrics (company_id, repo_name, total_commits, commits_last_30d, contributor_count, active_contributors_30d, primary_language, languages_json, release_count, last_release_date, issue_resolution_days, star_growth_30d, fork_growth_30d) |
| `github_history` | 187 | Historical GitHub snapshots |
| `technology_stack` | 559 | Detected technologies (company_id, category, technology, confidence) |

### Monitoring
| Table | Rows | Purpose |
|-------|------|---------|
| `website_snapshots` | 41 | Website change detection (company_id, url, content_hash, snapshot_data, detected_change) |
| `job_postings` | 0 | Job listings — EMPTY, collector exists but no data yet |
| `x_posts` | 7 | X/Twitter posts |

### Intelligence
| Table | Rows | Purpose |
|-------|------|---------|
| `competitor_relationships` | 4 | Auto-detected relationships (company_id, competitor_id, relationship_type, overlap_areas, confidence) |
| `investors` | 5 | Investor profiles |
| `alerts_sent` | 0 | Alert dedup tracking (event_id, channel, sent_at) |
| `alert_rules` | 0 | Alert rule definitions — CREATED this session |

### Legacy/Unused (from public company tracking)
`public_companies`, `sec_filings`, `financial_metrics`, `stock_prices`, `funding_events`, `product_updates`, `github_activity`, `rss_items`, `reports`, `founders`, `timeline_events`, `company_candidates`, `funding_events_investors`, `competitive_positioning`, `customer_signals`, `ip_assets`

## 4. Data Flow

```
RSS/X/GitHub/PH/HN/CB/AL ──► raw_signals (unprocessed)
                                    │
                           signal_processor.py
                                    │
                           intelligence_events (processed)
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              alert_engine.py  scoring engine   competitor_mapper
                    │               │               │
              Discord webhook  companies.score  competitor_relationships
```

### Scheduling (frequent vs Grok vs daily)

See **[SCHEDULING.md](SCHEDULING.md)** for cron examples (hourly RSS, 5×/day Eastern Grok, once-daily full sweep).

| Command | Role |
|---------|------|
| `make frequent` | RSS / HN / open web + `signal_processor` (no X quota) |
| `make grok-refresh` | Hermes `x_search` + X ingest + reprocess |
| `make daily-tiered` | Full daily with `CI_SKIP_GROK_X=1` after Grok cron |

### Daily Pipeline (`automation/daily_intel.py`)
Runs in order:
1. `run_intel.py` — Base intel collection
2. `funding_collector.py` — Funding events
3. `big_deals_collector.py` — Major deal tracking
4. `youtube_collector.py` — YouTube monitoring
5. `investor_collector.py` — Investor tracking
6. `producthunt_collector.py` — Product Hunt launches
7. `hackernews_collector.py` — HN stories
8. `crunchbase_collector.py` — Crunchbase data
9. `angellist_collector.py` — AngelList data
10. `website_monitor.py` — Website changes
11. `job_tracker.py` — Job postings
12. `tech_stack_detector.py` — Tech fingerprinting
13. `signal_processor.py` — Signal processing
14. `competitor_mapper.py` — Relationship detection
15. `momentum_detector.py` — Trending analysis
16. `enrichment_runner.py` — Company enrichment
17. `embedding_generator.py` — Embedding generation
18. `alert_engine.py` — Alert dispatch
19. `daily_brief.py --export` — Report generation
20. `tweet_generator.py` — Social content

**To add a new collector**: Create the file under `packages/py-collectors/collectors/`, add a `run()` function, and register it in `apps/worker/automation/collector_registry.py`.

### Ingestion conventions (collectors)

- HTTP: `utils/http.py` — `fetch_text`, `safe_request`, shared `httpx` client (not `requests`).
- Dedup ingest: `db/ingest.insert_raw_signal_dedup(cursor, source, url, data_json, ...)`.
- `signal_type` column stores dedup key (URL hash or scoped key like `x_post:{id}`).
- Human categories live in `data_json`: `kind`, `category`, `channel`.

### Feed registry (`packages/py-collectors/collectors/sources_registry.py`)

Single source of truth for RSS/Atom URLs. Each `FeedSource` has `name`, `url`, `category`, `trust_tier`, `enabled`, optional `disabled_reason`.

- **54 enabled** feeds (verified XML/RSS as of May 2026): tech/startup press, AI labs, **VC** (a16z Substack, Sequoia `/feed/`, Benchmark/Medium, Kleiner, Founders Fund, Lightspeed, Menlo, Battery, Insight, Redpoint, Craft, USV, YC), community (HN), Product Hunt, newsletters, EU regulatory, SEC Atom.
- **14 disabled** with reasons: legacy a16z.com / Sequoia `/blog/rss/` / benchmark.com URLs, Greylock/First Round/Bessemer (no public RSS), Anthropic news RSS, The Batch, TechCrunch FeedBurner fundings, Protocol (defunct), The Information (403), PitchBook (403), Axios Tech (404).

**Tech press & startup news (enabled `news` / `funding`):**

| Feed | URL |
|------|-----|
| TechCrunch (+ AI, Startups, Venture) | `techcrunch.com/.../feed/` |
| VentureBeat (+ AI) | `venturebeat.com/feed/` |
| Ars Technica | `feeds.arstechnica.com/arstechnica/index` |
| Wired | `wired.com/feed/rss` |
| Wired Business | `wired.com/feed/category/business/latest/rss` |
| The Verge | `theverge.com/rss/index.xml` |
| MIT Technology Review | `technologyreview.com/feed/` |
| Bloomberg Technology | `feeds.bloomberg.com/technology/news.rss` |
| Fast Company | `fastcompany.com/latest/rss` |
| ZDNet / CNET | `zdnet.com`, `cnet.com` RSS |
| GeekWire / SiliconANGLE / Techmeme | regional & aggregator |
| Business Insider / CNBC Tech | broad business tech |
| Sifted / Tech.eu / EU Startups / BetaKit | EU & regional startups |
| Crunchbase News / TechFundingNews | `funding` category |

**VC firm blogs (`vc` category, `trust_tier` 1 = top-tier signal):**

| Feed | URL | Tier |
|------|-----|------|
| a16z | `a16z.substack.com/feed` | 1 |
| Sequoia Capital | `sequoiacap.com/feed/` | 1 |
| Benchmark | `medium.com/feed/benchmark` | 1 |
| Kleiner Perkins | `kleinerperkins.com/feed/` | 1 |
| Founders Fund | `foundersfund.com/feed/` | 1 |
| Lightspeed | `lsvp.com/feed/` | 1 |
| Y Combinator Blog | `ycombinator.com/blog/rss` | 1 |
| Menlo Ventures | `menlovc.com/feed/` | 2 |
| Battery Ventures | `battery.com/feed/` | 2 |
| Insight Partners | `insightpartners.com/feed/` | 2 |
| Redpoint / Craft (Medium) | `medium.com/feed/redpoint-ventures`, `craft-ventures` | 2 |
| Union Square Ventures | `usv.com/feed/` | 2 |

No working public RSS found (kept disabled): Greylock, First Round Review, Bessemer (BVP), Index Ventures, Accel.

`rss_collector` and `multi_source_collector` import enabled feeds from the registry. To add a feed: verify HTTP 200 + RSS body, add to `FEED_CATALOG`, set `enabled=True`.

### X / Grok pipeline

1. Hermes/Grok runs X search using prompts from `x_monitor.get_x_query_prompt()` or registry `X_MONITOR_QUERIES`.
2. Persist with `x_monitor.process_grok_x_results(company, json_posts)` or `x_signal_collector.store_grok_batch(query, posts)`.
3. Optional batch file: set `GROK_X_RESULTS_PATH` to JSON `[{"query": "...", "results": [...]}]` before `x_signal_collector.run()`.

Migrated collectors (http + dedup): hackernews (Firebase + Algolia Show HN), producthunt, crunchbase, angellist, edgar (optional `EDGAR_TRACKED_CIKS` + Form D quarterly ZIP — all primary issuers, no sector filter), ycombinator (public directory JSON, all companies stored), esma_mica (MiCA CASP CSV), techcrunch_edgar, x_signal_collector.

RSS/HN ingest is **discovery-first**: high-signal items and headline entity extraction are stored even when no company row exists yet. Names flow into `company_candidates` after `signal_processor`.

### Discovery → promote → rank (daily, after `signal_processor`)

1. **`candidate_discovery.py`** — Scans recent `raw_signals`, harvests plausible company names (payload fields + headline patterns), scores **attention** (volume, source diversity, hype language), upserts `company_candidates`.
2. **`auto_promote.py`** — Promotes candidates with score ≥ 0.65 into `companies` (sector-agnostic).
3. **`company_ranker.py`** — Updates `companies.score` from 30-day signal volume, velocity, source diversity, events, and hype. Dashboard top-N uses `ORDER BY score DESC`.

No fixed “big private” watchlist is required for the firehose; optional CIKs only via `EDGAR_TRACKED_CIKS`.

## 5. Signal Processor (`packages/py-collectors/collectors/signal_processor.py`)

Converts raw signals into structured intelligence events.

### Event Types
- `funding` — Funding rounds, investments
- `product_launch` — New products, features
- `partnership` — Collaborations, integrations
- `acquisition` — Acquisitions, mergers
- `hiring` — Executive hires, team expansion
- `research` — Papers, model releases
- `general` — Everything else

### Key Functions
- `classify_event(text, source)` — Classifies signal text into event type with confidence score
- `extract_amount(text)` — Extracts dollar amounts from text ($50M, $1.2 billion)
- `fuzzy_match_company(name, cursor)` — Matches company names using aliases + substring + Levenshtein distance (threshold 0.6)
- `is_duplicate(cursor, event_type, company_id, text)` — Deduplication within 7-day window
- `process_signals(batch_size)` — Main entry point, processes unprocessed signals

### Company Alias System
Loads company names, slugs, and X handles into a lookup table. Supports token-level matching for multi-word names.

## 6. Scoring

### 6a. Attention rank (`packages/py-collectors/collectors/company_ranker.py`)

**Primary ranking for “who’s hot”** — sector-agnostic, driven by the signal firehose. Run automatically in `DAILY_SEQUENTIAL` after discovery/promote. Composite 0–1 written to `companies.score` and `last_scored_at`.

### 6b. VC deep score (`packages/py-collectors/collectors/company_discovery.py`)

Optional 12-factor model for dossier-style analysis. All factors computed from real database data. Zero placeholders.

Each factor produces a 0-1 score, multiplied by its weight, summed for composite score.

### Factor Computation Details

1. **Funding Round Quality** (8%): Maps series stage to score (Series E=1.0, Series D=0.95, Series C=0.9, Series B=0.75, Series A=0.6, Seed=0.45, Pre-seed=0.35)

2. **Investor Tier** (7%): Checks lead_investor against tier lists (Tier 1: a16z, Sequoia, Benchmark, Accel, Founders Fund; Tier 2: Lightspeed, Kleiner, Greylock, Index, Bessemer, First Round, YC; Tier 3: Tiger Global, Coatue, Dragoneer)

3. **Capital Raised/Runway** (6%): Total raised amount (normalized to $500M) weighted 60% + recency score (decay over 24 months) weighted 40%

4. **Capital Efficiency** (9%): GitHub stars per contributor ratio, normalized to 500

5. **Product Traction** (12%): Signal count (50%), event count (30%), website snapshot count (20%)

6. **Revenue Monetization** (5%): Detects pricing/SaaS keywords in raw signals. Pricing detected = 0.6+, revenue signals = 0.3+

7. **Technical Depth** (13%): GitHub commits (60%) + technology stack diversity (40%)

8. **Founder Team Quality** (14%): Team member count + role detection (founder/CEO/CTO = 0.5+, exec roles = bonus, 3+ members = 0.9)

9. **Talent Hiring Velocity** (7%): Active job postings (60%) + 90-day new hires (40%)

10. **Market Timing/TAM** (9%): Industry TAM lookup (AI=0.95, AI Agents=0.85, etc.) + signal velocity bonus

11. **Competitive Moat** (8%): Technology stack depth + competitor relationships + GitHub stars

12. **Momentum/Risk** (12%): 7-day signal velocity (60%) + 7-day event velocity (40%)

### Running Scoring
```python
uv run python packages/py-collectors/collectors/company_discovery.py
```

## 7. Momentum Detector (`packages/py-collectors/collectors/momentum_detector.py`)

Real-time trending analysis. Compares current period vs previous period for growth rate.

### Thresholds
- **Breakout**: 0.55+ — Explosive growth
- **Trending**: 0.35+ — Above average
- **Rising**: 0.20+ — Emerging signals

### Velocity Dimensions
- Funding velocity: Round count + total amount in window
- Signal velocity: Growth rate of raw signals (current vs previous period)
- Hiring velocity: Active jobs + recent hires
- GitHub velocity: Commits + contributors + star growth
- Media velocity: Intelligence event growth rate
- Competitor mentions: Relationship count + co-mention signals

## 8. Competitor Mapper (`packages/py-collectors/collectors/competitor_mapper.py`)

Auto-detects competitor relationships by analyzing co-mentions in raw signals.

### Process
1. Scans raw signals within window (default 30 days)
2. Extracts all company names mentioned in each signal
3. Counts co-mention pairs
4. Computes overlap areas using industry keyword matching
5. Inserts bidirectional relationships with confidence scores

### Relationship Types
- `direct_competitor` — 2+ overlap areas
- `indirect_competitor` — 1 overlap area
- `competitor` — co-mentions only

## 9. Alert Engine (`alerts/alert_engine.py`)

Discord webhook dispatcher with deduplication.

### Alert Rules
- `funding` — Keywords: raised, funding, series, seed, investment. Min amount: $1M
- `acquisition` — Keywords: acquired, acquisition, buys, purchased, merger
- `launch` — Keywords: launch, announced, released, introducing, unveiled
- `hiring_spree` — Keywords: hires, hiring, expanding team, headcount. Min mentions: 3

### Direct Event Type Mapping
Also maps intelligence event types directly: funding→funding, funding_round→funding, acquisition→acquisition, product_launch→launch, hiring→hiring_spree

### Deduplication
Tracks sent alerts in `alerts_sent` table. Only sends each event once per channel.

## 10. API Architecture (`api/src/`)

### Stack
- **Framework**: Hono 4.6
- **Runtime**: Bun
- **Database**: bun:sqlite (native, not better-sqlite3)
- **Validation**: @hono/zod-validator + Zod
- **Security**: hono/secure-headers (HSTS, X-Frame-Options, CSP, etc.)
- **Logging**: hono/logger
- **Timing**: hono/timing

### Middleware Stack (applied to all routes)
1. CORS
2. Logger
3. Secure Headers
4. Timing

### Error Handling
- `onError` → 500 JSON response
- `notFound` → 404 JSON response

### Validation
All query parameters validated with Zod schemas in `schemas.ts`:
- `companyQuery` — limit (1-200, default 50), offset (0+)
- `signalQuery` — limit, offset, source (optional), processed (true/false)
- `eventQuery` — limit, offset, type (optional)
- `searchQuery` — q (required, 1-200 chars), limit (1-100, default 20)

### Database Connection (`api/src/db.ts`)
```typescript
import { Database } from "bun:sqlite";
// Opens DB as readonly, WAL mode, foreign keys ON
// Singleton pattern — lazy initialization
```

## 11. Dashboard Architecture (`dashboard/src/`)

### Stack
- **Framework**: SvelteKit (Svelte 5 runes mode)
- **Styling**: Tailwind CSS
- **Icons**: lucide-svelte
- **Runtime**: Bun
- **Color Palette**: Slate (neutral) + Amber (accent)

### Svelte 5 Patterns Used
- `$state()` for reactive state (not `let x = value`)
- `$derived()` for computed values
- `$props()` for component props
- `onclick` (not `on:click`)
- `<svelte:component this={Icon}>` for dynamic components

### Pages
| Route | Purpose |
|-------|---------|
| `/` | Dashboard overview with stat cards, top sources, recent events |
| `/companies` | Company list table |
| `/companies/[id]` | Company detail with tabs (overview, funding, team, signals) |
| `/signals` | Raw signal feed |
| `/events` | Intelligence event timeline |
| `/funding` | Funding event tracker |
| `/search` | Search interface |
| `/settings` | Settings page |

### Components
- `StatCard.svelte` — Reusable stat card with icon
- `SearchBar.svelte` — Search input component
- `DarkModeToggle.svelte` — Theme toggle

### API Client (`dashboard/src/lib/api.ts`)
Wraps fetch calls to all API endpoints. Uses relative URLs (proxied through SvelteKit).

## 12. Sources Configuration (`sources.py`)

### Adding RSS Feeds
Add to the appropriate category dict, then it's automatically included in `ALL_SOURCES`:
```python
TECH_NEWS = {
    "New Source Name": "https://example.com/feed.xml",
}
```

### Adding X Queries
Append to `X_MONITORING_QUERIES` list:
```python
X_MONITORING_QUERIES = [
    # ... existing queries
    "new query here",
]
```

### Priority Sources
`COMPETITOR_INTEL_SOURCES` is a curated subset used for focused intel collection.

## 13. Embedding System

### Model
- **Preferred**: qwen3-embedding:4b (2.5GB, better quality) — fails to load due to resource limits
- **Fallback**: nomic-embed-text (works reliably via Ollama HTTP API)

### Usage
- Ollama HTTP API at `http://localhost:11434/api/embeddings`
- Embeddings stored in various tables as BLOB columns
- Used for semantic search and signal deduplication

### Generating Embeddings
```python
from collectors.enrichment.embedding_generator import run
run()
```

## 14. Known Issues & Technical Debt

### Critical
- `team_members` table empty — no founder/team data collected
- `job_postings` table empty — job tracker exists but not producing data
- `products` table empty — no product catalog data
- `src/competitor_intel/` architecture not wired — duplicate effort maintaining two versions

### Moderate
- No API rate limiting
- No API authentication
- Alert engine only supports Discord
- No frontend pages for competitors, scoring breakdown, or momentum
- Revenue signals table exists but unused
- No automated tests for collectors

### Minor
- Some legacy tables from public company tracking still exist (unused)
- Dashboard has no loading states for API errors
- No pagination in dashboard UI (API supports it)

## 15. Commands Reference

### Python Collectors
```bash
cd ~/Documents/Competitor-Intel
uv sync

# Run individual collector
uv run python packages/py-collectors/collectors/rss_collector.py
uv run python packages/py-collectors/collectors/signal_processor.py
uv run python packages/py-collectors/collectors/candidate_discovery.py
uv run python packages/py-collectors/collectors/company_ranker.py

# Run full daily pipeline
uv run python apps/worker/daily_intel.py
make daily

# Alerts
uv run python packages/py-core/alerts/alert_engine.py

# CLI
uv run python apps/cli/intel.py
```

### API
```bash
cd apps/api
bun install
bun run dev                   # Port from package.json
bun run build
```

### Dashboard
```bash
cd apps/dashboard
bun install
bun run dev
bun run build                 # Production build
```

### Database
```bash
# Direct SQLite access
sqlite3 competitor_intel.db

# Check table counts
python -c "
import sqlite3
conn = sqlite3.connect('competitor_intel.db')
c = conn.cursor()
for t in c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall():
    count = c.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
    print(f'{t[0]}: {count}')
conn.close()
"
```

## 16. Ollama Models Available

| Model | Purpose | Status |
|-------|---------|--------|
| qwen2.5:7b | Text generation/analysis | Working |
| qwen3.5:9b | Text generation/analysis | Working |
| nomic-embed-text | Embeddings | Working |
| qwen3-embedding:4b | Embeddings (preferred) | Fails to load (resource limits) |

## 17. Constraints (Do Not Violate)

1. **No paid APIs** — all data from free sources only
2. **SQLite only** — no Docker, no PostgreSQL (yet)
3. **Local-first** — runs on single host
4. **Hermes schedule system** — use built-in cron for automation
5. **No docstrings** — code must be self-documenting
6. **No AI slop** — production-grade code only, no placeholders, no TODOs in committed code
