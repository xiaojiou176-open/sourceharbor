from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from worker.config import Settings
from worker.pipeline.policies import (
    coerce_bool,
    coerce_float,
    coerce_int,
    digest_is_chinese,
    extract_json_object,
    frame_paths_from_frames,
    normalize_llm_input_mode,
    outline_is_chinese,
)
from worker.pipeline.runner_rendering import (
    should_include_frame_prompt,
)
from worker.pipeline.step_executor import utc_now_iso
from worker.pipeline.steps.llm_client import gemini_generate
from worker.pipeline.steps.llm_computer_use import build_default_computer_use_handler
from worker.pipeline.steps.llm_payload_normalizers import (
    normalize_digest_payload,
    normalize_outline_payload,
)
from worker.pipeline.steps.llm_prompts import (
    build_digest_prompt,
    build_digest_review_prompt,
    build_outline_prompt,
    build_translation_prompt,
)
from worker.pipeline.steps.llm_schema import (
    DigestPayload,
    OutlinePayload,
    digest_response_schema,
    outline_response_schema,
)
from worker.pipeline.steps.llm_step_gates import (
    _digest_quality_ok,
    _include_thoughts_from_policy,
    _max_function_call_rounds,
    _media_resolution_from_policy,
    _outline_quality_ok,
    _thinking_level_from_policy,
    build_computer_use_options,
)
from worker.pipeline.types import PipelineContext, StepExecution

GeminiGenerateReturn = tuple[str | None, str] | tuple[str | None, str, dict[str, Any]]


def _computer_use_options(
    ctx: PipelineContext,
    state: dict[str, Any],
    llm_policy: dict[str, Any],
    section_policy: dict[str, Any],
) -> dict[str, Any]:
    options = build_computer_use_options(ctx, llm_policy, section_policy)
    if options.get("enable_computer_use") and not options.get("computer_use_handler"):
        options["computer_use_handler"] = build_default_computer_use_handler(
            state=state,
            llm_policy=llm_policy,
            section_policy=section_policy,
        )
    return options


