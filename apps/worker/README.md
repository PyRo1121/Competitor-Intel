# Worker

Daily and frequent pipelines.

| Entry | Role |
|-------|------|
| `daily_intel.py` | **Canonical** daily orchestrator |
| `frequent_intel.py` | RSS / open-web tier |
| `automation/` | `collector_registry.py`, `parallel_collect.py` |

```bash
uv run python apps/worker/daily_intel.py
make daily
```

Do not add a second `daily_intel` under `automation/` — removed as duplicate.

Docs: [docs/PIPELINE.md](../../docs/PIPELINE.md) · [docs/ROADMAP.md](../../docs/ROADMAP.md)
