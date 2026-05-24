#!/usr/bin/env python3
"""Evaluate classifier against golden_signals.jsonl with per-type metrics."""

from __future__ import annotations

import json
from collections import defaultdict

from ci_paths import MONOREPO_ROOT
from collectors.signal_processor import classify_for_storage

GOLDEN = MONOREPO_ROOT / "tests" / "fixtures" / "golden_signals.jsonl"
MIN_ACCURACY = 0.90


def run_eval(*, min_accuracy: float = MIN_ACCURACY) -> int:
    if not GOLDEN.is_file():
        print(f"FAIL: missing {GOLDEN}")
        return 1

    rows: list[dict] = []
    with GOLDEN.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    correct = 0
    by_type: dict[str, list[bool]] = defaultdict(list)
    misses: list[str] = []

    for row in rows:
        label, _, _ = classify_for_storage(row["text"], row.get("source", "rss"))
        expected = row["event_type"]
        ok = label == expected
        correct += int(ok)
        by_type[expected].append(ok)
        if not ok:
            misses.append(f"expected={expected} got={label} | {row['text'][:72]}")

    acc = correct / len(rows) if rows else 0.0
    print(f"Golden set: {correct}/{len(rows)} ({acc:.1%})")

    print("\nPer event_type:")
    for event_type in sorted(by_type):
        hits = by_type[event_type]
        pct = 100.0 * sum(hits) / len(hits)
        print(f"  {event_type}: {sum(hits)}/{len(hits)} ({pct:.0f}%)")

    if misses:
        print("\nMisses:")
        for m in misses:
            print(f"  {m}")

    if acc < min_accuracy:
        print(f"\nFAIL: accuracy {acc:.1%} < {min_accuracy:.0%}")
        return 1

    print(f"\nPASS: accuracy >= {min_accuracy:.0%}")
    return 0


def main() -> int:
    return run_eval()


if __name__ == "__main__":
    raise SystemExit(main())
