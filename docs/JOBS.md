# Jobs intelligence — granular hiring model

**Status:** operational collectors  
**Pipeline:** `collectors/job_tracker.py` → `collectors/job_rollup.py` — see [PIPELINE.md](PIPELINE.md)

## Data model

```
ATS APIs (Greenhouse / Lever / Ashby) + Hiring intelligence_events
        ↓
job_posting_claims          ← one row per source_url (title, comp, seniority, skills JSON)
        ↓
job_posting_skills          ← parsed tech per claim or canonical posting
        ↓
job_postings                ← canonical opening (cluster_key, corroboration, provenance)
        ↓
company_job_boards          ← verified ATS slug per company
job_velocity_snapshots      ← daily active_openings / new_30d rollups
```

### `job_posting_claims` (per outlet)

| Column | Purpose |
|--------|---------|
| `source_url` | Unique key |
| `ats_platform` | greenhouse, lever, ashby, company_careers, press_mention |
| `external_id` | ATS posting id |
| `seniority_band` | intern → executive |
| `employment_type` | full_time, contract, internship, part_time |
| `remote_policy` | remote, hybrid, onsite |
| `salary_min_usd` / `salary_max_usd` | Parsed compensation |
| `tech_stack_json` | Detected skills from title + description |
| `source_tier` / `source_weight` | Trust (company board = highest) |

### `job_postings` (canonical)

| Column | Purpose |
|--------|---------|
| `cluster_key` | `company:ats:external_id` or title+location fingerprint |
| `corroboration_score` | Multi-source agreement |
| `fields_provenance` | JSON per-field values + reporting URLs + skill mention counts |
| `report_count` | Claims merged into this opening |

## Commands

```bash
export CI_DB_PATH="$PWD/data/competitor_intel.db"
make job-rollup
# Limit scan for smoke:
CI_JOB_COMPANY_LIMIT=25 make job-rollup
```

## API

| Endpoint | Returns |
|----------|---------|
| `GET /api/jobs` | Active postings + aggregate stats |
| `GET /api/jobs/claims` | Per-source claims + skills |
| `GET /api/jobs/postings/:id` | Canonical posting + claims + skills + provenance |
| `GET /api/jobs/company/:id` | Postings, boards, velocity, skill mix |
| `GET /api/jobs/trends` | Hiring velocity by company |

## Code

- `collectors/jobs/ats_clients.py` — Greenhouse, Lever, Ashby fetch + slug probing
- `collectors/jobs/job_parser.py` — seniority, salary, remote, tech extraction
- `collectors/jobs/job_enricher.py` — claims + skills persistence
- `collectors/jobs/job_aggregator.py` — merge claims → postings
- `collectors/jobs/job_pipeline.py` — orchestration
