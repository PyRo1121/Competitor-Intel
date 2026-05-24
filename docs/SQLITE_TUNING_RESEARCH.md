# SQLite tuning research (Exa + sqlite.org)

**Question:** What to tune so `database is locked` stops and ingest gets faster?  
**Short answer:** SQLite is not “too slow” for this workload when **one writer batches writes** under **WAL + `synchronous=NORMAL`**. Your pain is mostly **many writer processes** + **per-row lock/fsync patterns**, not missing a magic pragma.

**SSOT in repo:** [SQLITE.md](SQLITE.md) · implementation: `packages/py-core/db/sqlite_tuning.py`, `writer_lock.py`, `ingest.py`, `batch.py`

---

## What SQLite actually guarantees (non-negotiable)

From [SQLite isolation](https://www.sqlite.org/isolation.html) and [WAL](https://www.sqlite.org/wal.html):

| Fact | Implication for Competitor Intel |
|------|----------------------------------|
| **Exactly one writer at a time** per database file | 6 parallel collector **processes** cannot multiply write throughput; they **queue** |
| WAL: readers don’t block writers; writers don’t block readers | Dashboard/API reads OK during ingest |
| WAL: **still one writer** | `CI_PARALLEL_COLLECTORS=4` = 4 processes taking turns → lock waits / `database is locked` |
| `busy_timeout` is **per connection**, not stored in the DB file | Every `get_conn()` must set it (you do via `apply_profile`) |
| `BEGIN` then later `INSERT` can deadlock with another `BEGIN` | Writers should use **`BEGIN IMMEDIATE`** ([forum](https://sqlite.org/forum/forumpost/54b14721c5)) — available as `transaction(immediate=True)` |

**Conclusion:** Tuning PRAGMAs can give **10×–100×** on a **single** writer with batched transactions ([sqlprostudio](https://www.sqlprostudio.com/blog/50-how-to-improve-sqlite-insert-performance), [travishorn](https://travishorn.com/a-hands-on-exploration-of-sqlite-for-production/)). It cannot turn **six writers** into six parallel SQLite writers.

---

## Recommended PRAGMA stack (industry + sqlite.org)

Canonical production stack ([sqlite.org WAL + synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous), [docsaid WAL/busy_timeout](https://docsaid.org/en/blog/sqlite-wal-busy-timeout-for-workers)):

```sql
PRAGMA journal_mode = WAL;        -- persistent on DB file
PRAGMA synchronous = NORMAL;      -- safe + fast with WAL (not FULL unless power-loss durability required)
PRAGMA foreign_keys = ON;       -- per connection
PRAGMA busy_timeout = 120000;     -- ms; wait instead of instant SQLITE_BUSY
PRAGMA cache_size = -512000;    -- ~512 MiB (negative = KiB)
PRAGMA mmap_size = 536870912;    -- 512 MiB — helps reads, not bulk insert CPU
PRAGMA temp_store = MEMORY;
PRAGMA journal_size_limit = 64000000;  -- cap -wal growth (~64MB)
PRAGMA wal_autocheckpoint = 10000;     -- default daily; 5000 for ingest_bulk
```

### What each knob does

| PRAGMA | Why | Your repo |
|--------|-----|-----------|
| **journal_mode=WAL** | Append writes to `-wal`; concurrent reads | ✅ `sqlite_tuning.py` |
| **synchronous=NORMAL** | Avoid fsync every commit; WAL still consistent on app crash | ✅ default + ingest_bulk |
| **busy_timeout** | Turns `SQLITE_BUSY` into wait+retry | ✅ 120s default (`CI_SQLITE_BUSY_TIMEOUT_MS`) |
| **cache_size** | Fewer page reads during ingest | ✅ ~512 MiB |
| **mmap_size** | Faster reads / less syscall overhead | ✅ 512 MiB |
| **journal_size_limit** | Prevents multi-GB `-wal` on disk | ✅ 64MB |
| **wal_autocheckpoint** | Trade write speed vs WAL file size / read degradation | ✅ 10000 / 5000 ingest |
| **PRAGMA optimize** | Planner stats (3.46+) | ✅ on open/close |

### What NOT to expect

| Myth | Reality |
|------|---------|
| “WAL = many writers” | WAL = many **readers** + **one** writer |
| “Raise cache → faster inserts” | Sequential keys already fast; random keys still slow ([voidstar](https://voidstar.tech/sqlite_insert_speed/)) |
| **synchronous=OFF** for prod | Faster but corruption risk on crash — avoid |
| **mmap fixes EDGAR bulk** | mmap helps **reads**; writes still go through btree + WAL |

---

## Why you saw `database is locked` (EDGAR + parallel batch)

From your failed `daily-prod` log:

1. **RSS, HN, GitHub, YC, TechCrunch, EDGAR, ESMA** ran as **separate processes** (`parallel_collect.py`).
2. Each process holds a connection and writes `raw_signals`.
3. EDGAR Form D bulk used `RawSignalBatchWriter` — good **batch commits**, but still competes with 5 other writers for the **single SQLite writer slot**.
4. `writer_lock` (POSIX flock) **serializes** cross-process writes — correct, but **wall time = sum of all writers** + retry backoff.

SQLite.org + [Stack Overflow WAL practices](https://stackoverflow.com/questions/75550581/sqlite-best-practices-for-dealing-with-multiple-process-access): many processes + short transactions + `busy_timeout` = OK; many processes + **long** write transactions = lock storms.

**Not a missing pragma** — an **architecture** mismatch: parallel fetch, **serial** SQLite writes.

---

## Speed: what actually moves the needle

### A. Single writer, batched (biggest win)

| Pattern | Inserts/sec (typical benchmarks) | Source |
|---------|----------------------------------|--------|
| Autocommit per INSERT | ~85–400 | [sqlprostudio](https://www.sqlprostudio.com/blog/50-how-to-improve-sqlite-insert-performance) |
| One transaction + many INSERTs | ~50k–125k | same |
| WAL + NORMAL + batched | ~33k+ | [travishorn](https://travishorn.com/a-hands-on-exploration-of-sqlite-for-production/) |

**You already have:** `INSERT OR IGNORE` + unique `(source, signal_type)`, `RawSignalBatchWriter`, RSS batched `writer_lock` for store phase.

**Still to tighten:** EDGAR path uses `writer_lock` **per row** inside `batch.insert()` — correct for safety, expensive under contention. Prefer **one lock per flush** (hold lock once per `commit_every` batch).

### B. Fewer concurrent writer processes

| Setting | Effect |
|---------|--------|
| `CI_PARALLEL_COLLECTORS=3` (new default) | Less flock contention |
| **Better:** collectors write **staging JSONL** → **one** `ingest_staging` merge ([SQLITE.md](SQLITE.md) already recommends) | One SQLite writer; parallel HTTP unchanged |

### C. WAL maintenance (latency for reads + disk)

[WAL checkpoint](https://www.sqlite.org/wal.html#ckpt):

- If readers always active, WAL grows (“checkpoint starvation”).
- After daily: `PRAGMA wal_checkpoint(RESTART)` or `TRUNCATE` in quiet window.
- You have `post_ingest_wal_maintenance()` / `make sqlite-checkpoint`.

| When | Command |
|------|---------|
| After large daily | `make sqlite-checkpoint` (TRUNCATE) |
| Ops check | `make sqlite-health` → `wal_log_frames`, `wal_checkpoint_busy` |

### D. Connection discipline

- **`sqlite3.connect(timeout=60)`** — Python wait to *open* file  
- **`PRAGMA busy_timeout=120000`** — wait during *lock* inside SQL  
Both needed ([forum on busy_timeout](https://sqlite.org/forum/info/538711653d62ec90)).

### E. Write transactions: `BEGIN IMMEDIATE`

For any multi-statement write section:

```python
with transaction(immediate=True):
    ...
```

Avoids read→write upgrade deadlock when two collectors share patterns ([sqlite forum](https://sqlite.org/forum/forumpost/54b14721c5)).

---

## Advanced (only if you must keep multi-writer processes)

| Option | Notes |
|--------|------|
| **BEGIN CONCURRENT** ([doc](https://github.com/sqlite/sqlite/blob/main/doc/begin_concurrent.md)) | Multiple writers in **one process**; commits still serialized; needs WAL + non-overlapping pages |
| **unix-excl VFS** | Slightly faster locks when all clients same host |
| **Postgres** | Real concurrent writers — only if SQLite contract breaks |

For Competitor Intel at current scale, **staging + single merge** beats exotic SQLite modes.

---

## Tuning checklist (actionable)

### Already aligned with research

- [x] WAL + `synchronous=NORMAL` on collectors
- [x] `busy_timeout` 120s via profile
- [x] Large `cache_size` / `mmap_size`
- [x] `journal_size_limit`
- [x] `writer_lock` + `retry_locked` on ingest
- [x] `ingest_bulk` profile for EDGAR
- [x] Dedup unique index + `INSERT OR IGNORE`
- [x] Fixed `locking_mode=EXCLUSIVE` stuck after init (see SQLITE.md)

### Do next (performance + locks)

1. **Re-run daily** with `CI_PARALLEL_COLLECTORS=2` after parallel HTTP fixes.
2. **EDGAR:** ensure `RawSignalBatchWriter` holds **one** `writer_lock` per flush, not per row.
3. **Schedule:** move EDGAR bulk + heavy Algolia HN to **weekly** or post-daily slot (not same wall clock as RSS/HN).
4. **After successful daily:** `make sqlite-checkpoint` + `PRAGMA optimize`.
5. **Monitor:** `make sqlite-health` — if `wal_log_frames` huge, lower `wal_autocheckpoint` or checkpoint more often.
6. **Medium term:** implement **staging → single merge** (eliminates cross-process writer fight entirely).

### Env block for `.env` (copy/paste)

```bash
CI_SQLITE_BUSY_TIMEOUT_MS=120000
CI_SQLITE_WRITER_LOCK=1
CI_SQLITE_WRITER_LOCK_TIMEOUT_SEC=300
CI_SQLITE_CACHE_KIB=-512000
CI_SQLITE_MMAP_BYTES=536870912
CI_SQLITE_WAL_AUTOCHECKPOINT=10000
CI_SQLITE_BATCH_COMMIT=500
CI_PARALLEL_COLLECTORS=2
```

---

## Vectors / Ollama (separate from ingest locks)

Embedding is **read SQLite → call Ollama → write vectors**. That is a **second writer** if it runs during daily.

**Rule:** Run `embedding_generator` on its own schedule **after** daily checkpoint, or in same process **after** collectors finish — not parallel with 6 collector processes.

---

## Bottom line

| Blame | Verdict |
|-------|---------|
| SQLite unsuitable | **No** for single-host, read-heavy + one batched writer |
| Missing WAL/synchronous | **No** — already set |
| Missing busy_timeout | **No** — 120s on profile |
| **Multi-process parallel collectors all writing** | **Yes** — primary cause of locks + slow wall clock |
| Per-row autocommit / unbatched inserts | **Partially fixed**; EDGAR batch can tighten lock scope |
| HN/RSS sequential HTTP | **Fixed in code** (parallel fetch); separate from SQLite |

**SQLite tuning gets you from “hundreds/sec” to “tens of thousands/sec” on one writer. Architecture tuning gets you from “six writers fighting” to “one writer, six fetchers.”** Do both; don’t pause the product for weeks — but **do** run the checklist above before trusting 7 green dailies.

---

## Sources (Exa / sqlite.org)

- [Write-Ahead Logging](https://www.sqlite.org/wal.html)
- [PRAGMA reference](https://www.sqlite.org/pragma.html) — `busy_timeout`, `synchronous`, `journal_size_limit`, `mmap_size`
- [Isolation in SQLite](https://www.sqlite.org/isolation.html)
- [WAL locking notes](https://sqlite.org/src/doc/tip/doc/wal-lock.md)
- [How to Improve SQLite INSERT Performance](https://www.sqlprostudio.com/blog/50-how-to-improve-sqlite-insert-performance)
- [SQLite in Production benchmark](https://travishorn.com/a-hands-on-exploration-of-sqlite-for-production/)
- [WAL + busy_timeout for workers](https://docsaid.org/en/blog/sqlite-wal-busy-timeout-for-workers)
- [Multi-process best practices (SO)](https://stackoverflow.com/questions/75550581/sqlite-best-practices-for-dealing-with-multiple-process-access)
- [BEGIN IMMEDIATE / upgrade deadlock](https://sqlite.org/forum/forumpost/54b14721c5)
