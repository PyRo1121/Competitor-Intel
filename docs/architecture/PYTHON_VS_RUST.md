# Python vs Rust for Competitor Intel backend

Decision guide for the API layer, ingestion workers, and storage path. **Verdict at end.**

## Context

| Layer | Today | Notes |
|-------|-------|-------|
| Read API | Bun + Hono + `bun:sqlite` | Fast to ship, TS ecosystem |
| Collectors / workers | Python 3.11+ | feedparser, httpx, BeautifulSoup, Ollama |
| Enterprise path | Python SQLAlchemy | Alembic, Pydantic, not fully wired |
| Database | SQLite (WAL) | Single file; Postgres optional later |

The user is open to Rust later but wants Python working first.

---

## 1. API layer

### Current: Bun + TypeScript (Hono)

**Pros**

- Same language family as Svelte dashboard; shared Zod schemas possible.
- `bun:sqlite` is zero-deps, fast enough for read-heavy dashboards (86 companies, ~2k rows).
- Hot reload and low ceremony for CRUD routes.
- AI codegen quality for TS/Hono is excellent.

**Cons**

- Two runtimes in production (Bun + Python workers) unless API is rewritten.
- No shared types with Python collectors without codegen or OpenAPI.

### Alternative: Python (FastAPI / Starlette)

**Pros**

- One runtime with workers; shared Pydantic models with enterprise package.
- httpx/async patterns match collectors.
- Easier for data team to own end-to-end.

**Cons**

- Slower cold start than Bun for tiny read API (marginal at current scale).
- Dashboard still TS — API contract via OpenAPI anyway.

### Alternative: Rust (Axum + sqlx)

**Pros**

- Smallest static binary, predictable memory, excellent concurrent I/O.
- sqlx compile-time SQL checks; strong fit for read API at scale.

**Cons**

- Rewrite all routes and validation; lose Bun’s built-in SQLite ergonomics.
- Team velocity hit during migration; AI assists Rust well but iteration is slower than Python/TS for CRUD.

**API takeaway:** Keep **Bun/Hono read API** until traffic or ops complexity justifies Rust. Consider **FastAPI** only if consolidating to a single Python runtime becomes a hard requirement.

---

## 2. Ingestion workers (RSS, parallel collect)

### Python (current)

**Pros**

- **Ecosystem:** `feedparser`, `httpx`, `beautifulsoup4`, `tenacity` — battle-tested for RSS/scraping.
- **Velocity:** 33 collector modules; fuzzy matching, enrichment, Ollama embeddings already in Python.
- **Parallelism:** `ThreadPoolExecutor` in `parallel_collect.py` is sufficient for I/O-bound RSS (6 workers).
- **AI codegen:** Highest success rate for one-off collectors and HTML parsing.

**Cons**

- GIL limits CPU-bound parsing (not the bottleneck today).
- Memory per worker higher than Rust (~50–150 MB vs ~10–30 MB per process).

### Rust (hypothetical)

**Pros**

- **tokio** + **reqwest** + **quick-xml** / **atom_syndication** — excellent for 99 parallel RSS fetches.
- One binary for worker + edge ingest; no venv on servers.
- Deterministic resource use for always-on cron.

**Cons**

- Rewriting 33 collectors + enrichment is **months** of work.
- HTML scraping ecosystem smaller; often still call Python or headless browser for hard sites.
- SEC/GitHub rate-limit logic and dedup keys must be re-ported and tested.

**Ingestion takeaway:** **Keep Python workers.** Port individual hot paths (e.g. RSS fan-out) to Rust only after profiling shows Python as bottleneck.

---

## 3. SQLite vs Postgres

| | SQLite | Postgres |
|---|--------|----------|
| **Fit today** | Single writer (daily pipeline), many readers (API) | Overkill for 86 companies |
| **WAL mode** | Handles concurrent API reads + writer | N/A |
| **Migration cost** | Zero | Alembic + connection pooling + hosting |
| **Rust story** | sqlx + SQLite fine for read API | sqlx + Postgres better at multi-tenant scale |

**Recommendation:** Stay on **SQLite** until multiple concurrent writers or >100 GB / multi-tenant isolation is required. Enterprise SQLAlchemy models already support swapping DSN via `CI_DB_PATH` / Postgres URL later.

---

## 4. Binary size, memory, cold start

| Runtime | Typical deploy artifact | RSS idle | Cold start |
|---------|-------------------------|----------|------------|
| Python worker venv | 200–400 MB (deps) | 80–200 MB | 1–3 s |
| Bun API | ~60 MB + node_modules | 40–80 MB | <500 ms |
| Rust API binary | 5–15 MB (stripped) | 10–30 MB | <100 ms |
| Rust worker binary | 8–20 MB | 15–40 MB | <100 ms |

At current scale, **infrastructure cost is negligible**; developer time dominates.

---

## 5. Hiring and AI codegen ergonomics

| | Python | Rust |
|---|--------|------|
| Hiring pool | Large (data, ML, backend) | Smaller; systems-focused |
| Agent/LLM codegen | Excellent for collectors, SQL, glue | Good for Axum/sqlx; weaker on messy HTML scrapers |
| Onboarding | README + PYTHONPATH | Cargo workspace + stricter compiler |
| Refactor safety | Runtime tests + mypy | Compiler + sqlx + clippy |

For a solo/small team with heavy AI-assisted development, **Python collectors + TS/Bun API** maximizes throughput.

---

## 6. Migration cost (Hermes → monorepo → Rust)

| Phase | Effort | Risk |
|-------|--------|------|
| Monorepo (done) | Low | Import paths, CI_DB_PATH |
| Package namespaces | Medium | Breaking relative imports |
| FastAPI replaces Bun | Medium | Dashboard CORS, parity tests |
| Rust read API | High | Feature parity, ops |
| Rust collectors | Very high | 33 modules, enrichment, Ollama |

---

## 7. Phased recommendation (explicit verdict)

### Phase 1 — Now (months 0–6)

- **Python** workers + collectors in `packages/py-collectors` / `apps/worker`.
- **Bun/Hono** read API in `apps/api`.
- **SQLite** at `data/competitor_intel.db`.
- Hermes integrates via **HTTP or CLI** only.

### Phase 2 — Scale triggers (optional)

- Extract **OpenAPI** contract; add contract tests.
- Consolidate DB path helpers; finish **py-enterprise** wiring for one collector at a time.
- If API p99 > 200 ms or multi-region: evaluate **Rust read replica** (Axum + sqlx, read-only SQLite or Postgres replica).

### Phase 3 — Rust where proven (optional)

- Rewrite **RSS fan-out** or **dedup ingest** as a Rust sidecar called from Python via subprocess/HTTP.
- Full Rust rewrite only if operational cost or reliability demands it.

### Verdict (one line)

**Ship and operate on Python workers + Bun read API + SQLite now; introduce Rust only for proven I/O-hot paths or a read API rewrite when scale or ops cost justify the migration tax—not before.**

---

## Reference stacks (if rewriting)

| Concern | Python | Rust |
|---------|--------|------|
| Async HTTP | httpx, asyncio | reqwest, tokio |
| RSS/Atom | feedparser | atom_syndication, quick-xml |
| SQLite ORM | SQLAlchemy 2 | sqlx, diesel |
| HTTP API | FastAPI, Hono (TS) | axum, actix-web |
| Config | pydantic-settings | figment, envy |

## Related

- [MONOREPO.md](./MONOREPO.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
