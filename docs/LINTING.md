# Linting and formatting

Track 3 engineering tooling. **Python only** (v1 pipeline repo): Ruff + ty.

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

### Workspace layout

ty `environment.root` includes `packages/py-core`, `packages/py-collectors`, plus `apps/worker`, `apps/cli`, `tests`, `scripts`. Collectors import `db.*` and `collectors.*` via `PYTHONPATH` at runtime; ty resolves those paths through the configured roots.

### Editor

- Ruff LSP or Ruff extension (format + lint on save).
- ty language server: `ty server` or editor plugin from Astral.

`pyrightconfig.json` was removed — it pointed at legacy `src/` / `collectors/` paths. Use **ty** as the type-check SSOT.

---

## Combined gate

```bash
make lint    # alias for lint-py
```

**v1 bar:** `make v1-check` = compile + test-cov + intel-gate + golden-eval + claims-audit-strict. CI runs the same Python job (see `.github/workflows/ci.yml`).

---

## Pre-commit (optional)

Example `.pre-commit-config.yaml` hooks (not installed by default):

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
      - id: ruff-format
```
