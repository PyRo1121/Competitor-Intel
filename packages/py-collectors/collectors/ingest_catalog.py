"""Export data/ingest_catalog.json for status surfaces."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ci_paths import MONOREPO_ROOT

from collectors.sources_registry import catalog_summary, get_x_monitor_queries

# YouTube collector not on daily path yet; catalog reports 0 until wired.
YOUTUBE_CHANNELS: list[str] = []

DEFAULT_OUT = MONOREPO_ROOT / "data" / "ingest_catalog.json"


def write_ingest_catalog(out_path: Path | None = None) -> Path:
    path = out_path or DEFAULT_OUT
    summary = catalog_summary()
    payload = {
        "generated": date.today().isoformat(),
        "source": "collectors.ingest_catalog",
        "rssFeedsEnabled": summary["enabled"],
        "rssFeedsTotal": summary["total"],
        "rssFeedsDisabled": summary["disabled"],
        "xMonitorQueries": len(get_x_monitor_queries()),
        "youtubeChannels": len(YOUTUBE_CHANNELS),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    path = write_ingest_catalog()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
