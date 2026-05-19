#!/usr/bin/env python3
import logging

from collectors.multi_source_collector import run as _run_multi_source

logger = logging.getLogger(__name__)


def run() -> int:
    logger.info("enhanced_signal_collector delegates to multi_source_collector")
    return _run_multi_source()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
