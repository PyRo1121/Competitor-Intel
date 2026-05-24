"""Shared environment presets for worker entrypoints and Hermes bridges."""

from __future__ import annotations

import os


def apply_daily_prod_env(
    env: dict[str, str] | None = None,
    *,
    mutate_os_environ: bool = False,
) -> dict[str, str]:
    """Production daily pipeline: skip inline Grok, strict ingest guards."""
    target = os.environ if mutate_os_environ else (env.copy() if env is not None else os.environ.copy())
    target["CI_SKIP_GROK_X"] = "1"
    target["CI_STRICT_PIPELINE"] = "1"
    target["CI_REQUIRE_DEDUP_INDEX"] = "1"
    return target
