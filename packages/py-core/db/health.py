"""SQLite health: pragmas, WAL size, checkpoint, ANALYZE, online backup."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ci_paths import MONOREPO_ROOT

from db.connection import active_db_path, connection_info, get_conn
from db.sqlite_tuning import read_pragma_snapshot, wal_checkpoint, wal_status


def read_health() -> dict[str, Any]:
    """Snapshot connection info, PRAGMAs, and passive WAL checkpoint stats."""
    path = active_db_path()
    info = connection_info()
    conn = get_conn(profile="maintenance")
    try:
        pragma = read_pragma_snapshot(conn)
        wal = wal_status(conn)
    finally:
        conn.close()
    return {
        "path": path,
        "connection_info": info,
        "pragma": pragma,
        "wal": wal,
    }


def checkpoint(mode: str) -> tuple[str, int, int]:
    """Run WAL checkpoint; returns (mode, log_frames, checkpointed_frames)."""
    conn = get_conn(profile="maintenance")
    try:
        result = wal_checkpoint(conn, mode)
        conn.commit()
        return result
    finally:
        conn.close()


def backup_db(dest: Path | None = None) -> Path:
    """Online backup via SQLite backup API (safe under WAL)."""
    src = active_db_path()
    if dest is None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        dest = MONOREPO_ROOT / "data" / "backups" / f"competitor_intel-{stamp}.db"
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src), timeout=120)
    dst_conn = sqlite3.connect(str(dest), timeout=120)
    try:
        src_conn.backup(dst_conn)
        dst_conn.commit()
    finally:
        dst_conn.close()
        src_conn.close()
    return dest


def _print_health(data: dict[str, Any]) -> None:
    path = data["path"]
    info = data["connection_info"]
    print(f"Database: {info.get('path', path)}")
    for key in sorted(info):
        if key != "path":
            print(f"  {key}: {info[key]}")

    print("\nPRAGMA snapshot:")
    for k, v in data["pragma"].items():
        print(f"  {k}: {v}")

    wal = data.get("wal") or {}
    if wal:
        print("\nWAL checkpoint (PASSIVE):")
        for k, v in wal.items():
            print(f"  {k}: {v}")
        busy = int(wal.get("wal_checkpoint_busy", "0"))
        log_frames = int(wal.get("wal_log_frames", "0"))
        if busy and log_frames:
            print(
                "\nWARN: WAL checkpoint blocked by readers — long API reads can starve checkpoint",
                file=sys.stderr,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite operational health")
    parser.add_argument(
        "--checkpoint",
        choices=("PASSIVE", "FULL", "RESTART", "TRUNCATE"),
        help="Run WAL checkpoint after reporting",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run ANALYZE (update query planner stats)",
    )
    parser.add_argument(
        "--backup",
        metavar="PATH",
        nargs="?",
        const="",
        help="Copy DB via backup API (default: data/backups/competitor_intel-UTC.db)",
    )
    args = parser.parse_args()

    path = active_db_path()
    if not path.is_file():
        print(f"ERROR: database not found: {path}", file=sys.stderr)
        return 1

    data = read_health()
    _print_health(data)
    info = data["connection_info"]

    conn = get_conn(profile="maintenance")
    try:
        if args.checkpoint:
            mode, log_frames, ckpt_frames = checkpoint(args.checkpoint)
            print(f"\nwal_checkpoint({mode}): log={log_frames} checkpointed={ckpt_frames}")

        if args.analyze:
            conn.execute("ANALYZE")
            conn.commit()
            print("\nANALYZE completed")

        if args.backup is not None:
            dest = Path(args.backup) if args.backup else None
            out = backup_db(dest)
            print(f"\nBackup written: {out} ({out.stat().st_size} bytes)")
    finally:
        conn.close()

    jm = str(info.get("journal_mode", "")).lower()
    if jm != "wal":
        print("\nWARN: journal_mode is not WAL — parallel ingest will suffer", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
