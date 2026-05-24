#!/usr/bin/env python3
"""
Hermes/Grok X smoke: real xAI x_search fetch → ingest → fanout → DB assert.

Uses Ollama only if you run a separate embed job — not part of this smoke.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys

from ci_paths import MONOREPO_ROOT

ROOT = MONOREPO_ROOT
ENRICH = ROOT / "data" / "hermes_enrich"
BATCH = ENRICH / "grok_x_results.json"


def _run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(cmd))
    env = {**os.environ, **kwargs.pop("env", {})}
    subprocess.run(cmd, check=True, cwd=ROOT, env=env, **kwargs)


def _count_x(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM raw_signals WHERE source='x'").fetchone()[0]


def main() -> int:
    os.chdir(ROOT)
    os.environ.setdefault("CI_DB_PATH", str(ROOT / "data" / "competitor_intel.db"))
    os.environ["GROK_X_MAX_QUERIES"] = "1"

    print("smoke-hermes-x: Hermes x_search (OAuth) → ingest → fanout")
    ENRICH.mkdir(parents=True, exist_ok=True)

    _run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "collectors.grok_x_export",
            "export",
            "--enriched",
        ],
        env={"PYTHONPATH": "packages/py-core:packages/py-collectors"},
    )

    _run(
        ["uv", "run", "python", "apps/worker/x_refresh/fetch.py", "--max-queries", "1"],
        env={
            "PYTHONPATH": "packages/py-core:packages/py-collectors",
            "GROK_X_MAX_QUERIES": "1",
            "XURL_MAX_QUERIES": "1",
        },
    )

    if not BATCH.is_file() or BATCH.stat().st_size < 50:
        print("FAIL: grok_x_results.json missing after fetch", file=sys.stderr)
        return 1

    db = os.environ["CI_DB_PATH"]
    before = _count_x(sqlite3.connect(db))

    os.environ["GROK_X_RESULTS_PATH"] = str(BATCH)
    os.environ["CI_REQUIRE_GROK_X"] = "1"
    _run(
        ["uv", "run", "python", "packages/py-collectors/collectors/x_signal_collector.py"],
        env={
            "PYTHONPATH": "packages/py-core:packages/py-collectors",
            "GROK_X_RESULTS_PATH": str(BATCH),
            "CI_REQUIRE_GROK_X": "1",
        },
    )

    after_ingest = _count_x(sqlite3.connect(db))
    if after_ingest <= before:
        print(
            f"FAIL: x signal count did not increase ({before} -> {after_ingest}). "
            "Grok returned no new posts or dedup swallowed them.",
            file=sys.stderr,
        )
        return 1
    print(f"OK: x signals {before} -> {after_ingest}")

    _run(
        ["uv", "run", "python", "packages/py-collectors/collectors/signal_url_fanout.py"],
        env={"PYTHONPATH": "packages/py-core:packages/py-collectors"},
    )

    batch = json.loads(BATCH.read_text(encoding="utf-8"))
    post_id = None
    if batch and batch[0].get("results"):
        post_id = batch[0]["results"][0].get("post_id")

    conn = sqlite3.connect(db)
    if post_id:
        row = conn.execute(
            "SELECT id FROM raw_signals WHERE source='x' AND data_json LIKE ?",
            (f"%{post_id}%",),
        ).fetchone()
        if not row:
            print(f"FAIL: post_id {post_id} not in DB", file=sys.stderr)
            return 1
        print(f"OK: verified post_id={post_id} raw_signal id={row[0]}")
    articles = conn.execute("SELECT COUNT(*) FROM raw_signals WHERE source='article'").fetchone()[0]
    print(f"OK: x_total={after_ingest} articles={articles}")
    print("smoke-hermes-x: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"FAIL: command exited {exc.returncode}", file=sys.stderr)
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
