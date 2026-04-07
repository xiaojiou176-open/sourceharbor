from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from integrations.binaries.media_commands import yt_dlp_metadata_command
from worker.pipeline.step_executor import utc_now_iso
from worker.pipeline.types import PipelineContext, StepExecution


async def step_fetch_metadata(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    run_command: Callable[[PipelineContext, list[str]], Awaitable[Any]],
) -> StepExecution:
    source_url = str(state.get("source_url") or "")
    base_metadata = {
        "title": state.get("title"),
        "platform": state.get("platform"),
        "video_uid": state.get("video_uid"),
        "source_url": source_url or None,
        "published_at": state.get("published_at"),
    }
    if not source_url:
        return StepExecution(
            status="failed",
            state_updates={"metadata": base_metadata},
            reason="source_url_missing",
            error="source_url_missing",
            degraded=True,
        )

    cmd = yt_dlp_metadata_command(source_url)
    result = await run_command(ctx, cmd)
    if result.ok:
        try:
            payload = json.loads(result.stdout)
            metadata = {
                **base_metadata,
                "extractor": payload.get("extractor"),
                "extractor_key": payload.get("extractor_key"),
                "uploader": payload.get("uploader"),
                "duration": payload.get("duration"),
                "description": payload.get("description"),
                "tags": payload.get("tags") or [],
                "thumbnail": payload.get("thumbnail"),
                "webpage_url": payload.get("webpage_url") or source_url,
                "fetched_at": utc_now_iso(),
            }
            return StepExecution(
                status="succeeded",
                output={"provider": "yt-dlp"},
                state_updates={"metadata": metadata},
            )
        except json.JSONDecodeError:
            pass

    fallback_metadata = {
        **base_metadata,
        "provider": "fallback",
        "fetched_at": utc_now_iso(),
    }
    reason = result.reason or "yt_dlp_failed"
    return StepExecution(
        status="succeeded",
        output={"provider": "fallback", "reason": reason},
        state_updates={"metadata": fallback_metadata},
        reason=reason,
        degraded=True,
    )
