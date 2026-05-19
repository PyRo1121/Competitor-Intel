#!/usr/bin/env python3
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("enterprise_collect")

BASE = Path(__file__).resolve().parents[3]


def run_enterprise_rss(dry_run: bool = False) -> int:
    cmd = [
        sys.executable,
        "-m",
        "competitor_intel.cli",
        "collect",
        "-c",
        "rss",
    ]
    if dry_run:
        cmd.append("--dry-run")
    logger.info("Enterprise collect: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=BASE)
    return result.returncode


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(run_enterprise_rss("--dry-run" in sys.argv))
