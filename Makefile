.PHONY: sync daily api-dev dashboard-dev compile test lock export-reqs

ROOT := $(CURDIR)
export CI_DB_PATH ?= $(ROOT)/data/competitor_intel.db

sync:
	uv sync

lock:
	uv lock

daily:
	uv run python apps/worker/daily_intel.py

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
	uv run pytest tests/

export-reqs:
	uv export --no-dev --format requirements-txt -o requirements.txt
