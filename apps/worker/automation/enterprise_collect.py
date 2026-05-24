#!/usr/bin/env python3
"""Opt-in SQLAlchemy RSS collect (shadow). Operational rss_collector remains canonical."""

import logging
import os
import subprocess
import sys
from pathlib import Path

from utils.enterprise_guard import assert_enterprise_sqlite_safe

logger = logging.getLogger("enterprise_collect")

BASE = Path(__file__).resolve().parents[3]
ENTERPRISE_SRC = BASE / "packages" / "py-enterprise" / "src"


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault(
        "PYTHONPATH",
        os.pathsep.join(
            [
                str(BASE / "packages" / "py-collectors"),
                str(BASE / "packages" / "py-core"),
                str(ENTERPRISE_SRC),
            ]
        ),
    )
    db_path = os.environ.get("CI_DB_PATH")
    if db_path:
        env["CI_DB_PATH"] = db_path
    return env


def run_enterprise_rss(dry_run: bool = False) -> int:
    if not dry_run:
        assert_enterprise_sqlite_safe(context="enterprise_collect")
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
    logger.info("CI_DB_PATH=%s", os.environ.get("CI_DB_PATH", "(default)"))
    result = subprocess.run(cmd, cwd=BASE, env=_child_env())
    return result.returncode


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    sys.exit(run_enterprise_rss("--dry-run" in sys.argv))
