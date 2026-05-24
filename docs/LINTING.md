# Linting and formatting

Track 3 engineering tooling (CI optional). Two stacks: **Python** (Ruff + ty) and **TypeScript/JavaScript** (Oxc: Oxfmt + Oxlint).

## Python — Ruff + ty

| Tool | Role | Replaces |
|------|------|----------|
| [Ruff](https://docs.astral.sh/ruff/) | Lint + format (one binary) | flake8, isort, black, much of pyupgrade |
| [ty](https://docs.astral.sh/ty/) | Type checking (Rust, uv-native) | mypy, Pyright for CI gates |

Config lives in root `pyproject.toml`: `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`, `[tool.ty.*]`.

### Commands

```bash
make lint-py          # ruff check + ruff format --check + ty check
make lint-py-fix      # auto-fix ruff issues + format (does not fix ty)
uv run ruff check packages apps/worker apps/cli tests scripts
uv run ty check
```

### Baseline (2026-05-20)

**Green:** `make lint` passes (Ruff check + format, ty with zero errors, Oxfmt/Oxlint, `svelte-check` with zero errors). Initial debt (~192 Ruff, ~169 ty) was cleared via `make lint-py-fix`, targeted fixes, and replacing deprecated `datetime.utcnow()` with `datetime.now(UTC)`.

### Workspace layout

ty `environment.root` includes `packages/py-core`, `packages/py-collectors`, `packages/py-enterprise`, plus `apps/worker`, `apps/cli`, `tests`, `scripts`. Collectors import `db.*` and `collectors.*` via `PYTHONPATH` at runtime; ty resolves those paths through the configured roots.

### Editor

- Ruff LSP or Ruff extension (format + lint on save).
- ty language server: `ty server` or editor plugin from Astral.

`pyrightconfig.json` was removed — it pointed at legacy `src/` / `collectors/` paths. Use **ty** as the type-check SSOT.

---

## TypeScript / JavaScript — Oxc (Oxfmt + Oxlint)

| Tool | Role | Replaces (in this repo) |
|------|------|-------------------------|
| [Oxfmt](https://oxc.rs/docs/guide/usage/formatter/) | Formatter | Prettier on `apps/api` |
| [Oxlint](https://oxc.rs/docs/guide/usage/linter/) | Linter | ESLint on `apps/api` |

Root `package.json` holds devDependencies; apps do not duplicate Oxc installs.

Config:

- `.oxfmtrc.json` — ignore `node_modules`, `.svelte-kit`, `dist`, etc.
- `.oxlintrc.json` — correctness + suspicious; TypeScript plugin enabled

### Commands

```bash
bun install            # once at repo root (installs oxfmt + oxlint)
make lint-js           # oxfmt --check + oxlint
make lint-js-fix       # format + oxlint --fix
bun run fmt            # write formatting
bun run fmt:check      # check only
```

### Scope

Oxc targets **`apps/api/src`** and **`apps/dashboard/src`** (`.ts` / `.js`). Svelte single-file components are **not** formatted by Oxfmt; use `bun run check` in `apps/dashboard` for Svelte/TS diagnostics (`svelte-check`).

### API app scripts

`apps/api/package.json` still lists legacy `eslint` / `prettier` scripts for now. Prefer root `make lint-js` / `bun run fmt` from the monorepo root.

---

## Combined gate

```bash
make lint    # lint-py + lint-js + dashboard svelte-check
```

`make enterprise-check` = compile + test-cov + intel-gate + golden-eval + API smoke + dashboard check (no lint). For Track 3 PR bar use **`make track3-verify`** (`lint` + `test-cov` + `golden-eval` + `test-api`). CI runs lint, tests, gate, and dry-run daily on the Python job (see `.github/workflows/ci.yml`).

---

## Pre-commit (optional)

Example `.pre-commit-config.yaml` hooks (not installed by default):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: ty
        name: ty
        entry: uv run ty check
        language: system
        pass_filenames: false
      - id: oxfmt
        name: oxfmt
        entry: bun run fmt:check
        language: system
        pass_filenames: false
```

---

## References

- Ruff: https://docs.astral.sh/ruff/
- ty: https://docs.astral.sh/ty/
- Oxfmt quickstart: https://oxc.rs/docs/guide/usage/formatter/quickstart.html
- Oxlint: https://oxc.rs/docs/guide/usage/linter/
