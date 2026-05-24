# Worker

| Script | Role |
|--------|------|
| `daily_intel.py` | **Canonical daily** — parallel ingest, `run_intel` schema gate, sequential rollups, brief export |
| `frequent_intel.py` | Hourly RSS/open-web tier |
| `grok_refresh.py` | Hermes Grok/X batch (separate cron) |
| `daily_brief.py` | Markdown brief generation |

Automation: `automation/collector_registry.py`, `parallel_collect.py`, `run_utils.py`.

```bash
make daily-prod
make grok-refresh
```
