# Track 5 — Investor dossier depth

Closes north-star **N4** (team/products/licenses) and **N6** (regulatory on dossier) without a second database or multi-tenant billing. Builds on Track 4 SQLite hardening.

## Scope

| ID | Deliverable | Notes |
|----|-------------|-------|
| P5-1 | Cap table ingest | `round_participants` → `cap_table_holdings`; daily `cap_table_rollup` |
| P5-2 | Dossier licenses tab | `regulatory_licenses` + `license_claims` on company API + dashboard |
| P5-3 | Dossier cap table tab | `cap_table_holdings` on company API + dashboard |
| P5-4 | — | Billing / org RBAC deferred (product decision) |

## P5-1 — Cap table

- Source: aggregated investors on `funding_rounds` (`round_participants` + `investor_firms`)
- No ownership % until filings provide it — `ownership_pct` stays null
- `share_class`: `lead` when `is_lead`, else participant `role`
- `source_url`: stable `funding_round:{id}:investor:{id}` for idempotent upsert

```bash
make cap-table-rollup
```

Disable daily step: `CI_CAP_TABLE_ROLLUP=0`

## P5-2 / P5-3 — Dashboard

Company dossier tabs: **Licenses**, **Cap table** (hash routes `#licenses`, `#cap_table`).

## Verification

```bash
make lint
make cap-table-rollup
uv run pytest tests/test_cap_table_rollup.py -q
cd apps/api && bun test
cd apps/dashboard && bun run check
```

## Exit criteria

- Daily pipeline runs cap table rollup after funding rollup (when enabled)
- Dossier shows licenses and cap table for companies with data
- Tests cover rollup upsert + API fields
