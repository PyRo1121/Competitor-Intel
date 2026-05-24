# py-enterprise freeze (Track 4 P4-2)

The `packages/py-enterprise/` SQLAlchemy stack is **frozen**. Operational truth lives in **SQLite + py-collectors** (no parallel DB).

## Rules

1. **Canonical ingest:** `packages/py-collectors/collectors/*` → `raw_signals` / `intelligence_events` via `db.ingest`.
2. **Enterprise is shadow-only:** opt-in via `CI_ENTERPRISE_RSS=1` in `daily_intel` or `make enterprise-rss`.
3. **No prod SQLite by default:** `enterprise_collect` and `make enterprise-rss-live` call `assert_enterprise_sqlite_safe()` — they refuse `data/competitor_intel.db` unless `CI_ENTERPRISE_ALLOW_PROD=1`.
4. **Do not merge** enterprise models into operational migrations without an explicit product decision.

## Commands

```bash
make enterprise-rss          # dry-run CLI (safe)
make enterprise-rss-live     # live shadow collect (blocked on default prod DB)
CI_DB_PATH=data/ci_test.db make enterprise-rss-live   # OK on test DB
```

## Override (operators only)

```bash
export CI_ENTERPRISE_ALLOW_PROD=1   # acknowledges writing via SQLAlchemy to prod SQLite
make enterprise-rss-live
```
