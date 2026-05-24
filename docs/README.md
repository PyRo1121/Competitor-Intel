# Documentation

**Start here:** [ROADMAP.md](ROADMAP.md) — single source of truth for what to build and in what order.

## Core (read these)

| Document | Use when you need |
|----------|-------------------|
| [ROADMAP.md](ROADMAP.md) | Priorities, tracks 0–5 (engineering exit criteria), backlog IDs |
| [ROADMAP_PRODUCTION.md](ROADMAP_PRODUCTION.md) | **What “production product” still requires** (Track 6, phased) |
| [PIPELINE.md](PIPELINE.md) | Data layers, signal/funding/jobs flow, Makefile targets, known gaps |
| [HANDBOOK.md](HANDBOOK.md) | Schema, collectors, feeds, commands, agent onboarding |
| [SQLITE.md](SQLITE.md) | WAL tuning, writer lock, batch ingest, env knobs, throughput |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Monorepo layout, dual stack, ingest model, X/Grok flow |
| [LINTING.md](LINTING.md) | Ruff + ty (Python), Oxfmt + Oxlint (TS/JS), `make lint` |

## Domain guides

| Document | Use when you need |
|----------|-------------------|
| [JOBS.md](JOBS.md) | Job claims, ATS, rollup tables |
| [SCHEDULING.md](SCHEDULING.md) | Cron tiers: frequent / Grok / daily |
| [DATA_AUDIT.md](DATA_AUDIT.md) | Trust tiers, domain registry (companion to dashboard `/data-quality`) |
| [CONFIDENCE_SCORING.md](CONFIDENCE_SCORING.md) | Corroboration weights and anti-gaming rules |

## Integration

| Document | Use when you need |
|----------|-------------------|
| [architecture/HERMES_INTEGRATION.md](architecture/HERMES_INTEGRATION.md) | Hermes HTTP/CLI model, Grok ingest, enrich queues |
| [../integrations/hermes/README.md](../integrations/hermes/README.md) | `call_intel.sh` quick reference |

## Session handoff

| Document | Use when you need |
|----------|-------------------|
| [AGENT_HANDOFF.md](AGENT_HANDOFF.md) | Paste into a new agent session |

## Evidence (reference only)

| Document | Use when you need |
|----------|-------------------|
| [audit-file-by-file-2026-05-19.md](audit-file-by-file-2026-05-19.md) | 40-shard census — why a finding exists |

Do not add new top-level plan docs. Update **ROADMAP.md** for priorities; **PIPELINE.md** for operational behavior.
