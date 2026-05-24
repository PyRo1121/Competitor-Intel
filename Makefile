.PHONY: sync daily daily-prod edgar-form-d-weekly frequent grok-refresh full-sweep export-x-queries export-x-queries-enriched compile test lock export-reqs lint lint-py lint-py-fix health-check verify verify-dry-run track2-verify

ROOT := $(CURDIR)
export CI_DB_PATH ?= $(ROOT)/data/competitor_intel.db

sync:
	uv sync

lock:
	uv lock

lock-check:
	uv lock --check

# 6-F01: lockfile + pip-audit. Ollama PYSEC advisories have no fix release yet (optional embed dep).
supply-chain-py: lock-check
	uv run pip-audit \
		--ignore-vuln PYSEC-2025-146 \
		--ignore-vuln PYSEC-2025-144 \
		--ignore-vuln PYSEC-2025-147 \
		--ignore-vuln PYSEC-2025-145 \
		--ignore-vuln PYSEC-2026-102 \
		--ignore-vuln PYSEC-2026-101

supply-chain: supply-chain-py

# Phase A: tiered daily (no inline Grok — use `make grok-refresh` on its cron)
daily:
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py

# Production cron: tiered daily + strict funding path + dedup index required at init
daily-prod:
	CI_SKIP_GROK_X=1 CI_STRICT_PIPELINE=1 CI_REQUIRE_DEDUP_INDEX=1 uv run python apps/worker/daily_intel.py

# SEC Form D quarterly ZIP (private rounds); not on daily — avoids SQLite writer fights
edgar-form-d-weekly:
	EDGAR_FORM_D_BULK=1 uv run python apps/worker/edgar_form_d_weekly.py

daily-with-grok:
	uv run python apps/worker/daily_intel.py

frequent:
	uv run python apps/worker/frequent_intel.py

grok-refresh:
	uv run python apps/worker/grok_refresh.py

# On-demand: full daily first (labels/claims), then enriched X search, then rollups for new X posts.
# CI_X_QUERY_AI_EXPAND=1 adds Hermes/xAI-generated queries on top of DB-derived ones.
full-sweep:
	@echo "=== Full sweep: daily (no X) → enriched X queries → grok-refresh → funding rollup ==="
	CI_COMPANY_DATA_ROLLUP=1 CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py
	uv run python -m collectors.grok_x_export export --enriched
	CI_X_PROVIDER=grok CI_X_QUERY_AI_EXPAND=1 GROK_X_MAX_QUERIES=18 $(MAKE) grok-refresh
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/funding_rollup.py

# Static registry queries only (grok cron before daily has run).
export-x-queries:
	uv run python -m collectors.grok_x_export export --baseline-only

export-x-queries-enriched:
	uv run python -m collectors.grok_x_export export --enriched

daily-tiered:
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py

intel:
	uv run python apps/cli/run_intel.py

cli:
	uv run python apps/cli/intel.py $(ARGS)

compile:
	uv run python -m compileall -q packages apps/worker apps/cli tests

test:
	uv run pytest -q

test-cov:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run pytest tests/ \
		--cov=db.migrations --cov=db.connection \
		--cov=collectors.signal_processor \
		--cov=collectors.signal_company_resolver \
		--cov=collectors.signal_repair \
		--cov=collectors.intel_quality_gate \
		--cov=collectors.funding_rollup \
		--cov=utils.http \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		--cov-config=pyproject.toml

test-all:
	uv run pytest tests/

reprocess-signals:
	uv run python -m db.reprocess --dry-run

intel-repair:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/signal_repair.py

migrate-dedup:
	uv run python packages/py-core/db/migrate_dedup.py

sqlite-health:
	uv run python -m db.health

sqlite-checkpoint:
	uv run python -m db.health --checkpoint TRUNCATE

sqlite-backup:
	uv run python -m db.health --backup

intel-gate:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/intel_quality_gate.py

phase-a-repair: intel-repair

phase-a-gate: intel-gate

golden-eval:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python tests/tools/golden_eval.py

export-ingest-catalog:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python -m collectors.ingest_catalog

# Production verification bar (see docs/PIPELINE.md, docs/ENGINEERING.md)
verify: compile test-cov intel-gate golden-eval claims-audit-strict

CI_DB_PATH ?= $(ROOT)/data/ci_test.db

migrate-db-ci:
	CI_DB_PATH="$(CI_DB_PATH)" uv run python -c "from db.schema import init_database; init_database()"

daily-dry-run-ci:
	CI_SKIP_GROK_X=1 CI_DB_PATH="$(CI_DB_PATH)" uv run python apps/worker/daily_intel.py --dry-run

