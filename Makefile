.PHONY: sync daily frequent grok-refresh api-dev dashboard-dev compile test lock export-reqs

ROOT := $(CURDIR)
export CI_DB_PATH ?= $(ROOT)/data/competitor_intel.db

sync:
	uv sync

lock:
	uv lock

daily:
	uv run python apps/worker/daily_intel.py

frequent:
	uv run python apps/worker/frequent_intel.py

grok-refresh:
	uv run python apps/worker/grok_refresh.py

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

compile:
	uv run python -m compileall -q packages apps/worker apps/cli tests

test:
	uv run pytest -q

test-cov:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run pytest tests/ -m "not enterprise" \
		--cov=db.migrations --cov=db.connection \
		--cov=collectors.signal_processor \
		--cov=collectors.signal_company_resolver \
		--cov=utils.http \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		--cov-config=pyproject.toml

test-all:
	uv run pytest tests/

reprocess-signals:
	uv run python scripts/reprocess_raw_signals.py --dry-run

phase-a-repair:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/phase_a_data_repair.py

phase-a-gate:
	PYTHONPATH=packages/py-core uv run python scripts/phase_a_quality_gate.py

phase-a-eval:
	PYTHONPATH=packages/py-collectors uv run python scripts/eval_golden_set.py

phase-a-all: phase-a-repair phase-a-gate test-cov phase-a-eval

phase-a-caveats: phase-a-repair relink-actionable enrich-queue-export

relink-actionable:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/relink_actionable_orphans.py

enrich-queue-export:
	PYTHONPATH=packages/py-core uv run python scripts/enrich_queue_export.py

export-x-queries:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/export_x_monitor_queries.py

grok-x-normalize:
	@test -n "$(INPUT)" || (echo "Usage: make grok-x-normalize INPUT=path/to/hermes_raw.json"; exit 1)
	uv run python scripts/grok_x_normalize.py "$(INPUT)" -o data/hermes_enrich/grok_x_results.json

grok-x-fetch:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_grok_x.py

grok-x-fetch-smoke:
	GROK_X_MAX_QUERIES=1 PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/fetch_grok_x.py --max-queries 1

grok-x-ingest:
	@test -f data/hermes_enrich/grok_x_results.json || (echo "Missing data/hermes_enrich/grok_x_results.json — run: make grok-x-fetch"; exit 1)
	GROK_X_RESULTS_PATH="$(CURDIR)/data/hermes_enrich/grok_x_results.json" \
	PYTHONPATH=packages/py-core:packages/py-collectors \
	uv run python packages/py-collectors/collectors/x_signal_collector.py
	GROK_X_RESULTS_PATH="$(CURDIR)/data/hermes_enrich/grok_x_results.json" \
	PYTHONPATH=packages/py-core:packages/py-collectors \
	uv run python packages/py-collectors/collectors/signal_url_fanout.py
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/phase_b_populate_funding.py

smoke-hermes-x:
	uv run python scripts/smoke_hermes_x_pipeline.py

enrich-queue-apply:
	PYTHONPATH=packages/py-core uv run python scripts/enrich_queue_apply.py

phase-b-funding:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/phase_b_populate_funding.py

phase-b-jobs:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/phase_b_populate_jobs.py

phase-b-company:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/phase_b_populate_company.py

phase-b-all: phase-b-funding phase-b-jobs phase-b-company

funding-enrich-export:
	PYTHONPATH=packages/py-core uv run python scripts/funding_enrich_export.py

funding-enrich-apply:
	PYTHONPATH=packages/py-core:packages/py-collectors uv run python scripts/funding_enrich_apply.py

migrate-db:
	uv run python -c "from db.schema import init_database; init_database()"

export-reqs:
	uv export --no-dev --format requirements-txt -o requirements.txt
