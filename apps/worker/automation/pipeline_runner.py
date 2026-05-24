"""Shared step runner for daily / frequent / grok pipelines."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from automation.run_utils import log_timings, run_script

PipelineStep: TypeAlias = str | tuple[str, tuple[str, ...]]
RunScriptFn = Callable[..., tuple[bool, float]]


def _abort_unless_force(
    step: str,
    ok: bool,
    force: bool,
    logger: logging.Logger | None = None,
) -> bool:
    """Return True if the pipeline should stop immediately."""
    log = logger or logging.getLogger("pipeline_runner")
    if ok:
        return False
    if force:
        log.warning("%s failed (--force: continuing)", step)
        return False
    log.error("%s failed; aborting pipeline (use --force to continue)", step)
    return True


def _normalize_step(step: PipelineStep) -> tuple[str, tuple[str, ...], str]:
    if isinstance(step, str):
        script = step
        args: tuple[str, ...] = ()
    else:
        script, args = step
    step_id = script.rsplit("/", 1)[-1].replace(".py", "")
    return script, args, step_id


@dataclass(frozen=True)
class PipelineResult:
    success: int
    total_steps: int
    timings: list[tuple[str, float]]
    aborted: bool
    aborted_step: str | None = None


def run_pipeline(
    steps: Sequence[PipelineStep],
    *,
    abort_on_fail: bool = False,
    force: bool = False,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    logger: logging.Logger,
    run_script_fn: RunScriptFn | None = None,
) -> PipelineResult:
    """Run pipeline steps in order; return counts and timings."""
    run_fn = run_script_fn or run_script
    if dry_run:
        os.environ["CI_DAILY_DRY_RUN"] = "1"
    if env:
        os.environ.update(env)

    timings: list[tuple[str, float]] = []
    success = 0
    total_steps = 0

    for step in steps:
        script, args, step_id = _normalize_step(step)
        ok, elapsed = run_fn(script, *args, logger=logger, step_id=step_id)
        timings.append((script, elapsed))
        total_steps += 1
        if ok:
            success += 1
        elif abort_on_fail and _abort_unless_force(script, ok, force, logger):
            log_timings(logger, timings)
            return PipelineResult(
                success=success,
                total_steps=total_steps,
                timings=timings,
                aborted=True,
                aborted_step=script,
            )

    return PipelineResult(
        success=success,
        total_steps=total_steps,
        timings=timings,
        aborted=False,
    )