ci: lock-check supply-chain-py lint-py migrate-db-ci compile
	CI_DB_PATH="$(CI_DB_PATH)" $(MAKE) test-cov intel-gate golden-eval claims-audit-strict
	$(MAKE) daily-dry-run-ci CI_DB_PATH="$(CI_DB_PATH)"

verify-dry-run: verify
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py --dry-run

track2-verify: verify

# --- Lint (Track 3 tooling; CI wiring optional) ---
PY_LINT_PATHS := packages apps/worker apps/cli tests scripts

lint-py:
	uv run ruff check $(PY_LINT_PATHS)
	uv run ruff format --check $(PY_LINT_PATHS)
	uv run ty check

lint-py-fix:
	uv run ruff check --fix $(PY_LINT_PATHS)
	uv run ruff format $(PY_LINT_PATHS)

lint: lint-py

# Bare-metal ops health (SQLite; optional CI_HEALTH_REQUIRE_API=1 for legacy API URL).
health-check:
	PYTHONPATH=packages/py-core:packages/py-collectors:apps/cli uv run python apps/cli/healthcheck.py

track3-verify: lint test-cov golden-eval

intel-all: intel-repair intel-gate test-cov golden-eval

phase-a-eval: golden-eval

phase-a-all: intel-all

phase-a-caveats: intel-repair relink-actionable

relink-actionable:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/signal_repair.py actionable

grok-x-normalize:
	@test -n "$(INPUT)" || (echo "Usage: make grok-x-normalize INPUT=path/to/hermes_raw.json"; exit 1)
	uv run python -m collectors.grok_x_export normalize "$(INPUT)" -o data/hermes_enrich/grok_x_results.json

grok-x-fetch:
	uv run python apps/worker/x_refresh/fetch.py

grok-x-fetch-smoke:
	GROK_X_MAX_QUERIES=1 uv run python apps/worker/x_refresh/fetch.py --max-queries 1

x-check:
	uv run python apps/worker/x_refresh/fetch_xurl.py --check

x-fetch:
	uv run python apps/worker/x_refresh/fetch_xurl.py

x-fetch-smoke:
	XURL_MAX_QUERIES=1 uv run python apps/worker/x_refresh/fetch_xurl.py --max-queries 1

grok-x-ingest:
	@test -f data/hermes_enrich/grok_x_results.json || (echo "Missing data/hermes_enrich/grok_x_results.json — run: make grok-x-fetch"; exit 1)
	GROK_X_RESULTS_PATH="$(CURDIR)/data/hermes_enrich/grok_x_results.json" \
	PYTHONPATH=packages/py-core:packages/py-collectors \
	uv run python packages/py-collectors/collectors/x_signal_collector.py
	GROK_X_RESULTS_PATH="$(CURDIR)/data/hermes_enrich/grok_x_results.json" \
	PYTHONPATH=packages/py-core:packages/py-collectors \
	uv run python packages/py-collectors/collectors/signal_url_fanout.py
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/funding_rollup.py

smoke-hermes-x:
	uv run python tests/integration/smoke_hermes_x_pipeline.py

funding-rollup:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/funding_rollup.py

job-rollup:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/job_rollup.py

company-data-rollup:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/company_data_rollup.py

regulatory-license-rollup:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/regulatory_license_rollup.py

cap-table-rollup:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/cap_table_rollup.py

rollup-all: funding-rollup job-rollup regulatory-license-rollup cap-table-rollup company-data-rollup

phase-b-funding: funding-rollup

phase-b-jobs: job-rollup

phase-b-company: company-data-rollup

phase-b-all: rollup-all

claims-audit:
	CI_DB_PATH="$(CI_DB_PATH)" uv run python -m db.claims_audit

claims-audit-strict:
	CI_CLAIMS_AUDIT_STRICT=1 CI_DB_PATH="$(CI_DB_PATH)" uv run python -m db.claims_audit

daily-deep:
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py

phase-b-audit: claims-audit

migrate-db:
	uv run python -c "from db.schema import init_database; init_database()"

export-reqs:
	uv export --no-dev --format requirements-txt -o requirements.txt

# Linear: dry-run commit sync (needs LINEAR_API_KEY in env). See docs/LINEAR.md
linear-sync-dry:
	@test -n "$$LINEAR_API_KEY" || (echo "Set LINEAR_API_KEY"; exit 1)
	uv run python .github/scripts/linear_commit_sync.py --dry-run --message "fixes COM-5"

linear-sync-test:
	uv run pytest tests/test_linear_commit_sync.py -q
