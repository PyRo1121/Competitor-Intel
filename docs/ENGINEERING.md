# Engineering standards

**Applies to:** all code, filenames, Makefile targets, and new docs.  
**Checklist order:** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) · **Product:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md)

---

## Naming

| Do | Don't |
|----|--------|
| Production names (`daily-prod`, `PIPELINE.md`, `verify`) | Versioned filenames (`V1_PIPELINE`, `v2_api`) |
| Phase labels **only in docs/checklist** (`P0`, `E1`) | `v1` / `v2` in Python modules, env vars, or types |
| Describe behavior (`daily_no_x`, `trust_tier`) | `new_`, `legacy_`, `enhanced_` unless one canonical path remains |

External API paths (e.g. `https://api.x.ai/v1`) are unchanged.

---

## Structure

1. **Single writer path** — `apps/worker/daily_intel.py` + `collector_registry.py` schedule collectors; no second daily orchestrator.
2. **Shared logic in packages** — `packages/py-core` (DB, ingest, QA), `packages/py-collectors` (sources, rollups). Apps are thin orchestration and CLI.
3. **One file when cohesion allows** — prefer extending an existing module over `foo_v2.py` / `foo_new.py`.
4. **Shared types** — trust tiers, source weights, claim shapes live in one module (e.g. `py-core` or `collectors` types module) and are imported everywhere.
5. **Registry SSOT** — if a collector is not in `collector_registry` (daily, frequent, grok, or `INTEL_CLI_COLLECTORS`), it is not scheduled; delete or merge dead `__main__` scripts when safe.

---

## No dead code

- Remove unused modules, Makefile targets, and CLI subcommands when a change makes them orphaned.
- Do not keep “just in case” collectors on disk without a registry entry unless actively migrating — track in [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md).
- Tests-only helpers live under `tests/`, not `scripts/`.
- Run `make verify` before claiming a slice done.

---

## Duplication

| Pattern | Prefer |
|---------|--------|
| Two fetch scripts | One module, `CI_X_PROVIDER` switch |
| Script + collector doing same job | Collector module; worker/CLI calls it |
| Copy-paste SQL | View or helper in `py-core/db` |
| Parallel doc specs | Link to [PIPELINE.md](PIPELINE.md) / [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) |
| Scheduling / health probes | `hermes cron` + Python (`integrations/hermes/cron_*.py`, `apps/cli/healthcheck.py`) — not `.sh` or system crontab |

---

## Makefile targets (production)

| Target | Purpose |
|--------|---------|
| `make daily-prod` | Production cron ingest |
| `make grok-refresh` | X/Grok batch |
| `make verify` | compile + test-cov + intel-gate + golden-eval + claims-audit-strict |
| `make verify-dry-run` | `verify` + daily dry-run |
| `make health-check` | SQLite (+ optional API if `CI_HEALTH_REQUIRE_API=1`) |

Aliases like `track2-verify` may point at `verify` for compatibility.

---

## Agents

When completing work:

1. Update [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) checkboxes.
2. Follow this file for naming and dead-code rules.
3. Do not add version suffixes to new files.
