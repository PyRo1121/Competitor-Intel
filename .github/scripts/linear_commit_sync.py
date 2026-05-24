#!/usr/bin/env python3
"""CI shim — implementation: integrations/linear/commit_sync.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))
sys.path.insert(0, str(ROOT))

from integrations.linear.commit_sync import main

if __name__ == "__main__":
    raise SystemExit(main())
