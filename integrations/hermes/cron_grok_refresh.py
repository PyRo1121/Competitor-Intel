#!/usr/bin/env python3
"""Hermes cron (--no-agent): Grok/X refresh batch. See docs/SCHEDULING.md."""

from __future__ import annotations

from cron_runner import run_job


def main() -> int:
    return run_job("grok-refresh")


if __name__ == "__main__":
    raise SystemExit(main())
