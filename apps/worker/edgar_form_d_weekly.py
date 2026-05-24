#!/usr/bin/env python3
"""Weekly SEC Form D quarterly ZIP ingest (private fundraising). See docs/PIPELINE.md."""

from __future__ import annotations

import logging
import os

from ci_paths import ensure_app_paths

ensure_app_paths()

from automation.run_utils import configure_logging, run_script

logger = logging.getLogger("edgar_form_d_weekly")


def main() -> int:
    os.environ["EDGAR_FORM_D_BULK"] = "1"
    logger.info("=== SEC Form D bulk ingest (weekly) ===")
    ok, elapsed = run_script("collectors/edgar_collector.py", logger=logger)
    if ok:
        logger.info("Form D bulk finished in %.1fs", elapsed)
        return 0
    logger.error("Form D bulk failed (exit != 0, %.1fs)", elapsed)
    return 1


if __name__ == "__main__":
    configure_logging(logger)
    raise SystemExit(main())
