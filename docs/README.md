# Documentation

**Progress (check off in order):** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md)  
**Product:** [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) · **Operations:** [PIPELINE.md](PIPELINE.md) · **Standards:** [ENGINEERING.md](ENGINEERING.md)

| Document | Use when |
|----------|----------|
| **[EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md)** | **What to do next** — ordered tasks for humans + AI |
| [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) | Why we build; scoring/trust/SaaS shape |
| [PIPELINE.md](PIPELINE.md) | What runs daily, active collectors, `make verify` |
| [ENGINEERING.md](ENGINEERING.md) | Production naming, shared modules, no dead code |
| [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) | Kill orphan scripts; re-home deleted tooling as modules |
| [SCHEDULING.md](SCHEDULING.md) | Cron: `daily-prod`, `frequent`, `grok-refresh` |
| [SQLITE.md](SQLITE.md) | WAL, writer lock, backup, `CI_DB_PATH` |
| [JOBS.md](JOBS.md) | Job claims, ATS, `job_rollup` |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Monorepo layout |
| [LINTING.md](LINTING.md) | `make lint`, Ruff, ty |
| [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md) | Hermes / Grok boundaries |
| [../integrations/hermes/README.md](../integrations/hermes/README.md) | `call_intel.sh` commands |

Do not add historical roadmap or audit shards here; extend **PIPELINE.md** for operator changes.
