#!/usr/bin/env python3
import logging

from collectors.signal_processor_v2 import process_signals, run

logger = logging.getLogger("signal_processor")


def process_all_signals(batch_size: int = 100) -> dict:
    return process_signals(batch_size=batch_size)


def backfill_all_signals() -> dict:
    total = {"processed": 0, "created": 0, "skipped": 0, "by_type": {}}
    while True:
        batch = process_signals(batch_size=100)
        if batch["processed"] == 0:
            break
        total["processed"] += batch["processed"]
        total["created"] += batch["created"]
        total["skipped"] += batch["skipped"]
    logger.info(
        "Backfill complete: processed=%s created=%s skipped=%s",
        total["processed"],
        total["created"],
        total["skipped"],
    )
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backfill_all_signals()
