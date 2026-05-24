# Linear — project tracking

**Team:** COM (Competitor Intel)  
**Project:** [Competitor Intel](https://linear.app/competitor-intel/project/competitor-intel-e52ae7293016)  
**Checklist SSOT:** [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) (keep in sync with issue state)

---

## For humans

1. Pick work from the project board (milestones = phases P0, E1, …).
2. Move issue to **In Progress** when you start.
3. Branch: `com-42-short-description` (lowercase ok; Linear links `COM-42`).
4. Commit with `COM-42: what you changed` or put `fixes COM-42` in the merge commit.
5. Open PR using the template; merge to `main`.
6. CI **Linear sync** moves issues to **Done** when close keywords are present (see below).
7. Check off the matching line in `EXECUTION_CHECKLIST.md`.

---

## For AI agents (Cursor, Hermes)

**Before coding**

1. Read [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) for phase priority (current focus: **P0**).
2. In Linear, find or create an issue on project **Competitor Intel** with a clear title.
3. Note the identifier (`COM-123`). Use it in branch and commits.

**While coding**

- One issue per logical change; don’t batch unrelated work.
- Apply labels when useful:
  - **area:** `area:pipeline`, `area:collectors`, `area:worker`, `area:hermes`, `area:data`, `area:docs`, `area:ci`, `area:tests`, `area:api`, `area:dashboard`
  - **workflow:** `workflow:agent-task`, `workflow:human-gate`
  - **type:** Feature / Bug / Improvement (built-in)

**Commits (required format when an issue exists)**

```text
COM-42: tighten funding dedup index check
```

**To auto-close on merge to main** (any of):

```text
fixes COM-42
closes COM-42, COM-43
COM-42: ship dedup fix [done]
```

**Do not** auto-close with only `COM-42:` in the subject unless you add `[done]` or `(done)`.

**After merge**

- Confirm issue is **Done** in Linear.
- Mark checklist `[x]` in `EXECUTION_CHECKLIST.md` with date if not already.

**MCP (Cursor)**

- Linear MCP: `~/.cursor/mcp.json` (see `.cursor/mcp.json.example`). Reload Cursor after changes.
- Prefer MCP tools for search/create/update when available; otherwise API key + `docs/LINEAR.md` conventions.

---

## Labels

| Label | Use |
|-------|-----|
| `area:pipeline` | daily_intel, Makefile, cron, rollups |
| `area:collectors` | `packages/py-collectors` |
| `area:worker` | `apps/worker` |
| `area:hermes` | `integrations/hermes`, Grok/X |
| `area:data` | SQLite schema, migrations, quality gates |
| `area:docs` | docs only |
| `area:ci` | GitHub Actions, linear sync |
| `area:tests` | pytest, fixtures |
| `area:api` | read API (P3+) |
| `area:dashboard` | Svelte dashboard (P3+) |
| `workflow:agent-task` | Expected to be executed by an agent |
| `workflow:human-gate` | Requires human judgment (e.g. 7 green dailies) |
| `ci:auto-closed` | Applied by automation when commit closed issue |

Milestones on the project map to phases (S0, P0, E1, P1–P7, E2, E3). Prefer milestone for phase; use `area:*` for filtering.

---

## CI: commit → Done

Workflow: [.github/workflows/linear-sync.yml](../.github/workflows/linear-sync.yml)

On push to `main` / `master`, parses commits in the push range and calls Linear API when:

| Pattern | Action |
|---------|--------|
| `fixes COM-12` / `closes COM-12` / `resolves COM-12` | → **Done** + label `ci:auto-closed` |
| `COM-12: summary [done]` | → **Done** + label `ci:auto-closed` |
| `COM-12: summary` only | No auto-close (link via GitHub integration optional) |

**Setup (one time)**

1. Linear → Settings → API → Create personal API key.
2. GitHub repo → Settings → Secrets → Actions → `LINEAR_API_KEY`.
3. Optional: Linear → Settings → Integrations → **GitHub** (branch/PR linking, magic words on merge).

**Manual test**

```bash
export LINEAR_API_KEY=lin_api_...
uv run python .github/scripts/linear_commit_sync.py --dry-run --message "fixes COM-5"
make linear-sync-dry
```

**Dispatch dry-run on GitHub:** Actions → Linear sync → Run workflow → dry_run true.

Config (team/state UUIDs): [.github/linear.config.json](../.github/linear.config.json)

---

## GitHub ↔ Linear (recommended)

Connect the GitHub integration in Linear so that:

- Branches named `com-42-*` or `COM-42-*` attach to the issue.
- PR titles with `COM-42` show in Linear.
- Merge commit `fixes COM-42` also closes via Linear’s native GitHub app (redundant with our workflow but harmless).

Our `linear-sync.yml` still helps when you squash-merge with a custom message or push directly to main.

---

## Security

- Never commit `LINEAR_API_KEY` to the repo.
- Rotate keys if exposed in chat or logs.
- CI uses GitHub Actions secret only.

---

## Related docs

| Doc | Role |
|-----|------|
| [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) | Ordered tasks ↔ milestones |
| [ROADMAP_ENTRYPOINTS.md](ROADMAP_ENTRYPOINTS.md) | E1 slice detail |
| [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md) | Product phases P0–P7 |
| [ENGINEERING.md](ENGINEERING.md) | Code standards |
