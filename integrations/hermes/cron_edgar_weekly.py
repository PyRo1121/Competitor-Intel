#!/usr/bin/env python3
"""Hermes cron (--no-agent): SEC Form D bulk ingest. See docs/SCHEDULING.md."""

from __future__ import annotations

from cron_runner import run_job


def main() -> int:
    return run_job("edgar-weekly")


if __name__ == "__main__":
    raise SystemExit(main())
