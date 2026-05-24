# SQLite — enterprise setup (Competitor Intel)

**Research synthesis (Exa + sqlite.org):** [SQLITE_TUNING_RESEARCH.md](SQLITE_TUNING_RESEARCH.md)

Single-file SQLite (`data/competitor_intel.db`) is the production store for this monorepo. With correct tuning it handles **very high read throughput** and **sustained write batches** without Postgres. The limit is **concurrent writers**: SQLite WAL allows many readers + **one writer at a time**.

Implementation SSOT: `packages/py-core/db/`.

## Architecture rules

1. **All Python access** via `db.connection.get_conn()` — never raw `sqlite3.connect()` in collectors/API.
2. **WAL mode** always (`PRAGMA journal_mode=WAL`).
3. **Dedup index** required: `UNIQUE (source, signal_type)` on `raw_signals` → `INSERT OR IGNORE` (no SELECT-before-INSERT).
4. **Parallel HTTP, serialized writes**: collector subprocesses fetch in parallel; writes use `CI_SQLITE_WRITER_LOCK=1` (POSIX flock) by default.
5. **Batch commits** for heavy ingest (EDGAR bulk): `db.batch.RawSignalBatchWriter` commits every N rows.
6. **Bun API** mirrors pragmas in `apps/api/src/db.ts` (single shared connection — do not open RW + RO on same file).

## PRAGMA profiles

| Profile | Use | Highlights |
|---------|-----|------------|
| `default` | Collectors, workers, CLI | WAL, NORMAL sync, 512MB cache/mmap, `PRAGMA optimize=0x10002` on open |
| `ingest_bulk` | EDGAR bulk, staging merge | 512MB cache/mmap, `wal_autocheckpoint=5000` (shorter WAL during bulk) |
| `api_read` | Read-heavy paths | `query_only=ON` |
| `maintenance` | init, migrate, dedupe | `locking_mode=EXCLUSIVE`, FULL sync |

Applied by `db.sqlite_tuning.apply_profile()`.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CI_DB_PATH` | `data/competitor_intel.db` | Database file |
| `CI_SQLITE_BUSY_TIMEOUT_MS` | `120000` | Wait on lock before SQLITE_BUSY |
| `CI_SQLITE_WRITER_LOCK` | `1` | Cross-process flock on `<db>.write.lock` |
| `CI_SQLITE_WRITER_LOCK_TIMEOUT_SEC` | `300` | Max wait for writer lock |
| `CI_PARALLEL_COLLECTORS` | `4` | Parallel collector subprocesses |
| `CI_SQLITE_BATCH_COMMIT` | `500` | Rows per commit in `RawSignalBatchWriter` |
| `CI_SQLITE_CACHE_KIB` | `-512000` | Page cache (~512 MiB) |
| `CI_SQLITE_MMAP_BYTES` | `536870912` | Memory-mapped I/O (512 MiB) |
| `CI_SQLITE_WAL_AUTOCHECKPOINT` | `10000` | WAL checkpoint frequency (pages); ingest_bulk uses `5000` |
| `CI_SQLITE_LOCK_RETRIES` | `16` | Max retries on busy/locked (with jitter backoff) |
| `CI_SQLITE_RETRY_BASE_SEC` | `0.05` | Initial backoff |
| `CI_SQLITE_RETRY_CAP_SEC` | `2.0` | Max backoff per retry |

Set `CI_SQLITE_WRITER_LOCK=0` only if you run a **single** ingest process (e.g. staged JSONL merge).

## Retry stack (three layers)

1. **`PRAGMA busy_timeout`** — connection waits up to 120s inside SQLite before returning `SQLITE_BUSY`.
2. **`db.sqlite_retry.retry_locked`** — exponential backoff + jitter on top of busy_timeout (ingest path).
3. **`db.writer_lock`** — POSIX flock so only one process executes write statements at a time (collectors stay parallel for HTTP).

Bun API: set `PRAGMA synchronous = NORMAL` explicitly (Bun default can be FULL — hurts write throughput). See [Bun SQLite docs](https://bun.com/docs/runtime/bun-sqlite#wal-mode).

## WAL checkpointing

- **Auto:** `wal_autocheckpoint` (default 10000 pages; **5000** on `ingest_bulk` profile) runs PASSIVE checkpoints on COMMIT when WAL is large.
- **Ops:** `make sqlite-checkpoint` → `TRUNCATE` after large daily/full-sweep ingest.
- **Starvation:** long-lived dashboard readers pin WAL snapshots → checkpoint `busy=1`. `sqlite-health` warns when `wal_log_frames` stays high.

Schedule `RESTART` checkpoint when API traffic is low (cron after `make daily`).

## Monitoring (`make sqlite-health`)

Reports: pragma snapshot, `data_version` (cheap change detector), WAL file bytes, passive `wal_checkpoint` stats (`wal_log_frames`, `wal_checkpoint_busy`).

```bash
make sqlite-health
uv run python scripts/sqlite_health.py --analyze
uv run python scripts/sqlite_health.py --backup   # → data/backups/competitor_intel-<UTC>.db
```

## Backup / durability

- **Online backup:** `scripts/sqlite_health.py --backup` (SQLite backup API, safe under WAL).
- **Litestream** (optional): continuous WAL replication to S3 — good for off-box DR; not bundled in-repo.
- **Crash safety:** WAL + `synchronous=NORMAL` is SQLite-recommended; commits may roll back on power loss but DB stays consistent.

## One writer vs many writers (architecture)

**Yes — target shape is: many readers, one write pipeline.**

| Layer | Today | Scale-out |
|-------|--------|-----------|
| Fetch | N parallel collector subprocesses (HTTP/RSS/EDGAR) | Same |
| Write | N processes → **serialized** via `writer_lock` + per-row INSERT | **Preferred:** collectors → JSONL staging → **one** `ingest_staging.py` with `RawSignalBatchWriter` |
| Read | Bun API + dashboard (unlimited WAL readers) | Same |

SQLite allows **one writer at a time** regardless. Extra writer processes only add lock contention — they do not increase write throughput. Flock + retry is correct for current scale; **staging → single merge** is the next step when collector count or EDGAR volume grows (eliminates cross-process lock entirely).

You do **not** need Postgres for this workload if writes are batched/serialized and reads stay WAL-backed.

**Bug fix (2026-05):** `init_database()` used `locking_mode=EXCLUSIVE` and left it on the file — blocking parallel collectors. Init now resets `locking_mode=NORMAL` + WAL before close.

## Throughput expectations (realistic)

| Pattern | Approx throughput |
|---------|-------------------|
| Single process, batched INSERT in one transaction | 30k–300k rows/s (hardware dependent) |
| Many processes, uncoordinated writers | Lock storms → `database is locked` |
| Many processes + writer flock | Serialized writes, stable; wall time = sum of writes |
| API reads under WAL | 50k+ simple SELECTs/s possible with mmap + cache |

Marketing “100k+ reads and writes per second” applies to **read-heavy** or **single-writer batched** workloads — not N uncoordinated writer processes.

## Operator commands

```bash
# Pragmas, WAL size, journal mode
make sqlite-health

