# Monorepo layout

Competitor Intel is organized as an **apps / packages / infra** monorepo. Python operational code and TypeScript apps share one SQLite database under `data/`.

## Directory map

```
Competitor-Intel/
├── apps/                    # Runnable applications
│   ├── api/                 # Bun + Hono REST API (read-mostly)
│   ├── dashboard/           # Svelte 5 + Vite frontend
│   ├── worker/              # Daily intel pipeline entrypoints
│   └── cli/                 # intel.py, run_intel.py scripts
├── packages/                # uv workspace members
│   ├── py-core/             # competitor-intel-core (db, utils, alerts, ci_paths)
│   ├── py-collectors/       # competitor-intel-collectors (collectors/)
│   └── py-enterprise/       # competitor-intel (src/competitor_intel/)
├── infra/scripts/           # Dedupe, migration, deploy helpers
├── integrations/hermes/     # Thin client for Hermes agents
├── docs/                    # Handbook + architecture
├── pyproject.toml           # uv virtual workspace root
├── uv.lock                  # Locked Python dependencies
└── data/                    # SQLite, exports (gitignored)
```

## Toolchain

### Python — uv workspace

Root `pyproject.toml` defines a **virtual workspace** (`tool.uv.package = false`) with three installable members:

| Package | Path | Import surface |
|---------|------|----------------|
| `competitor-intel-core` | `packages/py-core` | `db`, `utils`, `alerts`, `ci_paths` |
| `competitor-intel-collectors` | `packages/py-collectors` | `collectors.*` |
| `competitor-intel` | `packages/py-enterprise` | `competitor_intel.*` |

```bash
uv sync                              # install all workspace packages + dev deps
uv run python apps/worker/daily_intel.py
uv run python apps/cli/run_intel.py
uv run competitor-intel collect -c rss
uv run pytest tests/
```

Path resolution for DB, exports, and reports: `ci_paths.py` (`CI_DB_PATH` override supported).

Worker/cli scripts call `ci_paths.ensure_app_paths()` so `automation` and sibling modules resolve without manual `PYTHONPATH`.

### JavaScript — Bun only

| App | Commands | Port |
|-----|----------|------|
| `apps/api` | `bun install`, `bun run dev`, `bun run build` | 3000 |
| `apps/dashboard` | `bun install`, `bun run dev`, `bun run check` | 5173 |

No npm/yarn/pnpm. Lockfiles: `apps/api/bun.lock`, `apps/dashboard/bun.lock`.

## Design principles

1. **Apps own entrypoints** — `daily_intel.py` under `apps/worker/`; HTTP under `apps/api/`.
2. **Packages own reusable code** — installed via uv workspace, not ad-hoc `PYTHONPATH`.
3. **One database file** — `data/competitor_intel.db` (or `CI_DB_PATH`).
4. **API-first integration** — Hermes calls HTTP or CLI, not cross-repo Python imports.
5. **Dual Python stacks (transitional)** — operational collectors + enterprise SQLAlchemy package.

## Root symlinks (legacy subprocess paths)

Orchestration still references repo-root paths for subprocess calls:

```
collectors   → packages/py-collectors/collectors
run_intel.py → apps/cli/run_intel.py
automation   → apps/worker/automation
```

Remove when `collector_registry.py` paths are fully monorepo-native.

## Makefile

```bash
make sync            # uv sync
make daily           # uv run daily_intel
make api-dev         # bun API
make dashboard-dev   # bun Vite
make compile         # compileall via uv
make test            # pytest via uv
```

## Related

- [HERMES_INTEGRATION.md](./HERMES_INTEGRATION.md)
- [PYTHON_VS_RUST.md](./PYTHON_VS_RUST.md)
