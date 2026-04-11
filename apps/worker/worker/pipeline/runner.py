from __future__ import annotations

from typing import Any

from ..comments import (
    BilibiliCommentCollector,
    YouTubeCommentCollector,
)
from ..config import Settings
from ..state.postgres_store import PostgresBusinessStore
from ..state.sqlite_store import SQLiteStateStore
from . import orchestrator
from .policies import (
    apply_comments_policy as _apply_comments_policy,
)
from .policies import (
    build_comments_policy as _build_comments_policy,
)
from .policies import (
    build_frame_policy as _build_frame_policy,
)
from .policies import (
    build_llm_policy as _build_llm_policy,
)
from .policies import (
    build_llm_policy_section as _build_llm_policy_section,
)
from .policies import (
    build_retry_policy as _build_retry_policy_impl,
)
from .policies import (
    classify_error as _classify_error_impl,
)
from .policies import (
    coerce_bool as _coerce_bool,
)
from .policies import (
    coerce_float as _coerce_float,
)
from .policies import (
    coerce_int as _coerce_int,
)
from .policies import (
    coerce_str_list as _coerce_str_list,
)
from .policies import (
    dedupe_keep_order as _dedupe_keep_order,
)
from .policies import (
    default_comment_sort_for_platform as _default_comment_sort_for_platform,
)
from .policies import (
    digest_is_chinese as _digest_is_chinese,
)
from .policies import (
    extract_json_object as _extract_json_object,
)
from .policies import (
    frame_paths_from_frames as _frame_paths_from_frames,
)
from .policies import (
    llm_media_input_dimension as _llm_media_input_dimension,
)
from .policies import (
    normalize_llm_input_mode as _normalize_llm_input_mode,
)
from .policies import (
    normalize_overrides_payload as _normalize_overrides_payload,
)
from .policies import (
    normalize_pipeline_mode as _normalize_pipeline_mode,
)
from .policies import (
    outline_is_chinese as _outline_is_chinese,
)
from .policies import (
    override_section as _override_section,
)
from .policies import (
    refresh_llm_media_input_dimension as _refresh_llm_media_input_dimension,
)
from .policies import (
    retry_delay_seconds as _retry_delay_seconds_impl,
)
from .runner_rendering import (
    build_artifact_asset_url as _build_artifact_asset_url,
)
from .runner_rendering import (
    build_chapters_markdown as _build_chapters_markdown,
)
from .runner_rendering import (
    build_chapters_toc_markdown as _build_chapters_toc_markdown,
)
from .runner_rendering import (
    build_code_blocks_markdown as _build_code_blocks_markdown,
)
from .runner_rendering import (
    build_comments_markdown as _build_comments_markdown,
)
from .runner_rendering import (
    build_comments_prompt_context as _build_comments_prompt_context,
)
from .runner_rendering import (
    build_fallback_notes_markdown as _build_fallback_notes_markdown,
)
from .runner_rendering import (
    build_frames_embedded_markdown as _build_frames_embedded_markdown,
)
from .runner_rendering import (
    build_frames_markdown as _build_frames_markdown,
)
from .runner_rendering import (
    build_frames_prompt_context as _build_frames_prompt_context,
)
from .runner_rendering import (
    build_timestamp_refs_markdown as _build_timestamp_refs_markdown,
)
from .runner_rendering import (
    collect_code_blocks as _collect_code_blocks,
)
from .runner_rendering import (
    estimate_duration_seconds as _estimate_duration_seconds,
)
from .runner_rendering import (
    extract_code_snippets as _extract_code_snippets,
)
from .runner_rendering import (
    format_seconds as _format_seconds,
)
from .runner_rendering import (
    load_digest_template as _load_digest_template,
)
from .runner_rendering import (
    materialize_frames_for_artifacts as _materialize_frames_for_artifacts,
)
from .runner_rendering import (
    parse_duration_seconds as _parse_duration_seconds,
)
from .runner_rendering import (
    render_template as _render_template,
)
from .runner_rendering import (
    should_include_frame_prompt as _should_include_frame_prompt,
)
from .runner_rendering import (
    timestamp_link as _timestamp_link,
)
from .step_executor import (
    append_degradation as _append_degradation,
)
from .step_executor import (
    apply_state_updates as _apply_state_updates,
)
from .step_executor import (
    build_mode_skip_step as _build_mode_skip_step,
)
from .step_executor import (
    build_step_cache_info as _build_step_cache_info,
)
from .step_executor import (
    execute_step as _execute_step,
)
from .step_executor import (
    run_command as _run_command,
)
from .step_executor import (
    run_command_once as _run_command_once,
)
from .steps.article import (
    step_fetch_article_content as _step_fetch_article_content_impl,
)
from .steps.artifacts import step_write_artifacts as _step_write_artifacts_impl
from .steps.comments import step_collect_comments as _step_collect_comments_impl
from .steps.embedding import step_build_embeddings as _step_build_embeddings_impl
from .steps.frames import step_extract_frames as _step_extract_frames_impl
from .steps.llm import (
    gemini_generate as _gemini_generate,
)
from .steps.llm import (
    normalize_digest_payload as _normalize_digest_payload,
)
from .steps.llm import (
    normalize_outline_payload as _normalize_outline_payload,
)
from .steps.llm import (
    step_llm_digest as _step_llm_digest_impl,
)
from .steps.llm import (
    step_llm_outline as _step_llm_outline_impl,
)
from .steps.media import step_download_media as _step_download_media_impl
from .steps.metadata import step_fetch_metadata as _step_fetch_metadata_impl
from .steps.subtitles import (
    fetch_youtube_transcript_text as _fetch_youtube_transcript_text,
)
from .steps.subtitles import (
    step_collect_subtitles as _step_collect_subtitles_impl,
)
from .types import (
    ARTICLE_PIPELINE_STEPS,
    PIPELINE_MODE_FORCE_STEPS,
    PIPELINE_MODE_SKIP_STEPS,
    PIPELINE_MODE_SKIP_UPDATES,
    PIPELINE_STEPS,
    STEP_INPUT_KEYS,
    STEP_SETTING_KEYS,
    STEP_VERSIONS,
    CommandResult,
    LLMInputMode,
    PipelineContext,
    PipelineMode,
    PipelineStatus,
    RetryCategory,
    StepExecution,
    StepStatus,
)

