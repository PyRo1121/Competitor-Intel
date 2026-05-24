# Product brief — Competitor Intel

**Status:** Active · **Codename:** Competitor Intel  
**Audience:** You (customer zero) → optional SaaS later  
**Engineering companions:** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) (ordered tasks), [PIPELINE.md](PIPELINE.md) (artery ops), [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) (repo hygiene), [ENGINEERING.md](ENGINEERING.md) (naming / dead code)

---

## Vision

Build a **credible source of private-company intelligence**—funding-first—by combining many ingest lanes (RSS, regulatory, careers, GitHub, X via Hermes, etc.) into a **scored, trust-tiered** SQLite corpus. The **pipeline is the product artery**; the dashboard and Hermes are how you **see and use** the blood; X is a **distribution channel**, not the source of truth.

**Primary growth bet:** Authority and impressions on X (you post; Hermes helps draft). **Secondary bet:** SaaS on proprietary scored data + tools. Hobby-scale success without revenue is acceptable.

**Public line (no X in the pitch):**

> Multi-source private-company reporting, scored and verified—early speculative signals for subscribers, confirmed facts for everyone.

---

## Customer phases

| Phase | Who | Success |
|-------|-----|---------|
| **Now** | You | Daily trust in funding + breaking queue habit |
| **Growth** | Your X audience | Followers/impressions from verified + labeled speculative posts |
| **Later** | Paying users | Full speculative feed, dossiers, Hermes Q&A on your DB |

---

## What you open every day

1. **Dashboard** (main UI when built)—breaking queue, scored companies, funding dossier slice.  
2. **Hermes**—questions against the read API / DB; post drafts from pipeline data (you publish manually).

Cron + `make daily-prod` stay **background**; you do not live in logs.

---

## Hero signal and watchlist

| Choice | Decision |
|--------|----------|
| **Killer signal** | Funding |
| **Worst failure** | False **verified** funding (worse than a miss) |
| **Watchlist model** | Private companies; **score-based promotion**, not a fixed CSV |
| **Focus niches (soft)** | AI, fintech, neobank—boost/filter in UI and score, do not hard-exclude others yet |
| **Research pipeline** | When attention score crosses threshold (tune later), pull deeper data / dossier fields |

**Score v0 (before tuning):** store `companies.score` early; formula can start as recency + funding-signal weight + source diversity; adjust in config after real data. **Thresholds for promote/verify** are policy knobs later—not a reason to delay storing fields.

---

## Trust model (multi-source)

Trust is **not** “whatever X said.” Each report ingested carries **source credibility**; corroboration across paths moves claims through states:

```text
unverified  → never in briefs or public feeds
speculative → allowed for you/paid; clearly labeled
verified    → brief + shareable; eligible for free/public tier
```

Promotion **speculative → verified** uses the scoring system (weights per source type, independent paths, time). **Exact thresholds TBD** when scoring is tuned on production data.

**Product rules:**

- Include **speculative** in product; exclude **unverified**.  
- Every surfaced funding row shows **tier + why** (sources, corroboration).  
- Hermes **reads** the DB; it does not invent verified amounts.

---

## Freemium (business shape)

| Tier | Speculative | Verified |
|------|-------------|----------|
| **Free / public** | **6–10 items per week** (teaser) | **All verified**, timely—no artificial delay |
| **Paid (future you + SaaS)** | Full speculative queue + history | Same as free |

**Rationale:** Verified news is already public elsewhere—hiding it hurts adoption. Paid value = **edge before confirmation** + depth (dashboard, dossiers, Hermes, future vectors on your corpus). No “6-hour delay” gimmick; optional caps only on speculative volume for free users.

Implementation of weekly speculative caps is **P6** (after scoring/policy hooks exist).

---

## Initial dashboard (three screens)

| Screen | Purpose |
|--------|---------|
| **Breaking** | Funding-first queue; speculative + verified badges |
| **Companies** | Scored list; soft filters (AI / fintech / neobank); research tier |
| **Company → Funding** | Dossier slice: claims, rounds, evidence trail |

**Read model:** Live database via read API (not snapshot-only). Hybrid caching allowed later for expensive aggregates.

Hermes: sidecar for Q&A and drafts, same contract as dashboard.

---

## Hermes role

| Job | Artery / read path |
|-----|-------------------|
| Grok/X fetch | `grok_refresh`, `x_signal_collector`, query export |
| Q&A on private companies | Read API tools over SQLite |
| Post drafts | Brief + top events JSON; you post manually |

Hermes stays **outside** core truth; ingest and rollups remain Python worker + collectors.

---

## Architecture direction (not microservices)

**Polyglot modular monorepo**—one git repo, clear packages:

- **Write path:** `apps/worker` + `packages/py-collectors` + `packages/py-core`  
- **Read path (later):** `packages/contracts` + `apps/api` + `apps/dashboard`  
- **Integration:** `integrations/hermes/` (CLI/bash shim only)

**Rules:** one SQLite writer (worker); many readers; collectors do not import dashboard; core does not import collectors.

Defer **service split** until read stack deploys separately from cron box. Do **not** split per collector.

---

## Product phases (vs engineering)

| Phase | Product milestone | Engineering |
|-------|-------------------|-------------|
| **P0** | Trust funding on promoted companies | [PIPELINE.md](PIPELINE.md): `daily-prod`, audit |
| **P1** | Score v0 + niche boost flags | DB fields + simple ranker |
| **P2** | Trust tiers enforced in exports | Policy on claims/rounds |
| **P3** | Initial dashboard (3 screens) | Read API + UI |
| **P4** | Hermes tools on API | Draft + query tools |
| **P5** | Scoring tuning | Thresholds, promote rules |
| **P6** | Free speculative weekly cap | Entitlement logic |
| **P7** | Vectors/RAG (optional) | Search/Hermes accelerant, not ingest SSOT |

**7 green dailies** ([PIPELINE.md](PIPELINE.md)) completes **P0**. Dashboard starts after **P2** primitives exist in data.

---

## SLOs (plain language)

1. **Never mark verified** if it would embarrass you on X.  
2. **Unverified never ships** to brief or public surfaces.  
3. **Funding claims** on research-tier companies pass `claims-audit-strict` on schedule.

---

## Deferred decisions (intentionally)

- Numeric corroboration / promotion thresholds  
- Research-pipeline score cutoff  
- Exact weekly speculative cap mechanics (calendar vs rolling)  
- Prune/retention policy (keep all data for now)

Revisit when **P5** scoring runs on real neobank/fintech/AI corpus.

---

## Doc map

| Doc | Role |
|-----|------|
| **PRODUCT_BRIEF.md** (this file) | Why we build; business + product shape |
| [PIPELINE.md](PIPELINE.md) | Cron, collectors, production checklist |
| [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) | Slice 2a: scripts → modules; deleted script registry |
| [ENGINEERING.md](ENGINEERING.md) | Naming, structure, dead-code rules |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Repo layout |
| [SCHEDULING.md](SCHEDULING.md) | Cron tiers |

Do not resurrect deleted mega-roadmaps (`ROADMAP.md`, legacy `PIPELINE.md` shards, etc.) from git history unless auditing the past.
