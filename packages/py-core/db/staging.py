"""JSONL staging for collector ingest — parallel fetch, single merge writer."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ci_paths import MONOREPO_ROOT

from db.ingest import url_dedup_key


def ingest_staging_active() -> bool:
    """True only for parallel collector subprocesses (slot + run id set)."""
    if os.environ.get("CI_INGEST_STAGING", "").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return False
    if not os.environ.get("CI_STAGING_RUN_ID", "").strip():
        return False
    return bool(os.environ.get("CI_STAGING_SLOT", "").strip())


def staging_run_id() -> str:
    rid = os.environ.get("CI_STAGING_RUN_ID", "").strip()
    if not rid:
        raise RuntimeError("CI_STAGING_RUN_ID is required when CI_INGEST_STAGING=1")
    return rid


def staging_slot() -> str:
    return os.environ.get("CI_STAGING_SLOT", "default").strip() or "default"


def staging_run_dir(run_id: str | None = None) -> Path:
    rid = run_id or staging_run_id()
    path = MONOREPO_ROOT / "data" / "staging" / "raw_signals" / rid
    path.mkdir(parents=True, exist_ok=True)
    return path


def staging_file_path(run_id: str | None = None, slot: str | None = None) -> Path:
    return staging_run_dir(run_id) / f"{slot or staging_slot()}.jsonl"


def stage_raw_signal(
    source: str,
    url: str,
    data: dict[str, Any],
    company_id: int | None = None,
    detected_at: str | None = None,
    dedup_key: str | None = None,
) -> bool:
    """Append one signal row to per-collector JSONL (dedup at merge via INSERT OR IGNORE)."""
    if not url and not dedup_key:
        return False
    key = dedup_key or url_dedup_key(url)
    payload = dict(data)
    payload.setdefault("url", url)
    payload.setdefault("link", url)
    record = {
        "source": source,
        "url": url,
        "company_id": company_id,
        "detected_at": detected_at,
        "dedup_key": key,
        "data": payload,
    }
    path = staging_file_path()
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return True


def list_staging_files(run_id: str) -> list[Path]:
    run_dir = staging_run_dir(run_id)
    if not run_dir.is_dir():
        return []
    return sorted(run_dir.glob("*.jsonl"))


def iter_staged_records(run_id: str):
    for path in list_staging_files(run_id):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def clear_staging_run(run_id: str) -> None:
    run_dir = staging_run_dir(run_id)
    for path in run_dir.glob("*.jsonl"):
        path.unlink(missing_ok=True)
    try:
        run_dir.rmdir()
    except OSError:
        pass


def merge_staged_run(run_id: str) -> dict[str, int]:
    """Merge staged JSONL into raw_signals (single writer_lock + batch insert)."""
    from db.batch import RawSignalBatchWriter
    from db.writer_lock import writer_lock

    paths = list_staging_files(run_id)
    if not paths:
        return {"files": 0, "rows": 0, "inserted": 0}

    rows = 0
    inserted = 0
    commit_every = max(100, int(os.environ.get("CI_SQLITE_BATCH_COMMIT", "500")))

    with writer_lock():
        with RawSignalBatchWriter(
            commit_every=commit_every,
            profile="ingest_bulk",
            use_writer_lock=False,
        ) as batch:
            for record in iter_staged_records(run_id):
                rows += 1
                if batch.insert(
                    record["source"],
                    record.get("url") or "",
                    record["data"],
                    company_id=record.get("company_id"),
                    detected_at=record.get("detected_at"),
                    dedup_key=record.get("dedup_key"),
                ):
                    inserted += 1

    return {"files": len(paths), "rows": rows, "inserted": inserted}


# Back-compat alias used by ingest_staging CLI
merge_staging_run = merge_staged_run
