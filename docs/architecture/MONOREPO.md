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
├── packages/                # Shared libraries
│   ├── py-collectors/       # Version A collectors (production)
│   ├── py-core/             # db/, utils/, alerts/, config/
│   └── py-enterprise/       # src/competitor_intel/ (SQLAlchemy)
├── infra/scripts/           # Dedupe, migration, deploy helpers
├── integrations/hermes/     # Thin client for Hermes agents
├── docs/                    # Handbook + architecture
└── data/                    # SQLite, exports (gitignored)
```

## Design principles

1. **Apps own entrypoints** — `daily_intel.py` lives under `apps/worker/`; HTTP server under `apps/api/`.
2. **Packages own reusable code** — collectors and DB access are importable without running a full app.
3. **One database file** — `CI_DB_PATH` defaults to `<repo>/data/competitor_intel.db`.
4. **API-first integration** — external systems (Hermes, cron, CI) call HTTP or CLI, not Python imports across repos.
5. **Dual Python stacks (transitional)** — operational `py-collectors` + enterprise `py-enterprise`; converge over time.

## PYTHONPATH (development)

Until packages are published as installable wheels with proper namespaces:

```bash
export PYTHONPATH="\
packages/py-collectors:\
packages/py-core:\
apps/worker:\
apps/cli:\
packages/py-enterprise/src"
```

Install enterprise package editable:

```bash
pip install -e ".[dev]"
```

Collectors import as flat modules (`from db.connection import get_conn`, `from collectors.rss_collector import ...`) matching the legacy layout.

### Root symlinks (legacy script paths)

Subprocess orchestration expects `collectors/` and `run_intel.py` at repo root:

```
collectors   → packages/py-collectors
run_intel.py → apps/cli/run_intel.py
automation     → apps/worker/automation
```

Remove symlinks once all script paths are updated to monorepo locations.

## Future: uv / hatch workspace

Root `pyproject.toml` documents the layout. A full `[tool.uv.workspace]` or hatch multi-package setup can split:

- `competitor-intel-core` → `packages/py-core`
- `competitor-intel-collectors` → `packages/py-collectors`
- `competitor-intel` → `packages/py-enterprise`

That refactor is deferred to avoid breaking imports during migration.

## TypeScript apps

| App | Package manager | Port |
|-----|-----------------|------|
| `apps/api` | Bun | 3000 |
| `apps/dashboard` | Bun | 5173 (Vite dev) |

API reads SQLite via `bun:sqlite`; path from `CI_DB_PATH` or monorepo `data/competitor_intel.db`.

## Tests

```bash
export PYTHONPATH=...  # as above
pytest tests/
```

## Related

- [HERMES_INTEGRATION.md](./HERMES_INTEGRATION.md)
- [PYTHON_VS_RUST.md](./PYTHON_VS_RUST.md)
