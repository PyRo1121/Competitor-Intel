#!/usr/bin/env python3
"""Hermes cron (--no-agent): frequent RSS/open-web tier. See docs/SCHEDULING.md."""

from __future__ import annotations

from cron_runner import run_job


def main() -> int:
    return run_job("frequent")


if __name__ == "__main__":
    raise SystemExit(main())
