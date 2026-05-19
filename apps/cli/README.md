# CLI app

Operational command-line scripts migrated from the Hermes agent root.

| Script | Role |
|--------|------|
| `intel.py` | Interactive intel queries |
| `run_intel.py` | Signal processor driver |
| `query.py` | DB queries |
| `sources.py` | Source registry helpers |
| `retrieval.py` | RAG retrieval |

Install enterprise CLI via root package:

```bash
pip install -e .
competitor-intel --help
```