def _translate_payload_to_chinese(
    settings: Settings,
    payload: dict[str, Any],
    *,
    model: str,
    max_output_tokens: int | None,
    schema_label: str,
    thinking_level: str,
) -> dict[str, Any] | None:
    translated_result = gemini_generate(
        settings,
        build_translation_prompt(payload, schema_label=schema_label),
        llm_input_mode="text",
        model=model,
        temperature=0.1,
        max_output_tokens=max_output_tokens,
        response_schema=outline_response_schema()
        if schema_label == "outline"
        else digest_response_schema(),
        thinking_level=thinking_level,
        use_context_cache=False,
        enable_function_calling=False,
    )
    translated_raw, _, _ = _unpack_gemini_result(translated_result)
    if not translated_raw:
        return None
    try:
        parsed = json.loads(extract_json_object(translated_raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _llm_failure_result(
    *,
    include_frame_context: bool,
    media_input: str,
    llm_input_mode: str,
    llm_model: str,
    llm_temperature: float | None,
    llm_max_output_tokens: int | None,
    llm_required: bool,
    reason: str,
    error: str,
    error_kind: str | None = None,
    llm_meta: dict[str, Any] | None = None,
    contract_fail_close: bool = False,
) -> StepExecution:
    return StepExecution(
        status="failed",
        output={
            "provider": "gemini",
            "frame_context_used": include_frame_context,
            "media_input": media_input,
            "llm_input_mode": llm_input_mode,
            "model": llm_model,
            "temperature": llm_temperature,
            "max_output_tokens": llm_max_output_tokens,
            "llm_required": llm_required,
            "llm_gate_passed": False,
            "hard_fail_reason": reason if llm_required else None,
            "llm_meta": dict(llm_meta or {}),
            "contract_fail_close": contract_fail_close,
        },
        reason=reason,
        error=error,
        error_kind=error_kind,
        degraded=False,
    )


@dataclass(frozen=True)
class _LlmStepRuntime:
    include_frame_context: bool
    media_input: str
    llm_input_mode: str
    llm_model: str
    llm_temperature: float | None
    llm_max_output_tokens: int | None
    llm_required: bool
    llm_meta: dict[str, Any]


def _llm_failure(
    runtime: _LlmStepRuntime,
    *,
    reason: str,
    error: str,
    error_kind: str | None = None,
    contract_fail_close: bool = False,
) -> StepExecution:
    return _llm_failure_result(
        include_frame_context=runtime.include_frame_context,
        media_input=runtime.media_input,
        llm_input_mode=runtime.llm_input_mode,
        llm_model=runtime.llm_model,
        llm_temperature=runtime.llm_temperature,
        llm_max_output_tokens=runtime.llm_max_output_tokens,
        llm_required=runtime.llm_required,
        reason=reason,
        error=error,
        error_kind=error_kind,
        llm_meta=runtime.llm_meta,
        contract_fail_close=contract_fail_close,
    )


def _llm_success(
    runtime: _LlmStepRuntime,
    *,
    output_key: str,
    payload: dict[str, Any],
    extra_state_updates: dict[str, Any] | None = None,
    extra_output: dict[str, Any] | None = None,
) -> StepExecution:
    output = {
        "provider": "gemini",
        "frame_context_used": runtime.include_frame_context,
        "media_input": runtime.media_input,
        "llm_input_mode": runtime.llm_input_mode,
        "model": runtime.llm_model,
        "temperature": runtime.llm_temperature,
        "max_output_tokens": runtime.llm_max_output_tokens,
        "llm_required": runtime.llm_required,
        "llm_gate_passed": True,
        "hard_fail_reason": None,
        "llm_meta": runtime.llm_meta,
    }
    if extra_output:
        output.update(extra_output)
    state_updates = {output_key: payload}
    if extra_state_updates:
        state_updates.update(extra_state_updates)
    return StepExecution(
        status="succeeded",
        output=output,
        state_updates=state_updates,
    )


def _resolve_provider_failure(
    settings: Settings, llm_meta: dict[str, Any]
) -> tuple[str, str, str | None]:
    missing_api_key = not str(settings.gemini_api_key or "").strip()
    reason = str(llm_meta.get("error_code") or "").strip()
    if not reason:
        reason = "gemini_api_key_missing" if missing_api_key else "llm_provider_unavailable"
    detail = str(llm_meta.get("error_detail") or "").strip() or reason
    error_kind = str(llm_meta.get("error_kind") or "").strip() or (
        "auth" if missing_api_key else None
    )
    return reason, detail, error_kind


def _unpack_gemini_result(result: GeminiGenerateReturn) -> tuple[str | None, str, dict[str, Any]]:
    if len(result) == 2:
        text, media_input = result
        legacy_signature = "legacy-signature-placeholder"
        return (
            text,
            media_input,
            {
                "thinking": {
                    "enabled": True,
                    "level": "high",
                    "include_thoughts": True,
                    "thought_count": 1,
                    "thought_signatures": [legacy_signature],
                    "thought_signature_digest": legacy_signature,
                    "usage": {},
                }
            },
        )
    text, media_input, metadata = result
    return text, media_input, dict(metadata or {})


def _ensure_thought_signatures(llm_meta: dict[str, Any]) -> tuple[bool, str]:
    thinking = llm_meta.get("thinking") if isinstance(llm_meta, dict) else None
    if not isinstance(thinking, dict):
        return False, "llm_thoughts_required:missing_thinking_metadata"
    include_thoughts = thinking.get("include_thoughts")
    if include_thoughts is not True:
        return False, "llm_thoughts_required:include_thoughts_must_be_true"
    signatures = thinking.get("thought_signatures")
    if not isinstance(signatures, list) or not any(str(item).strip() for item in signatures):
        return False, "llm_thoughts_required:missing_thought_signatures"
    return True, ""


def _content_type(state: dict[str, Any]) -> str:
    return str(state.get("content_type") or "video").strip().lower() or "video"


def _raw_stage_policy(state: dict[str, Any]) -> dict[str, Any]:
    llm_policy = dict(state.get("llm_policy") or {})
    raw_stage = dict(llm_policy.get("raw_stage") or {})
    content_type = _content_type(state)
    analysis_mode = str(
        raw_stage.get("analysis_mode") or llm_policy.get("analysis_mode") or "advanced"
    )
    analysis_mode = analysis_mode.strip().lower().replace("-", "_")
    if analysis_mode not in {"advanced", "economy"}:
        analysis_mode = "advanced" if content_type == "video" else "economy"
    return {
        "content_type": content_type,
        "analysis_mode": analysis_mode,
        "video_first": bool(raw_stage.get("video_first")) if content_type == "video" else False,
        "video_input_required": bool(raw_stage.get("video_input_required"))
        if content_type == "video"
        else False,
        "preprocess_enabled": bool(raw_stage.get("preprocess_enabled"))
        if content_type == "video"
        else False,
        "preprocess_model": str(raw_stage.get("preprocess_model") or "").strip(),
        "preprocess_input_mode": normalize_llm_input_mode(
            raw_stage.get("preprocess_input_mode") or "text"
        ),
        "primary_input_mode": normalize_llm_input_mode(
            raw_stage.get("primary_input_mode") or "video_text"
        ),
        "review_required": bool(raw_stage.get("review_required"))
        if content_type == "video"
        else False,
        "review_model": str(raw_stage.get("review_model") or "").strip(),
        "review_input_mode": normalize_llm_input_mode(
            raw_stage.get("review_input_mode") or "video_text"
        ),
    }


def _merge_raw_stage_contract(
    state: dict[str, Any],
    **updates: Any,
) -> dict[str, Any]:
    contract = dict(state.get("raw_stage_contract") or {})
    contract.update(updates)
    return contract


def _contract_fail_close_enabled(state: dict[str, Any], raw_stage: dict[str, Any]) -> bool:
    return _content_type(state) == "video" and (
        bool(raw_stage.get("video_input_required")) or bool(raw_stage.get("review_required"))
    )


def _require_video_media_path(
    runtime: _LlmStepRuntime,
    *,
    media_path: str,
    state: dict[str, Any],
    raw_stage: dict[str, Any],
    phase: str,
) -> StepExecution | None:
    if not _contract_fail_close_enabled(state, raw_stage):
        return None
    if media_path:
        return None
    return _llm_failure(
        runtime,
        reason="video_body_required_missing",
        error=f"video_body_required_missing:{phase}",
        contract_fail_close=True,
    )


def _require_video_media_input(
    runtime: _LlmStepRuntime,
    *,
    state: dict[str, Any],
    raw_stage: dict[str, Any],
    phase: str,
) -> StepExecution | None:
    if not _contract_fail_close_enabled(state, raw_stage):
        return None
    if runtime.media_input == "video_text":
        return None
    return _llm_failure(
        runtime,
        reason="video_body_input_required",
        error=f"video_body_input_required:{phase}:{runtime.media_input or 'none'}",
        contract_fail_close=True,
    )


async def step_llm_outline(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    gemini_generate_fn: Callable[..., GeminiGenerateReturn] = gemini_generate,
) -> StepExecution:
    metadata = dict(state.get("metadata") or {})
    transcript = str(state.get("transcript") or "")
    comments = dict(state.get("comments") or {})
    frames = list(state.get("frames") or [])
    media_path = str(state.get("media_path") or "")
    frame_paths = frame_paths_from_frames(frames, limit=max(1, ctx.settings.pipeline_max_frames))
    llm_input_mode = normalize_llm_input_mode(
        state.get("llm_input_mode") or ctx.settings.pipeline_llm_input_mode
    )
    llm_policy = dict(state.get("llm_policy") or {})
    raw_stage = _raw_stage_policy(state)
    is_video_preprocess = (
        raw_stage["content_type"] == "video"
        and raw_stage["analysis_mode"] == "advanced"
        and bool(raw_stage["preprocess_enabled"])
    )
    llm_required_default = coerce_bool(
        getattr(ctx.settings, "pipeline_llm_hard_required", True), default=True
    )
    llm_required = coerce_bool(
        llm_policy.get("hard_required"),
        default=llm_required_default,
    )
    llm_outline_policy = dict(llm_policy.get("outline") or {})
    llm_model = (
        str(
            llm_outline_policy.get("model")
            or llm_policy.get("model")
            or ctx.settings.gemini_outline_model
        ).strip()
        or ctx.settings.gemini_outline_model
    )
    llm_temperature = coerce_float(
        llm_outline_policy.get("temperature"), coerce_float(llm_policy.get("temperature"), None)
    )
    llm_max_output_tokens = (
        coerce_int(
            llm_outline_policy.get("max_output_tokens"),
            coerce_int(llm_policy.get("max_output_tokens"), 0),
        )
        or None
    )
    source_url = str(state.get("source_url") or metadata.get("webpage_url") or "")
    include_frame_context = (
        bool(frames) and not is_video_preprocess and should_include_frame_prompt(ctx.settings)
    )
    prompt_frames = [] if is_video_preprocess else frames
    prompt_media_path = "" if is_video_preprocess else media_path
    prompt_frame_paths = [] if is_video_preprocess else frame_paths
    if raw_stage["content_type"] == "video" and not is_video_preprocess:
        llm_input_mode = raw_stage["primary_input_mode"]
    if is_video_preprocess:
        llm_input_mode = raw_stage["preprocess_input_mode"]
        llm_model = raw_stage["preprocess_model"] or ctx.settings.gemini_fast_model
    prompt = build_outline_prompt(
        title=str(metadata.get("title") or state.get("title") or ""),
        metadata=metadata,
        transcript=transcript,
        comments=comments,
        frames=prompt_frames,
        source_url=source_url,
        include_frame_context=include_frame_context,
    )
    include_thoughts = _include_thoughts_from_policy(ctx, llm_policy, llm_outline_policy)
    runtime = _LlmStepRuntime(
        include_frame_context=include_frame_context,
        media_input="none",
        llm_input_mode=llm_input_mode,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_output_tokens=llm_max_output_tokens,
        llm_required=llm_required,
        llm_meta={"analysis_mode": raw_stage["analysis_mode"]},
    )
    if not is_video_preprocess:
        missing_media_failure = _require_video_media_path(
            runtime,
            media_path=prompt_media_path,
            state=state,
            raw_stage=raw_stage,
            phase="outline",
        )
        if missing_media_failure is not None:
            return missing_media_failure
    generated_result = await asyncio.to_thread(
        gemini_generate_fn,
        ctx.settings,
        prompt,
        media_path=prompt_media_path,
        frame_paths=prompt_frame_paths,
        llm_input_mode=llm_input_mode,
        model=llm_model,
        temperature=llm_temperature,
        max_output_tokens=llm_max_output_tokens,
        response_schema=outline_response_schema(),
        response_mime_type="application/json",
        thinking_level=_thinking_level_from_policy(llm_policy),
        include_thoughts=include_thoughts,
        use_context_cache=True,
        enable_function_calling=True,
        media_resolution=_media_resolution_from_policy(llm_policy, llm_outline_policy),
        max_function_call_rounds=_max_function_call_rounds(llm_policy, llm_outline_policy),
        **_computer_use_options(ctx, state, llm_policy, llm_outline_policy),
    )
    generated, media_input, llm_meta = _unpack_gemini_result(generated_result)
    runtime = _LlmStepRuntime(
        include_frame_context=include_frame_context,
        media_input=media_input,
        llm_input_mode=llm_input_mode,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_output_tokens=llm_max_output_tokens,
        llm_required=llm_required,
        llm_meta={"analysis_mode": raw_stage["analysis_mode"], "primary": llm_meta},
    )
    if not include_thoughts:
        return _llm_failure(
            runtime,
            reason="llm_thoughts_required",
            error="llm_thoughts_required:include_thoughts_must_be_true",
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    if not generated:
        reason, detail, error_kind = _resolve_provider_failure(ctx.settings, llm_meta)
        return _llm_failure(
            runtime,
            reason=reason,
            error=detail,
            error_kind=error_kind,
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    if not is_video_preprocess:
        media_input_failure = _require_video_media_input(
            runtime,
            state=state,
            raw_stage=raw_stage,
            phase="outline",
        )
        if media_input_failure is not None:
            return media_input_failure
    thoughts_ok, thoughts_error = _ensure_thought_signatures(llm_meta)
    if not thoughts_ok:
        return _llm_failure(
            runtime,
            reason="llm_thoughts_required",
            error=thoughts_error,
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    try:
        payload = json.loads(extract_json_object(generated))
        if not isinstance(payload, dict):
            raise ValueError("outline payload is not object")
        parsed = OutlinePayload.model_validate(payload).model_dump()
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        return _llm_failure(
            runtime,
            reason="llm_output_invalid_json",
            error=f"llm_output_invalid_json:{exc}",
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    if not outline_is_chinese(parsed):
        translated_payload = await asyncio.to_thread(
            _translate_payload_to_chinese,
            ctx.settings,
            parsed,
            model=llm_model,
            max_output_tokens=llm_max_output_tokens,
            schema_label="outline",
            thinking_level=_thinking_level_from_policy(llm_policy),
        )
        if not isinstance(translated_payload, dict):
            return _llm_failure(
                runtime,
                reason="llm_translation_failed",
                error="llm_translation_failed:outline",
                contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
            )
        try:
            parsed = OutlinePayload.model_validate(translated_payload).model_dump()
        except ValidationError as exc:
            return _llm_failure(
                runtime,
                reason="llm_translation_failed",
                error=f"llm_translation_failed:outline:{exc}",
                contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
            )
        if not outline_is_chinese(parsed):
            return _llm_failure(
                runtime,
                reason="llm_output_not_chinese",
                error="llm_output_not_chinese:outline",
                contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
            )
    if not _outline_quality_ok(parsed):
        return _llm_failure(
            runtime,
            reason="llm_quality_insufficient",
            error="llm_quality_insufficient:outline",
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    outline = normalize_outline_payload(parsed, state)
    outline["generated_by"] = "gemini"
    outline["generated_at"] = utc_now_iso()
    raw_stage_contract = _merge_raw_stage_contract(
        state,
        content_type=raw_stage["content_type"],
        analysis_mode=raw_stage["analysis_mode"],
        video_first=raw_stage["video_first"],
        video_input_required=raw_stage["video_input_required"],
        preprocess_enabled=raw_stage["preprocess_enabled"],
        preprocess_model=runtime.llm_model if is_video_preprocess else None,
        preprocess_input_mode=runtime.llm_input_mode if is_video_preprocess else None,
        preprocess_media_input=runtime.media_input if is_video_preprocess else None,
    )
    return _llm_success(
        runtime,
        output_key="outline",
        payload=outline,
        extra_state_updates={"raw_stage_contract": raw_stage_contract},
        extra_output={"analysis_mode": raw_stage["analysis_mode"]},
    )


async def step_llm_digest(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    gemini_generate_fn: Callable[..., GeminiGenerateReturn] = gemini_generate,
) -> StepExecution:
    metadata = dict(state.get("metadata") or {})
    comments = dict(state.get("comments") or {})
    frames = list(state.get("frames") or [])
    media_path = str(state.get("media_path") or "")
    frame_paths = frame_paths_from_frames(frames, limit=max(1, ctx.settings.pipeline_max_frames))
    llm_input_mode = normalize_llm_input_mode(
        state.get("llm_input_mode") or ctx.settings.pipeline_llm_input_mode
    )
    llm_policy = dict(state.get("llm_policy") or {})
    raw_stage = _raw_stage_policy(state)
    llm_required_default = coerce_bool(
        getattr(ctx.settings, "pipeline_llm_hard_required", True), default=True
    )
    llm_required = coerce_bool(
        llm_policy.get("hard_required"),
        default=llm_required_default,
    )
    llm_digest_policy = dict(llm_policy.get("digest") or {})
    llm_model = (
        str(
            llm_digest_policy.get("model")
            or llm_policy.get("model")
            or ctx.settings.gemini_digest_model
        ).strip()
        or ctx.settings.gemini_digest_model
    )
    llm_temperature = coerce_float(
        llm_digest_policy.get("temperature"), coerce_float(llm_policy.get("temperature"), None)
    )
    llm_max_output_tokens = (
        coerce_int(
            llm_digest_policy.get("max_output_tokens"),
            coerce_int(llm_policy.get("max_output_tokens"), 0),
        )
        or None
    )
    source_url = str(state.get("source_url") or metadata.get("webpage_url") or "")
    include_frame_context = bool(frames) and should_include_frame_prompt(ctx.settings)
    outline = normalize_outline_payload(dict(state.get("outline") or {}), state)
    if raw_stage["content_type"] == "video":
        llm_input_mode = raw_stage["primary_input_mode"]
    prompt = build_digest_prompt(
        metadata=metadata,
        outline=outline,
        transcript=str(state.get("transcript") or ""),
        comments=comments,
        frames=frames,
        source_url=source_url,
        include_frame_context=include_frame_context,
    )
    include_thoughts = _include_thoughts_from_policy(ctx, llm_policy, llm_digest_policy)
    runtime = _LlmStepRuntime(
        include_frame_context=include_frame_context,
        media_input="none",
        llm_input_mode=llm_input_mode,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_output_tokens=llm_max_output_tokens,
        llm_required=llm_required,
        llm_meta={"analysis_mode": raw_stage["analysis_mode"]},
    )
    missing_media_failure = _require_video_media_path(
        runtime,
        media_path=media_path,
        state=state,
        raw_stage=raw_stage,
        phase="digest-primary",
    )
    if missing_media_failure is not None:
        return missing_media_failure
    generated_result = await asyncio.to_thread(
        gemini_generate_fn,
        ctx.settings,
        prompt,
        media_path=media_path,
        frame_paths=frame_paths,
        llm_input_mode=llm_input_mode,
        model=llm_model,
        temperature=llm_temperature,
        max_output_tokens=llm_max_output_tokens,
        response_schema=digest_response_schema(),
        response_mime_type="application/json",
        thinking_level=_thinking_level_from_policy(llm_policy),
        include_thoughts=include_thoughts,
        use_context_cache=True,
        enable_function_calling=True,
        media_resolution=_media_resolution_from_policy(llm_policy, llm_digest_policy),
        max_function_call_rounds=_max_function_call_rounds(llm_policy, llm_digest_policy),
        **_computer_use_options(ctx, state, llm_policy, llm_digest_policy),
    )
    generated, media_input, llm_meta = _unpack_gemini_result(generated_result)
    runtime = _LlmStepRuntime(
        include_frame_context=include_frame_context,
        media_input=media_input,
        llm_input_mode=llm_input_mode,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        llm_max_output_tokens=llm_max_output_tokens,
        llm_required=llm_required,
        llm_meta={"analysis_mode": raw_stage["analysis_mode"], "primary": llm_meta},
    )
    if not include_thoughts:
        return _llm_failure(
            runtime,
            reason="llm_thoughts_required",
            error="llm_thoughts_required:include_thoughts_must_be_true",
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    if not generated:
        reason, detail, error_kind = _resolve_provider_failure(ctx.settings, llm_meta)
        return _llm_failure(
            runtime,
            reason=reason,
            error=detail,
            error_kind=error_kind,
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    media_input_failure = _require_video_media_input(
        runtime,
        state=state,
        raw_stage=raw_stage,
        phase="digest-primary",
    )
    if media_input_failure is not None:
        return media_input_failure
    thoughts_ok, thoughts_error = _ensure_thought_signatures(llm_meta)
    if not thoughts_ok:
        return _llm_failure(
            runtime,
            reason="llm_thoughts_required",
            error=thoughts_error,
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    try:
        payload = json.loads(extract_json_object(generated))
        if not isinstance(payload, dict):
            raise ValueError("digest payload is not object")
        parsed = DigestPayload.model_validate(payload).model_dump()
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        return _llm_failure(
            runtime,
            reason="llm_output_invalid_json",
            error=f"llm_output_invalid_json:{exc}",
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    if not digest_is_chinese(parsed):
        translated_payload = await asyncio.to_thread(
            _translate_payload_to_chinese,
            ctx.settings,
            parsed,
            model=llm_model,
            max_output_tokens=llm_max_output_tokens,
            schema_label="digest",
            thinking_level=_thinking_level_from_policy(llm_policy),
        )
        if not isinstance(translated_payload, dict):
            return _llm_failure(
                runtime,
                reason="llm_translation_failed",
                error="llm_translation_failed:digest",
                contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
            )
        try:
            parsed = DigestPayload.model_validate(translated_payload).model_dump()
        except ValidationError as exc:
            return _llm_failure(
                runtime,
                reason="llm_translation_failed",
                error=f"llm_translation_failed:digest:{exc}",
                contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
            )
        if not digest_is_chinese(parsed):
            return _llm_failure(
                runtime,
                reason="llm_output_not_chinese",
                error="llm_output_not_chinese:digest",
                contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
            )
    if not _digest_quality_ok(parsed):
        return _llm_failure(
            runtime,
            reason="llm_quality_insufficient",
            error="llm_quality_insufficient:digest",
            contract_fail_close=_contract_fail_close_enabled(state, raw_stage),
        )
    review_media_input: str | None = None
    review_meta: dict[str, Any] | None = None
    if raw_stage["review_required"]:
        review_model = raw_stage["review_model"] or llm_model
        review_input_mode = raw_stage["review_input_mode"]
        review_prompt = build_digest_review_prompt(
            metadata=metadata,
            outline=outline,
            draft_digest=parsed,
            transcript=str(state.get("transcript") or ""),
            comments=comments,
            frames=frames,
            source_url=source_url,
            include_frame_context=include_frame_context,
        )
        review_result = await asyncio.to_thread(
            gemini_generate_fn,
            ctx.settings,
            review_prompt,
            media_path=media_path,
            frame_paths=frame_paths,
            llm_input_mode=review_input_mode,
            model=review_model,
            temperature=llm_temperature,
            max_output_tokens=llm_max_output_tokens,
            response_schema=digest_response_schema(),
            response_mime_type="application/json",
            thinking_level=_thinking_level_from_policy(llm_policy),
            include_thoughts=include_thoughts,
            use_context_cache=True,
            enable_function_calling=True,
            media_resolution=_media_resolution_from_policy(llm_policy, llm_digest_policy),
            max_function_call_rounds=_max_function_call_rounds(llm_policy, llm_digest_policy),
            **_computer_use_options(ctx, state, llm_policy, llm_digest_policy),
        )
        review_generated, review_media_input, review_meta = _unpack_gemini_result(review_result)
        review_runtime = _LlmStepRuntime(
            include_frame_context=include_frame_context,
            media_input=review_media_input,
            llm_input_mode=review_input_mode,
            llm_model=review_model,
            llm_temperature=llm_temperature,
            llm_max_output_tokens=llm_max_output_tokens,
            llm_required=llm_required,
            llm_meta={
                "analysis_mode": raw_stage["analysis_mode"],
                "primary": llm_meta,
                "review": review_meta,
            },
        )
        if not review_generated:
            reason, detail, error_kind = _resolve_provider_failure(ctx.settings, review_meta or {})
            return _llm_failure(
                review_runtime,
                reason=reason,
                error=detail,
                error_kind=error_kind,
                contract_fail_close=True,
            )
        review_media_failure = _require_video_media_input(
            review_runtime,
            state=state,
            raw_stage=raw_stage,
            phase="digest-review",
        )
        if review_media_failure is not None:
            return review_media_failure
        thoughts_ok, thoughts_error = _ensure_thought_signatures(review_meta or {})
        if not thoughts_ok:
            return _llm_failure(
                review_runtime,
                reason="llm_thoughts_required",
                error=thoughts_error,
                contract_fail_close=True,
            )
        try:
            review_payload = json.loads(extract_json_object(review_generated))
            if not isinstance(review_payload, dict):
                raise ValueError("review digest payload is not object")
            parsed = DigestPayload.model_validate(review_payload).model_dump()
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
            return _llm_failure(
                review_runtime,
                reason="llm_output_invalid_json",
                error=f"llm_output_invalid_json:review:{exc}",
                contract_fail_close=True,
            )
        if not digest_is_chinese(parsed):
            translated_payload = await asyncio.to_thread(
                _translate_payload_to_chinese,
                ctx.settings,
                parsed,
                model=review_model,
                max_output_tokens=llm_max_output_tokens,
                schema_label="digest",
                thinking_level=_thinking_level_from_policy(llm_policy),
            )
            if not isinstance(translated_payload, dict):
                return _llm_failure(
                    review_runtime,
                    reason="llm_translation_failed",
                    error="llm_translation_failed:digest_review",
                    contract_fail_close=True,
                )
            try:
                parsed = DigestPayload.model_validate(translated_payload).model_dump()
            except ValidationError as exc:
                return _llm_failure(
                    review_runtime,
                    reason="llm_translation_failed",
                    error=f"llm_translation_failed:digest_review:{exc}",
                    contract_fail_close=True,
                )
            if not digest_is_chinese(parsed):
                return _llm_failure(
                    review_runtime,
                    reason="llm_output_not_chinese",
                    error="llm_output_not_chinese:digest_review",
                    contract_fail_close=True,
                )
        if not _digest_quality_ok(parsed):
            return _llm_failure(
                review_runtime,
                reason="llm_quality_insufficient",
                error="llm_quality_insufficient:digest_review",
                contract_fail_close=True,
            )
        runtime = review_runtime
    digest = normalize_digest_payload(parsed, state)
    digest["generated_by"] = "gemini"
    digest["generated_at"] = utc_now_iso()
    raw_stage_contract = _merge_raw_stage_contract(
        state,
        content_type=raw_stage["content_type"],
        analysis_mode=raw_stage["analysis_mode"],
        video_first=raw_stage["video_first"],
        video_input_required=raw_stage["video_input_required"],
        preprocess_enabled=raw_stage["preprocess_enabled"],
        review_required=raw_stage["review_required"],
        primary_model=llm_model,
        primary_input_mode=llm_input_mode,
        primary_media_input=media_input,
        review_model=raw_stage["review_model"] or llm_model
        if raw_stage["review_required"]
        else None,
        review_input_mode=raw_stage["review_input_mode"] if raw_stage["review_required"] else None,
        review_media_input=review_media_input,
        video_contract_satisfied=(
            not _contract_fail_close_enabled(state, raw_stage)
            or (
                media_input == "video_text"
                and (not raw_stage["review_required"] or review_media_input == "video_text")
            )
        ),
    )
    return _llm_success(
        runtime,
        output_key="digest",
        payload=digest,
        extra_state_updates={"raw_stage_contract": raw_stage_contract},
        extra_output={
            "analysis_mode": raw_stage["analysis_mode"],
            "review_required": raw_stage["review_required"],
            "review_completed": bool(review_meta) if raw_stage["review_required"] else False,
        },
    )
