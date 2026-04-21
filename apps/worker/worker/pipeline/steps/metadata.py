from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from integrations.binaries.media_commands import yt_dlp_metadata_command
from integrations.providers.bilibili_comments import build_bilibili_headers
from integrations.providers.bilibili_evidence import fetch_bilibili_rich_evidence
from worker.pipeline.step_executor import utc_now_iso
from worker.pipeline.types import PipelineContext, StepExecution


async def step_fetch_metadata(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    run_command: Callable[[PipelineContext, list[str]], Awaitable[Any]],
    fetch_bilibili_rich_evidence: Callable[
        ..., Awaitable[dict[str, Any]]
    ] = fetch_bilibili_rich_evidence,
) -> StepExecution:
    source_url = str(state.get("source_url") or "")
    platform = str(state.get("platform") or "").strip().lower()
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

    settings = getattr(ctx, "settings", None)
    bilibili_cookie = getattr(settings, "bilibili_cookie", None)
    request_timeout_seconds = float(getattr(settings, "request_timeout_seconds", 10.0) or 10.0)
    ytdlp_headers = (
        build_bilibili_headers(cookie=bilibili_cookie) if platform == "bilibili" else None
    )
    cmd = yt_dlp_metadata_command(source_url, headers=ytdlp_headers)
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
                "language": payload.get("language"),
                "description": payload.get("description"),
                "tags": payload.get("tags") or [],
                "thumbnail": payload.get("thumbnail"),
                "webpage_url": payload.get("webpage_url") or source_url,
                "uploader_id": payload.get("uploader_id"),
                "uploader_url": payload.get("uploader_url"),
                "channel_id": payload.get("channel_id"),
                "channel_url": payload.get("channel_url"),
                "fetched_at": utc_now_iso(),
            }
            danmaku: dict[str, Any] = {}
            if platform == "bilibili":
                try:
                    richer_evidence = await fetch_bilibili_rich_evidence(
                        source_url=source_url,
                        video_uid=str(state.get("video_uid") or ""),
                        request_timeout_seconds=request_timeout_seconds,
                        cookie=str(bilibili_cookie or "").strip() or None,
                    )
                    rich_metadata = dict(richer_evidence.get("metadata") or {})
                    if rich_metadata:
                        metadata.update(rich_metadata)
                    danmaku = dict(richer_evidence.get("danmaku") or {})
                except Exception as exc:
                    danmaku = {
                        "status": "unavailable",
                        "entry_count": 0,
                        "entries": [],
                        "reason": str(exc)[:240] or "bilibili_rich_evidence_unavailable",
                    }
            return StepExecution(
                status="succeeded",
                output={"provider": "yt-dlp"},
                state_updates={"metadata": metadata, "danmaku": danmaku},
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
        state_updates={"metadata": fallback_metadata, "danmaku": {}},
        reason=reason,
        degraded=True,
    )
