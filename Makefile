.PHONY: sync daily frequent grok-refresh full-sweep export-x-queries export-x-queries-enriched api-dev dashboard-dev compile test lock export-reqs lint lint-py lint-py-fix lint-js lint-js-fix health-check track3-verify

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

supply-chain-api:
	cd apps/api && bun install --frozen-lockfile && bun audit

supply-chain-dashboard:
	cd apps/dashboard && bun install --frozen-lockfile && bun audit

supply-chain: supply-chain-py supply-chain-api supply-chain-dashboard

# Phase A: tiered daily (no inline Grok — use `make grok-refresh` on its cron)
daily:
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py

# Production cron: tiered daily + strict funding path + dedup index required at init
daily-prod:
	CI_SKIP_GROK_X=1 CI_STRICT_PIPELINE=1 CI_REQUIRE_DEDUP_INDEX=1 uv run python apps/worker/daily_intel.py

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
	uv run python scripts/export_x_monitor_queries.py --enriched
	CI_X_PROVIDER=grok CI_X_QUERY_AI_EXPAND=1 GROK_X_MAX_QUERIES=18 $(MAKE) grok-refresh
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/funding_rollup.py

# Static registry queries only (grok cron before daily has run).
export-x-queries:
	uv run python scripts/export_x_monitor_queries.py --baseline-only

export-x-queries-enriched:
	uv run python scripts/export_x_monitor_queries.py --enriched

daily-tiered:
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py

intel:
	uv run python apps/cli/run_intel.py

cli:
	uv run python apps/cli/intel.py $(ARGS)

api-dev:
	cd apps/api && bun run dev

api-build:
	cd apps/api && bun run build

dashboard-dev:
	cd apps/dashboard && bun run dev

dashboard-check:
	cd apps/dashboard && bun run check

dashboard-test:
	cd apps/dashboard && bun run test:unit

seed-ci-e2e:
	@test -n "$(CI_DB_PATH)" || export CI_DB_PATH="$(CURDIR)/data/ci_test.db"; \
	PYTHONPATH=packages/py-core uv run python scripts/migrate_ci_db.py; \
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/seed_ci_e2e.py

dashboard-e2e: test-api seed-ci-e2e
	cd apps/dashboard && CI=true bun run test:e2e

compile:
	uv run python -m compileall -q packages apps/worker apps/cli tests

test:
	uv run pytest -q

test-cov:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run pytest tests/ -m "not enterprise" \
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
	uv run python scripts/reprocess_raw_signals.py --dry-run

intel-repair:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/signal_repair.py

migrate-dedup:
	uv run python packages/py-core/db/migrate_dedup.py

sqlite-health:
	uv run python scripts/sqlite_health.py

sqlite-checkpoint:
	uv run python scripts/sqlite_health.py --checkpoint TRUNCATE

sqlite-backup:
	uv run python scripts/sqlite_health.py --backup

intel-gate:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python packages/py-collectors/collectors/intel_quality_gate.py

phase-a-repair: intel-repair

phase-a-gate: intel-gate

golden-eval:
	PYTHONPATH=packages/py-collectors uv run python scripts/eval_golden_set.py

test-api:
	@test -n "$(CI_DB_PATH)" || export CI_DB_PATH="$(CURDIR)/data/ci_test.db"; \
	CI_SQLITE_BUSY_TIMEOUT_MS=60000 PYTHONPATH=packages/py-core uv run python scripts/migrate_ci_db.py; \
	cd apps/api && CI_DB_PATH="$$CI_DB_PATH" bun test

export-ingest-catalog:
	PYTHONPATH=packages/py-collectors uv run python scripts/export_ingest_catalog.py

enterprise-check: compile test-cov intel-gate golden-eval test-api dashboard-check

track2-verify: enterprise-check claims-audit-strict

# --- Lint (Track 3 tooling; CI wiring optional) ---
PY_LINT_PATHS := packages apps/worker apps/cli tests scripts

