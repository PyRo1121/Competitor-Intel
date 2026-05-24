# Track 4 — Enterprise (SQLite-only)

Operational hardening for hosted-style deployment on **bare metal + SQLite WAL**. No Postgres path — single-file DB is the production store ([SQLITE.md](SQLITE.md)).

## Scope delivered

| ID | Item | Implementation |
|----|------|----------------|
| P4-2 / X-11 | Enterprise freeze | [ENTERPRISE_FREEZE.md](ENTERPRISE_FREEZE.md), `assert_enterprise_sqlite_safe()` |
| P4-3 | API rate limits | `apps/api/src/middleware/rateLimit.ts` — `CI_API_RATE_LIMIT_RPM`, bucket pruning |
| P4-4 | Pipeline observability | `step_id` + JSON `pipeline_step` in `run_utils.log_pipeline_step` |
| P4-5 | Regulatory → licenses | `regulatory_extract.py`, daily `regulatory_license_rollup.py` |
| P4-6 | Entity resolution | `company_aliases`, `collectors/entity_resolution.py`, `company_match` integration |
| P4-6 | Cap table (schema) | `cap_table_holdings`, `GET /api/cap-table` — ingest deferred |

## P4-5 — Regulatory pipeline

| Source | Ingest | License claims |
|--------|--------|----------------|
| SEC Form D bulk | `edgar_form_d_bulk.py` | `regulatory_extract` (US jurisdiction, SEC regulator) |
| ESMA MiCA | `esma_mica_collector.py` | `extract_raw_signals._esma_license` |
| Regulatory RSS | `rss_collector.py` | `regulatory_extract` (pattern match on title/summary) |
| Press events | `extract_signals` | regex on `intelligence_events` |

**Daily:** `regulatory_license_rollup.py` runs after `funding_rollup` (default on; `CI_REGULATORY_LICENSE_ROLLUP=0` to skip).

**Not duplicated in** `company_data_rollup` — regulatory licenses are a separate step to avoid double-scanning `raw_signals`.

```bash
make regulatory-license-rollup
```

## P4-6 — Entity resolution

- `company_aliases` maps normalized external names → `company_id`
- `resolve_company_entity()` → alias lookup, then fuzzy match
- `company_match.resolve_company_id()` uses the resolver (optional `record_alias=True`)

Cap table rows are schema-only until a product decision on % ownership sources.

## Auth model (today)

- Reads: open (local/trusted network)
- Writes: `CI_API_KEY` on mutation routes
- Rate limit: all routes except `/health`

## Verification

```bash
make lint
uv run pytest tests/test_regulatory_extract.py tests/test_entity_resolution.py tests/test_extract_raw_signals_bulk.py -q
cd apps/api && bun test
make regulatory-license-rollup
```

## Remaining for full hosted sign-off

- Cap table ingest from Form D / funding participants
- Optional: dashboard licenses tab wired to `/api/licenses`
- Billing / multi-tenant (product decision) — not started; SQLite stays single-tenant
