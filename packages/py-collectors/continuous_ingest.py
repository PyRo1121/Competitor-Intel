"""
Continuous / Near Real-Time Ingest
Lightweight collector designed to run frequently (every 30-60 min).
Delegates to automation/continuous_ingest.py for consistent timing/logging.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("continuous_ingest")


def run_continuous_ingest() -> tuple[int, int]:
    from automation.continuous_ingest import run_continuous_ingest as _run

    return _run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ok, total = run_continuous_ingest()
    sys.exit(0 if ok == total else 1)