# After large ingest — shrink WAL file
make sqlite-checkpoint

# Update planner statistics
uv run python scripts/sqlite_health.py --analyze

# Ensure dedup unique index exists
make migrate-dedup
```

## Parallel daily / full-sweep

`make daily` and `make full-sweep` run `parallel_collect.py` (up to `CI_PARALLEL_COLLECTORS` subprocesses). Each subprocess calls `insert_raw_signal_dedup()` which:

1. Acquires `writer_lock` (if enabled)
2. `INSERT OR IGNORE` with retry/backoff

For zero lock errors during huge EDGAR runs, optionally:

```bash
CI_PARALLEL_COLLECTORS=2 make full-sweep
```

## Code patterns

### Collector (many small inserts)

```python
from db.connection import get_conn
from db.ingest import insert_raw_signal_dedup

conn = get_conn()
cur = conn.cursor()
try:
    for item in items:
        insert_raw_signal_dedup(cur, source, url, data, company_id=cid)
    conn.commit()
finally:
    conn.close()
```

### Bulk ingest (thousands of rows)

```python
from db.batch import RawSignalBatchWriter

with RawSignalBatchWriter(commit_every=500) as batch:
    for row in rows:
        batch.insert("sec_edgar", url, payload, dedup_key=key)
```

### Write-heavy transaction

```python
from db.connection import transaction

with transaction(immediate=True, profile="ingest_bulk") as conn:
    ...
```

## Staging ingest (recommended at scale)

**Default (daily parallel):** `CI_INGEST_STAGING=1`

1. Collectors append JSONL under `data/staging/raw_signals/<run_id>/<collector>.jsonl` (no SQLite writes in collector processes; SELECTs for company match OK).
2. `apps/worker/ingest_staging.py` merges with `RawSignalBatchWriter` + `ingest_bulk` + **one** outer `writer_lock` (batch commits use `use_writer_lock=False`).
3. Post-ingest: `make sqlite-checkpoint` / `post_ingest_wal_maintenance` on daily success.

**Do not** call `writer_lock()` while `CI_INGEST_STAGING=1` unless you are actually writing SQLite in that section. Holding the flock during JSONL-only work blocks `ingest_staging` merge (`TimeoutError` on `<db>.write.lock`). Collectors that were wrong: `yc_collector`, `hackernews_collector` (fixed); pattern to copy: `rss_collector` (`ingest_staging_active()`).

**Bun read API** (`archive/v2-read-surface/api/`): use a single shared connection with `query_only=ON` (see `api_read` profile in Python). Do not run two API servers against the same `CI_DB_PATH` during `make daily-prod` — extra connections extend WAL checkpoint time; they should not take `writer_lock`, but they still compete for filesystem cache and can pin WAL snapshots.

Disable staging: `CI_INGEST_STAGING=0` (legacy per-process SQLite writes + `writer_lock`).

## References

- [SQLite WAL](https://sqlite.org/wal.html)
- [SQLite pragma](https://sqlite.org/pragma.html)
- [Performance tuning (phiresky)](https://phiresky.github.io/blog/2020/sqlite-performance-tuning/)