lint-py:
	uv run ruff check $(PY_LINT_PATHS)
	uv run ruff format --check $(PY_LINT_PATHS)
	uv run ty check

lint-py-fix:
	uv run ruff check --fix $(PY_LINT_PATHS)
	uv run ruff format $(PY_LINT_PATHS)

lint-js:
	bun run fmt:check
	bun run lint:js

lint-js-fix:
	bun run fmt
	bun run lint:js:fix

lint: lint-py lint-js dashboard-check

# Bare-metal ops health (P3-7 — API must be listening on CI_API_URL).
health-check:
	bash scripts/healthcheck.sh

track3-verify: lint test-cov golden-eval test-api

intel-all: intel-repair intel-gate test-cov golden-eval

phase-a-eval: golden-eval

phase-a-all: intel-all

phase-a-caveats: intel-repair relink-actionable enrich-queue-export

relink-actionable:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/relink_actionable_orphans.py

enrich-queue-export:
	PYTHONPATH=packages/py-core uv run python scripts/enrich_queue_export.py

grok-x-normalize:
	@test -n "$(INPUT)" || (echo "Usage: make grok-x-normalize INPUT=path/to/hermes_raw.json"; exit 1)
	uv run python scripts/grok_x_normalize.py "$(INPUT)" -o data/hermes_enrich/grok_x_results.json

grok-x-fetch:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_x.py

grok-x-fetch-smoke:
	GROK_X_MAX_QUERIES=1 PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_x.py --max-queries 1

x-check:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_xurl.py --check

x-fetch:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_xurl.py

x-fetch-smoke:
	XURL_MAX_QUERIES=1 PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_xurl.py --max-queries 1

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
	uv run python scripts/smoke_hermes_x_pipeline.py

enrich-queue-apply:
	PYTHONPATH=packages/py-core uv run python scripts/enrich_queue_apply.py

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
	CI_DB_PATH="$(CI_DB_PATH)" PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/claims_audit.py

claims-audit-strict:
	CI_CLAIMS_AUDIT_STRICT=1 CI_DB_PATH="$(CI_DB_PATH)" PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/claims_audit.py

# Shadow SQLAlchemy RSS (operational rss_collector is canonical). Dry-run by default.
enterprise-rss:
	PYTHONPATH=packages/py-core:packages/py-collectors:packages/py-enterprise/src \
	uv run python apps/worker/automation/enterprise_collect.py --dry-run

enterprise-rss-live:
	@echo "Requires CI_DB_PATH on a copy or CI_ENTERPRISE_ALLOW_PROD=1 (see docs/ENTERPRISE_FREEZE.md)"
	PYTHONPATH=packages/py-core:packages/py-collectors:packages/py-enterprise/src \
	uv run python apps/worker/automation/enterprise_collect.py

daily-deep:
	CI_SKIP_GROK_X=1 uv run python apps/worker/daily_intel.py

phase-b-audit: claims-audit

funding-enrich-export:
	PYTHONPATH=packages/py-core uv run python scripts/funding_enrich_export.py

funding-enrich-apply:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/funding_enrich_apply.py

company-enrich-export:
	PYTHONPATH=packages/py-core uv run python scripts/company_enrich_export.py

company-enrich-apply:
	PYTHONPATH=packages/py-core uv run python scripts/company_enrich_apply.py

# Export Hermes queues (run agent on data/hermes_enrich/*.jsonl), then apply results.
enrich-all-export: enrich-queue-export funding-enrich-export company-enrich-export
	@echo "Next: run Hermes on data/hermes_enrich/*_queue.jsonl — then: make enrich-all-apply"

enrich-all-apply: enrich-queue-apply funding-enrich-apply company-enrich-apply

enrich-all: enrich-all-export

migrate-db:
	uv run python -c "from db.schema import init_database; init_database()"

export-reqs:
	uv export --no-dev --format requirements-txt -o requirements.txt
