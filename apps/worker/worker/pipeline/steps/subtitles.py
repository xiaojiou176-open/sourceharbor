from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import is_dataclass, replace
from pathlib import Path
from typing import Any

from integrations.providers import youtube_transcript as youtube_transcript_provider
from integrations.providers.bilibili_support import (
    assess_bilibili_asr_quality,
    build_bilibili_asr_plan,
)
from worker.pipeline.policies import coerce_bool
from worker.pipeline.types import CommandResult, PipelineContext, StepExecution

extract_youtube_video_id = youtube_transcript_provider.extract_youtube_video_id
fetch_youtube_transcript_text = youtube_transcript_provider.fetch_youtube_transcript_text


def _with_subprocess_timeout(ctx: PipelineContext, timeout_seconds: int) -> PipelineContext:
    updated_settings = replace(
        ctx.settings,
        pipeline_subprocess_timeout_seconds=timeout_seconds,
    )
    if is_dataclass(ctx):
        return replace(ctx, settings=updated_settings)

    state = dict(getattr(ctx, "__dict__", {}))
    state["settings"] = updated_settings
    return type(ctx)(**state)


def subtitle_candidates(download_dir: Path) -> list[Path]:
    return sorted(
        [p for p in download_dir.glob("*.vtt") if p.is_file()]
        + [p for p in download_dir.glob("*.srt") if p.is_file()]
        + [p for p in download_dir.glob("*.ass") if p.is_file()]
    )


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def subtitle_to_text(raw_content: str) -> str:
    lines: list[str] = []
    for line in raw_content.splitlines():
        content = line.strip()
        if not content:
            continue
        if content == "WEBVTT" or content.isdigit():
            continue
        if re.match(r"^\d{2}:\d{2}:\d{2}", content):
            continue
        if "-->" in content:
            continue
        content = re.sub(r"<[^>]+>", "", content)
        lines.append(content)
    return "\n".join(lines).strip()


def collect_subtitle_text_from_files(
    subtitle_files: list[Path],
    *,
    limit: int = 6,
) -> tuple[str, list[str]]:
    transcript_chunks: list[str] = []
    used_files: list[str] = []
    for path in subtitle_files[:limit]:
        text = subtitle_to_text(read_text_file(path))
        if text:
            transcript_chunks.append(text)
        used_files.append(str(path.resolve()))
    transcript = "\n".join(chunk for chunk in transcript_chunks if chunk).strip()
    return transcript, used_files


