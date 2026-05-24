# Competitor Intel — agent notes

# Project layout (monorepo)

- **Root:** `~/Documents/Competitor-Intel/`
- **v1 north star:** [docs/V1_PIPELINE.md](docs/V1_PIPELINE.md) — pipeline-first; `make daily-prod`, `make grok-refresh`, `make v1-check`
- **Operational pipeline:** `packages/py-collectors/`, **`apps/worker/daily_intel.py`** (canonical daily entry; not `automation/daily_intel.py`), SQLite `data/competitor_intel.db`, `integrations/hermes/`
- **Python toolchain:** `uv sync` from repo root (no pip); workspace packages: `py-core`, `py-collectors` only
- **Lint/format:** `make lint` → `make lint-py` (Ruff + ty) — see [docs/LINTING.md](docs/LINTING.md)
- **Env:** `CI_DB_PATH`, `HERMES_AGENT_ROOT`, `CI_SKIP_GROK_X` — see `.env.example`
- **SQLite SSOT:** `packages/py-core/db/` + [docs/SQLITE.md](docs/SQLITE.md) — always `get_conn()`, WAL, writer lock for parallel collectors
- **Roadmap (SSOT — what to build):** `docs/ROADMAP.md` · **Doc index:** `docs/README.md`
- **Handbook:** `docs/HANDBOOK.md`
- **Pipeline (signals + rollups):** `docs/PIPELINE.md`
- **New session handoff:** `docs/AGENT_HANDOFF.md`
- **Hermes integration:** `integrations/hermes/` — HTTP/CLI only, no embedded imports

Legacy Hermes agent copy remains at `~/.hermes/agents/competitor_intel/` (see `MIGRATED.md`); do not edit unless migrating stragglers.

Do not refactor Hermes agent boilerplate outside the integration shim unless asked.

---

description: Behavioral guidelines to reduce common LLM coding mistakes. Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria.

alwaysApply: true

---

# Karpathy behavioral guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:

- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

```

1. [Step] → verify: [check]

2. [Step] → verify: [check]

3. [Step] → verify: [check]

```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.