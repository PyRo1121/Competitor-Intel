"""Shared environment presets for worker entrypoints and Hermes bridges."""

from __future__ import annotations

import os


def apply_daily_prod_env(
    env: dict[str, str] | None = None,
    *,
    mutate_os_environ: bool = False,
) -> dict[str, str]:
    """Production daily pipeline: skip inline Grok, strict ingest guards."""
    out = (env if env is not None else dict(os.environ)).copy()
    out["CI_SKIP_GROK_X"] = "1"
    out["CI_STRICT_PIPELINE"] = "1"
    out["CI_REQUIRE_DEDUP_INDEX"] = "1"
    if mutate_os_environ:
        os.environ.update(out)
    return out