_build_context = orchestrator.build_context
_resolve_pipeline_status = orchestrator.resolve_pipeline_status

__all__ = [
    "PIPELINE_MODE_FORCE_STEPS",
    "PIPELINE_MODE_SKIP_STEPS",
    "PIPELINE_MODE_SKIP_UPDATES",
    "PIPELINE_STEPS",
    "STEP_INPUT_KEYS",
    "STEP_SETTING_KEYS",
    "STEP_VERSIONS",
    "CommandResult",
    "LLMInputMode",
    "PipelineContext",
    "PipelineMode",
    "PipelineStatus",
    "RetryCategory",
    "StepExecution",
    "StepStatus",
    "_append_degradation",
    "_apply_comments_policy",
    "_apply_state_updates",
    "_build_artifact_asset_url",
    "_build_chapters_markdown",
    "_build_chapters_toc_markdown",
    "_build_code_blocks_markdown",
    "_build_comments_markdown",
    "_build_comments_policy",
    "_build_comments_prompt_context",
    "_build_context",
    "_build_fallback_notes_markdown",
    "_build_frame_policy",
    "_build_frames_embedded_markdown",
    "_build_frames_markdown",
    "_build_frames_prompt_context",
    "_build_llm_policy",
    "_build_llm_policy_section",
    "_build_mode_skip_step",
    "_build_retry_policy",
    "_build_step_cache_info",
    "_build_timestamp_refs_markdown",
    "_classify_error",
    "_coerce_bool",
    "_coerce_float",
    "_coerce_int",
    "_coerce_str_list",
    "_collect_code_blocks",
    "_dedupe_keep_order",
    "_default_comment_sort_for_platform",
    "_digest_is_chinese",
    "_estimate_duration_seconds",
    "_execute_step",
    "_extract_code_snippets",
    "_extract_json_object",
    "_fetch_youtube_transcript_text",
    "_format_seconds",
    "_frame_paths_from_frames",
    "_gemini_generate",
    "_llm_media_input_dimension",
    "_load_digest_template",
    "_materialize_frames_for_artifacts",
    "_normalize_digest_payload",
    "_normalize_llm_input_mode",
    "_normalize_outline_payload",
    "_normalize_overrides_payload",
    "_normalize_pipeline_mode",
    "_outline_is_chinese",
    "_override_section",
    "_parse_duration_seconds",
    "_refresh_llm_media_input_dimension",
    "_render_template",
    "_resolve_pipeline_status",
    "_retry_delay_seconds",
    "_run_command",
    "_run_command_once",
    "_should_include_frame_prompt",
    "_step_build_embeddings",
    "_step_collect_comments",
    "_step_collect_subtitles",
    "_step_download_media",
    "_step_extract_frames",
    "_step_fetch_metadata",
    "_step_llm_digest",
    "_step_llm_outline",
    "_step_write_artifacts",
    "_timestamp_link",
    "run_pipeline",
]


