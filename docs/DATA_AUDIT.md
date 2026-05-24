# Data quality audit

This document is the human-readable companion to **`GET /api/data-audit`** and the dashboard **`/data-quality`** page. It maps every domain we store → what collects it → where the UI shows it → how much to trust it.

Counts are **live from SQLite** at request time (default: `data/competitor_intel.db`). Re-run after pipeline jobs.

## Trust tiers

| Tier | Meaning |
|------|---------|
| **Verified** | Official filings or primary-source confirmation with high corroboration. |
| **Corroborated** | Multi-source merge; check `corroboration_score` and `official_report_count` before trusting dollar amounts. |
| **Operational** | Raw ingest + classification; good for **monitoring**, not ground truth. |
| **Partial** | Collector runs but low company coverage or sparse fields. |
| **Empty** | Schema exists; no pipeline writing rows. |
| **Inferred** | Derived from jobs, GitHub, heuristics; confidence varies. |

## Trust model (private companies)

Public-company logic (SEC filings as ground truth) does not apply to most of this watchlist. Evidence is **announcements, press, careers pages, GitHub, RSS**, and similar — the same kinds of signals operators actually use.

Trust is **confidence on a 0–1 scale**, not a binary verified flag:

- More **independent outlets** reporting the same fact → confidence rises.
- **Company-owned sources** (press release, careers site) add weight but are not the only path.
- **Field agreement** across claims (e.g. amount) nudges the score up or down.

Funding implements this as `funding_rounds.corroboration_score` (see `docs/CONFIDENCE_SCORING.md` for weights and anti-gaming rules). After aggregation, scores flow into linked `intelligence_events.confidence`.

## Display policy (UI)

1. **One list per domain** — no parallel “verified” vs “unverified” sections.
2. **Show the value** (amount, headline, role title) with a **confidence tag** on the row: `Early signal` → `Building` → `Strong` (or the numeric % in badges).
3. As new claims arrive and scores recompute, tags **move up in place** — that is the product story for “noise becomes truth.”
4. **Do not invent fields** with no collector (leadership, products) — empty is honest; confidence does not apply to data we never ingested.

## Domains (canonical registry)

Source of truth for definitions: `apps/api/src/dataAuditRegistry.ts`.

| Domain | Table | Tier | Collector | Dashboard surfaces |
|--------|-------|------|-----------|-------------------|
| Company registry | `companies` | Operational | Seed / manual + discovery | Companies list, header, search |
| Company enrichment | `company_details` | Partial | `company_enricher.py` | Company overview (sparse) |
| Leadership & officers | `team_members` | **Empty** | *none* | Team tab, scoring — **do not infer from jobs** |
| Funding rounds | `funding_rounds` | Corroborated | funding_rollup + signal_processor | Funding, company Funding, KPIs |
| Funding claims | `funding_round_claims` | Operational | funding_collector, RSS/press | Claims layer |
| Investor firms | `investor_firms` | Corroborated | `investor_collector.py` | Funding → investors |
| Job postings | `job_postings` | Operational | `job_tracker.py` | Jobs, company Jobs — **ATS demand, not org chart** |
| Raw signals | `raw_signals` | Operational | RSS, X, GitHub, … | Signals feed |
| Intelligence events | `intelligence_events` | Operational | `signal_processor.py` | Events — **classifier labels, not legal facts** |
| GitHub metrics | `github_metrics` | Partial | `github_collector.py` | Company GitHub panel |
| Technology stack | `technology_stack` | Inferred | `tech_stack_detector.py` | Company Tech tab |
| Competitor graph | `competitor_relationships` | Inferred | `competitor_mapper.py` | Competitive set (low coverage) |
| Products | `products` | **Empty** | *none* | Summary count only |
| X posts archive | `x_posts` | Partial | `x_signal_collector.py` | Mostly superseded by `raw_signals` |
| Website snapshots | `website_snapshots` | Partial | `website_monitor.py` | Internal / alerts (not on dossier yet) |

## Dashboard surfaces (what mixes trust levels)

| Surface | Path | Risk |
|---------|------|------|
| Dashboard home | `/` | Aggregate KPIs — funding totals must use **verified** raised only. |
| Company dossier | `/companies/:slug` | **Highest risk** — many tiers on one page; disclaimers required. |
| Signals | `/signals` | Always show source + time; never imply verification. |
| Events | `/events` | `event_type` is NLP output. |
| Funding | `/funding` | Corroboration badges mandatory. |
| Jobs | `/jobs` | ATS listings only. |
| Data quality | `/data-quality` | This audit (live). |

## Known gaps (as of audit build)

1. **`team_members` has zero rows** — no SEC/state officer collector wired; leadership UI must say “not collected.”
2. **`company_details` and `github_metrics`** — very low company coverage; do not treat absence as “no HQ” or “no GitHub activity.”
3. **Most `funding_rounds`** — corroboration below 0.45; show unverified totals separately.
4. **Jobs** — template titles filtered in API; still not leadership data.
5. **`products`** — unused table.

## How to refresh

```bash
# API (from repo root)
CI_DB_PATH=data/competitor_intel.db PORT=3000 bun run --cwd apps/api dev

# Audit JSON
curl -s http://127.0.0.1:3000/api/data-audit | jq '.highlights, .domains[] | {id, rowCount, coveragePct, tier}'

# Dashboard
PUBLIC_CI_API_URL=http://127.0.0.1:3000 bun run --cwd apps/dashboard dev
# → http://localhost:5173/data-quality
```

## Next engineering steps

1. Apply trust-tier badges and empty states on **Signals**, **Events**, **Funding list**, **Jobs**, **Search** (company dossier partially done).
2. Wire **leadership collector** → `team_members` with `source` + URL (SEC/state).
3. Gate global KPIs on verified funding only until domain coverage improves.
4. Expand `company_details` enrichment coverage.
