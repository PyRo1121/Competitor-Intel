#!/usr/bin/env python3
"""SQLite health: pragmas, WAL size, checkpoint, optional ANALYZE/backup."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "py-core"))

from db.connection import active_db_path, connection_info, get_conn  # noqa: E402
from db.sqlite_tuning import read_pragma_snapshot, wal_checkpoint, wal_status  # noqa: E402


def _backup_db(dest: Path) -> Path:
    """Online backup via SQLite backup API (safe under WAL)."""
    import sqlite3

    src = active_db_path()
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

    info = connection_info()
    print(f"Database: {info.get('path', path)}")
    for key in sorted(info):
        if key != "path":
            print(f"  {key}: {info[key]}")

    conn = get_conn(profile="maintenance")
    try:
        snap = read_pragma_snapshot(conn)
        print("\nPRAGMA snapshot:")
        for k, v in snap.items():
            print(f"  {k}: {v}")

        wal = wal_status(conn)
        if wal:
            print("\nWAL checkpoint (PASSIVE):")
            for k, v in wal.items():
                print(f"  {k}: {v}")
            busy = int(wal.get("wal_checkpoint_busy", "0"))
            log_frames = int(wal.get("wal_log_frames", "0"))
            if busy and log_frames:
                print(
                    "\nWARN: WAL checkpoint blocked by readers — "
                    "long API reads can starve checkpoint",
                    file=sys.stderr,
                )

        if args.checkpoint:
            mode, log_frames, ckpt_frames = wal_checkpoint(conn, args.checkpoint)
            conn.commit()
            print(f"\nwal_checkpoint({mode}): log={log_frames} checkpointed={ckpt_frames}")

        if args.analyze:
            conn.execute("ANALYZE")
            conn.commit()
            print("\nANALYZE completed")

        if args.backup is not None:
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            dest = (
                Path(args.backup)
                if args.backup
                else ROOT / "data" / "backups" / f"competitor_intel-{stamp}.db"
            )
            out = _backup_db(dest)
            print(f"\nBackup written: {out} ({out.stat().st_size} bytes)")
    finally:
        conn.close()

    jm = info.get("journal_mode", "").lower()
    if jm != "wal":
        print("\nWARN: journal_mode is not WAL — parallel ingest will suffer", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