def _build_retry_policy(
    settings: Settings, step_name: str | None = None
) -> dict[str, dict[str, float | int]]:
    resolved_step_name = "write_artifacts" if step_name is None else step_name
    return _build_retry_policy_impl(settings, step_name=resolved_step_name, llm_policy=None)


def _retry_delay_seconds(policy: dict[str, float | int], retries_used: int) -> float:
    return _retry_delay_seconds_impl(policy, retries_used)


def _classify_error(reason: str | None, error: str | None) -> RetryCategory:
    return _classify_error_impl(reason, error)


async def _step_fetch_metadata(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_fetch_metadata_impl(ctx, state, run_command=_run_command)


async def _step_fetch_article_content(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_fetch_article_content_impl(ctx, state, run_command=_run_command)


async def _step_download_media(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_download_media_impl(ctx, state, run_command=_run_command)


async def _step_collect_subtitles(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_collect_subtitles_impl(
        ctx,
        state,
        run_command=_run_command,
        fetch_youtube_transcript_text_fn=_fetch_youtube_transcript_text,
    )


async def _step_collect_comments(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_collect_comments_impl(
        ctx,
        state,
        bilibili_collector_cls=BilibiliCommentCollector,
        youtube_collector_cls=YouTubeCommentCollector,
    )


async def _step_extract_frames(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_extract_frames_impl(ctx, state, run_command=_run_command)


async def _step_llm_outline(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_llm_outline_impl(ctx, state, gemini_generate_fn=_gemini_generate)


async def _step_llm_digest(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_llm_digest_impl(ctx, state, gemini_generate_fn=_gemini_generate)


async def _step_write_artifacts(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_write_artifacts_impl(ctx, state)


async def _step_build_embeddings(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    return await _step_build_embeddings_impl(ctx, state)


async def run_pipeline(
    settings: Settings,
    sqlite_store: SQLiteStateStore,
    pg_store: PostgresBusinessStore,
    *,
    job_id: str,
    attempt: int,
    mode: str | None = None,
    overrides: dict[str, Any] | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    resolved_mode = "full" if mode is None else mode
    resolved_content_type = "video" if content_type is None else content_type
    if resolved_content_type == "article":
        step_handlers = [
            ("fetch_article_content", _step_fetch_article_content, False),
            ("llm_outline", _step_llm_outline, False),
            ("llm_digest", _step_llm_digest, False),
            ("build_embeddings", _step_build_embeddings, False),
            ("write_artifacts", _step_write_artifacts, True),
        ]
        pipeline_steps = ARTICLE_PIPELINE_STEPS
    elif resolved_content_type == "video":
        step_handlers = [
            ("fetch_metadata", _step_fetch_metadata, False),
            ("download_media", _step_download_media, False),
            ("collect_subtitles", _step_collect_subtitles, False),
            ("collect_comments", _step_collect_comments, False),
            ("extract_frames", _step_extract_frames, False),
            ("llm_outline", _step_llm_outline, False),
            ("llm_digest", _step_llm_digest, False),
            ("build_embeddings", _step_build_embeddings, False),
            ("write_artifacts", _step_write_artifacts, True),
        ]
        pipeline_steps = PIPELINE_STEPS
    else:
        raise ValueError(f"unsupported content_type: {resolved_content_type}")
    return await orchestrator.run_pipeline(
        settings=settings,
        sqlite_store=sqlite_store,
        pg_store=pg_store,
        job_id=job_id,
        attempt=attempt,
        mode=resolved_mode,
        overrides=overrides,
        step_handlers=step_handlers,
        pipeline_steps=pipeline_steps,
        content_type=resolved_content_type,
    )
