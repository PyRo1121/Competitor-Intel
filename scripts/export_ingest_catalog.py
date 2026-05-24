#!/usr/bin/env python3
"""Write data/ingest_catalog.json for API /api/status (Track 2 P2-3)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-collectors"))

from collectors.sources_registry import catalog_summary, get_x_monitor_queries  # noqa: E402
from collectors.youtube_collector import YOUTUBE_CHANNELS  # noqa: E402

OUT = ROOT / "data" / "ingest_catalog.json"


def main() -> int:
    summary = catalog_summary()
    payload = {
        "generated": date.today().isoformat(),
        "source": "scripts/export_ingest_catalog.py",
        "rssFeedsEnabled": summary["enabled"],
        "rssFeedsTotal": summary["total"],
        "rssFeedsDisabled": summary["disabled"],
        "xMonitorQueries": len(get_x_monitor_queries()),
        "youtubeChannels": len(YOUTUBE_CHANNELS),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
