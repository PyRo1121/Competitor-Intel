# Documentation

**North star:** [V1_PIPELINE.md](V1_PIPELINE.md) — solo-operator pipeline, cron, and done checklist.

| Document | Use when |
|----------|----------|
| [V1_PIPELINE.md](V1_PIPELINE.md) | What runs daily, active collectors, v1 gates |
| [SCHEDULING.md](SCHEDULING.md) | Cron: `daily-prod`, `frequent`, `grok-refresh` |
| [SQLITE.md](SQLITE.md) | WAL, writer lock, backup, `CI_DB_PATH` |
| [JOBS.md](JOBS.md) | Job claims, ATS, `job_rollup` |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Monorepo layout |
| [LINTING.md](LINTING.md) | `make lint`, Ruff, ty |
| [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md) | Hermes / Grok boundaries |
| [../integrations/hermes/README.md](../integrations/hermes/README.md) | `call_intel.sh` commands |

Do not add historical roadmap or audit shards here; extend **V1_PIPELINE.md** for operator changes.
