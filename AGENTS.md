# Competitor Intel — agent notes

## GBrain Configuration (configured by /setup-gbrain)

- Engine: pglite
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-05-19
- MCP registered: yes (Cursor user `~/.cursor/mcp.json`, command `gbrain serve`)
- Memory sync: full → [https://github.com/PyRo1121/gstack-brain-pyro1121.git](https://github.com/PyRo1121/gstack-brain-pyro1121.git)
- Current repo policy: unset (no `origin` remote on this repo)

Restart Cursor after MCP changes so `gbrain` tools load in new sessions.

## GBrain Search Guidance (configured by /sync-gbrain)



GBrain is set up and synced on this machine. Prefer `gbrain search` / `gbrain query` over Grep when the question is semantic or you do not know the exact identifier yet. Indexed corpora:

- This repo's code (imported via `gbrain import`).
- `~/.gstack/` curated memory (`gstack-brain-pyro1121` federated source).

Prefer gbrain when:

- "Where is X handled?" → `gbrain search "<terms>"` or `gbrain query "<question>"`
- Symbol lookup → `gbrain code-def <symbol>`, `gbrain code-refs`, `gbrain code-callers`
- Past plans / learnings → `gbrain search "<terms>" --source gstack-brain-pyro1121`

Grep stays right for exact strings, regex, and file globs. Run `/sync-gbrain` to refresh indexing.



## Skill routing (gstack)

When the user's request matches an available gstack skill, use it. When in doubt, invoke the skill.


| Request                       | Skill                                           |
| ----------------------------- | ----------------------------------------------- |
| Product ideas / brainstorming | `/office-hours`                                 |
| Strategy / scope              | `/plan-ceo-review`                              |
| Architecture                  | `/plan-eng-review`                              |
| Design system / plan review   | `/design-consultation` or `/plan-design-review` |
| Full review pipeline          | `/autoplan`                                     |
| Bugs / errors                 | `/investigate`                                  |
| QA / test site behavior       | `/qa` or `/qa-only`                             |
| Code review / diff            | `/review`                                       |
| Visual polish                 | `/design-review`                                |
| Ship / deploy / PR            | `/ship` or `/land-and-deploy`                   |
| Save / resume context         | `/context-save` / `/context-restore`            |
| Refresh gbrain index          | `/sync-gbrain`                                  |


## Project layout (monorepo)

- **Root:** `~/Documents/Competitor-Intel/`
- **Operational pipeline:** `packages/py-collectors/`, `apps/worker/daily_intel.py`, SQLite `data/competitor_intel.db`
- **Handbook:** `docs/HANDBOOK.md`
- **Dashboard/API:** `apps/dashboard/`, `apps/api/`
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