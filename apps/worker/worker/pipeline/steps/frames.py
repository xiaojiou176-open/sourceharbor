from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from integrations.binaries.media_commands import ffmpeg_extract_frames_command
from worker.pipeline.policies import coerce_int
from worker.pipeline.types import CommandResult, PipelineContext, StepExecution, StepStatus


async def step_extract_frames(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    run_command: Callable[[PipelineContext, list[str]], Awaitable[CommandResult]],
) -> StepExecution:
    media_path = state.get("media_path")
    if not media_path:
        return StepExecution(
            status="skipped",
            state_updates={"frames": []},
            reason="media_path_missing",
            degraded=True,
        )

    frame_policy = dict(state.get("frame_policy") or {})
    frame_interval = max(1, int(ctx.settings.pipeline_frame_interval_seconds))
    frame_method = str(frame_policy.get("method") or "fps").strip().lower()
    if frame_method not in {"fps", "scene"}:
        frame_method = "fps"
    max_frames = max(
        1, coerce_int(frame_policy.get("max_frames"), int(ctx.settings.pipeline_max_frames))
    )

    output_pattern = str((ctx.frames_dir / "frame_%03d.jpg").resolve())
    cmd = ffmpeg_extract_frames_command(
        str(media_path),
        output_pattern,
        frame_method=frame_method,
        frame_interval=frame_interval,
        max_frames=max_frames,
    )

    result = await run_command(ctx, cmd)
    if not result.ok:
        status: StepStatus = "skipped" if result.reason == "binary_not_found" else "failed"
        return StepExecution(
            status=status,
            state_updates={"frames": []},
            reason=result.reason or "ffmpeg_failed",
            error=(result.stderr or "").strip()[-500:] or result.reason,
            degraded=True,
        )

    frame_files = sorted(path.resolve() for path in ctx.frames_dir.glob("frame_*.jpg"))
    if not frame_files:
        return StepExecution(
            status="failed",
            state_updates={"frames": []},
            reason="frame_not_generated",
            error="frame_not_generated",
            degraded=True,
        )

    frames_meta = [
        {
            "path": str(path),
            "timestamp_s": frame_interval * idx,
        }
        for idx, path in enumerate(frame_files)
    ]
    return StepExecution(
        status="succeeded",
        output={"frames": len(frames_meta), "method": frame_method, "max_frames": max_frames},
        state_updates={"frames": frames_meta},
    )