def collect_asr_output_text(download_dir: Path, media_path: str) -> str:
    media_stem = Path(media_path).stem
    preferred = download_dir / f"{media_stem}.txt"
    candidates: list[Path] = []
    if preferred.exists() and preferred.is_file():
        candidates.append(preferred)

    candidates.extend(
        sorted(
            [
                p
                for p in download_dir.glob("*.txt")
                if p.is_file() and p.name not in {preferred.name}
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    )
    for path in candidates:
        text = read_text_file(path).strip()
        if text:
            return text
    return ""


async def step_collect_subtitles(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    run_command: Callable[[PipelineContext, list[str]], Awaitable[CommandResult]],
    fetch_youtube_transcript_text_fn: Callable[[str], str],
) -> StepExecution:
    subtitle_files = subtitle_candidates(ctx.download_dir)
    transcript, used_subtitle_files = collect_subtitle_text_from_files(subtitle_files)
    overrides = dict(state.get("overrides") or {})
    subtitle_override_section = overrides.get("subtitles")
    subtitle_overrides = (
        dict(subtitle_override_section) if isinstance(subtitle_override_section, dict) else {}
    )
    platform = str(state.get("platform") or "").strip().lower()
    metadata = dict(state.get("metadata") or {})
    default_asr_profile = build_bilibili_asr_plan(metadata) if platform == "bilibili" else {}
    youtube_transcript_fallback_enabled = coerce_bool(
        subtitle_overrides.get("youtube_transcript_fallback_enabled"),
        default=coerce_bool(
            getattr(ctx.settings, "youtube_transcript_fallback_enabled", True),
            default=True,
        ),
    )
    asr_fallback_enabled = coerce_bool(
        subtitle_overrides.get("asr_fallback_enabled"),
        default=coerce_bool(
            default_asr_profile.get("enabled"),
            default=coerce_bool(
                getattr(ctx.settings, "asr_fallback_enabled", False),
                default=False,
            ),
        )
        or bool(default_asr_profile.get("enabled")),
    )
    explicit_asr_model = str(subtitle_overrides.get("asr_model_size") or "").strip()
    asr_model_candidates = (
        [explicit_asr_model]
        if explicit_asr_model
        else [
            str(item).strip()
            for item in (default_asr_profile.get("model_candidates") or [])
            if str(item).strip()
        ]
    )
    if not asr_model_candidates:
        asr_model_candidates = [
            str(getattr(ctx.settings, "asr_model_size", "small") or "small").strip() or "small"
        ]
    raw_timeout_override = subtitle_overrides.get("subprocess_timeout_seconds")
    try:
        if raw_timeout_override is not None:
            subtitle_timeout_override = max(1, int(raw_timeout_override))
        elif default_asr_profile.get("subprocess_timeout_seconds") is not None:
            subtitle_timeout_override = max(
                1,
                int(default_asr_profile["subprocess_timeout_seconds"]),
            )
        else:
            subtitle_timeout_override = None
    except (TypeError, ValueError):
        subtitle_timeout_override = None
    if transcript:
        return StepExecution(
            status="succeeded",
            output={
                "subtitle_files": len(used_subtitle_files),
                "transcript_provider": "downloaded_subtitles",
                "fallback_used": False,
            },
            state_updates={"transcript": transcript, "subtitle_files": used_subtitle_files},
        )

    failure_reasons: list[str] = []
    if used_subtitle_files:
        failure_reasons.append("subtitle_text_empty_after_parse")
    else:
        failure_reasons.append("subtitle_file_not_found")

    source_url = str(state.get("source_url") or "").strip()
    video_uid = str(state.get("video_uid") or "").strip()
    if asr_fallback_enabled and not default_asr_profile and platform not in {"youtube"}:
        failure_reasons.append("asr_fallback_platform_unsupported")
        asr_fallback_enabled = False

    if platform == "youtube" and youtube_transcript_fallback_enabled:
        video_id = extract_youtube_video_id(source_url, video_uid)
        if video_id:
            try:
                yt_transcript = await asyncio.to_thread(fetch_youtube_transcript_text_fn, video_id)
                if yt_transcript.strip():
                    return StepExecution(
                        status="succeeded",
                        output={
                            "subtitle_files": len(used_subtitle_files),
                            "transcript_provider": "youtube_transcript_fallback",
                            "fallback_used": True,
                        },
                        state_updates={
                            "transcript": yt_transcript.strip(),
                            "subtitle_files": used_subtitle_files,
                        },
                    )
                failure_reasons.append("youtube_transcript_empty")
            except Exception as exc:  # pragma: no cover
                failure_reasons.append(f"youtube_transcript_failed:{exc.__class__.__name__}")
        else:
            failure_reasons.append("youtube_video_id_not_resolved")
    else:
        failure_reasons.append("youtube_transcript_fallback_disabled_or_not_youtube")

    if asr_fallback_enabled:
        media_path = str(state.get("media_path") or "").strip()
        if media_path:
            asr_failure_reasons: list[str] = []
            run_ctx = ctx
            if subtitle_timeout_override is not None and subtitle_timeout_override != int(
                getattr(ctx.settings, "pipeline_subprocess_timeout_seconds", 180) or 180
            ):
                run_ctx = _with_subprocess_timeout(ctx, subtitle_timeout_override)
            last_asr_quality = None
            for candidate_model in asr_model_candidates:
                asr_commands = [
                    [
                        "whisper",
                        media_path,
                        "--model",
                        candidate_model,
                        "--task",
                        "transcribe",
                        "--output_format",
                        "txt",
                        "--output_dir",
                        str(ctx.download_dir.resolve()),
                    ],
                    [
                        "faster-whisper",
                        media_path,
                        "--model",
                        candidate_model,
                        "--output_dir",
                        str(ctx.download_dir.resolve()),
                        "--output_format",
                        "txt",
                    ],
                ]
                escalate_to_next_model = False
                stop_after_model_failure = False
                for cmd in asr_commands:
                    result = await run_command(run_ctx, cmd)
                    if result.ok:
                        asr_text = collect_asr_output_text(ctx.download_dir, media_path)
                        if not asr_text:
                            asr_failure_reasons.append("asr_transcript_empty")
                            continue
                        asr_quality = assess_bilibili_asr_quality(asr_text, metadata)
                        last_asr_quality = asr_quality
                        if asr_quality["status"] == "passed":
                            return StepExecution(
                                status="succeeded",
                                output={
                                    "subtitle_files": len(used_subtitle_files),
                                    "transcript_provider": "asr_fallback",
                                    "asr_model_size": candidate_model,
                                    "asr_model_candidates": asr_model_candidates,
                                    "asr_quality": asr_quality,
                                    "subprocess_timeout_seconds": getattr(
                                        run_ctx.settings,
                                        "pipeline_subprocess_timeout_seconds",
                                        None,
                                    ),
                                    "fallback_used": True,
                                },
                                state_updates={
                                    "transcript": asr_text,
                                    "subtitle_files": used_subtitle_files,
                                },
                            )
                        asr_failure_reasons.extend(
                            str(item).strip()
                            for item in (asr_quality.get("reasons") or [])
                            if str(item).strip()
                        )
                        escalate_to_next_model = True
                        break

                    asr_failure_reasons.append(result.reason or "asr_command_failed")
                    if result.reason != "binary_not_found":
                        stop_after_model_failure = True
                        break
                if escalate_to_next_model:
                    continue
                if stop_after_model_failure:
                    break

            if last_asr_quality is not None and last_asr_quality.get("status") != "passed":
                failure_reasons.append("asr_quality_insufficient")
                return StepExecution(
                    status="succeeded",
                    output={
                        "subtitle_files": len(used_subtitle_files),
                        "transcript_provider": "none",
                        "fallback_chain": failure_reasons,
                        "asr_model_candidates": asr_model_candidates,
                        "asr_quality": last_asr_quality,
                    },
                    state_updates={"transcript": "", "subtitle_files": used_subtitle_files},
                    reason="asr_quality_insufficient",
                    degraded=True,
                )

            if asr_failure_reasons:
                failure_reasons.append(f"asr_failed:{'|'.join(asr_failure_reasons)}")
        else:
            failure_reasons.append("asr_media_path_missing")
    else:
        failure_reasons.append("asr_fallback_disabled")

    return StepExecution(
        status="succeeded",
        output={
            "subtitle_files": len(used_subtitle_files),
            "transcript_provider": "none",
            "fallback_chain": failure_reasons,
        },
        state_updates={"transcript": "", "subtitle_files": used_subtitle_files},
        reason=failure_reasons[-1] if failure_reasons else "subtitle_unavailable",
        degraded=True,
    )
