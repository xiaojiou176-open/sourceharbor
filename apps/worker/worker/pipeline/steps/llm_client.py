from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

from integrations.providers.gemini import build_gemini_client, load_gemini_sdk
from worker.config import Settings
from worker.pipeline.policies import normalize_llm_input_mode
from worker.pipeline.steps.llm_client_helpers import (
    _build_computer_use_tool,
    _build_frame_parts,
    _build_function_response_content,
    _cache_meta_default,
    _collect_thought_metadata,
    _execute_function_call,
    _extract_finish_reason,
    _extract_function_calls,
    _extract_primary_candidate_content,
    _extract_response_text,
    _is_cache_error,
    _normalize_media_resolution_policy,
    _response_is_safety_blocked,
    _thinking_config,
    classify_gemini_exception,
)
from worker.pipeline.steps.llm_prompts import build_evidence_citations, select_supporting_frames
from worker.pipeline.steps.llm_video_inputs import (
    prepare_video_proxy_for_gemini as _prepare_video_proxy_for_gemini,
)
from worker.pipeline.steps.llm_video_inputs import (
    wait_for_uploaded_file_ready as _wait_for_uploaded_file_ready,
)
from worker.pipeline.types import LLMInputMode

_CACHE_NAME_BY_KEY: dict[str, dict[str, Any]] = {}
_CACHE_SWEEP_STATE = {"last_sweep_at": 0.0}
ComputerUseHandler = Callable[..., dict[str, Any]]


def _cache_key(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8", errors="ignore"))
        digest.update(b"\0")
    return digest.hexdigest()


def _create_cached_content(
    client: Any,
    genai_types: Any,
    *,
    model: str,
    prompt: str,
    cache_key: str,
    ttl_seconds: int,
    max_keys: int,
    local_ttl_seconds: int,
) -> str | None:
    now = time.time()
    cached_entry = _CACHE_NAME_BY_KEY.get(cache_key)
    if isinstance(cached_entry, str) and cached_entry.strip():
        _CACHE_NAME_BY_KEY[cache_key] = {
            "name": cached_entry.strip(),
            "created_at": now,
            "last_used_at": now,
        }
        return cached_entry.strip()
    if isinstance(cached_entry, dict):
        cached_name = cached_entry.get("name")
        created_at = float(cached_entry.get("created_at") or 0.0)
        if (
            isinstance(cached_name, str)
            and cached_name
            and (now - created_at) <= max(60, local_ttl_seconds)
        ):
            cached_entry["last_used_at"] = now
            return cached_name

    ttl_seconds = max(300, int(ttl_seconds))
    cached = client.caches.create(
        model=model,
        config=genai_types.CreateCachedContentConfig(
            contents=[prompt],
            ttl=f"{ttl_seconds}s",
            system_instruction=(
                "Use cached context as the single source of truth and return strict JSON only."
            ),
        ),
    )
    name = getattr(cached, "name", None)
    if isinstance(name, str) and name.strip():
        _CACHE_NAME_BY_KEY[cache_key] = {
            "name": name,
            "created_at": now,
            "last_used_at": now,
        }
        _trim_local_cache(max_keys=max_keys)
        return name
    return None


def _drop_cached_content(cache_key: str) -> None:
    if not cache_key:
        return
    _CACHE_NAME_BY_KEY.pop(cache_key, None)


def _trim_local_cache(*, max_keys: int) -> None:
    max_keys = max(1, int(max_keys))
    if len(_CACHE_NAME_BY_KEY) <= max_keys:
        return
    ordered = sorted(
        _CACHE_NAME_BY_KEY.items(),
        key=lambda item: float((item[1] or {}).get("last_used_at") or 0.0),
    )
    overflow = len(_CACHE_NAME_BY_KEY) - max_keys
    for key, _ in ordered[:overflow]:
        _CACHE_NAME_BY_KEY.pop(key, None)


def _sweep_local_cache(*, local_ttl_seconds: int, sweep_interval_seconds: int) -> None:
    now = time.time()
    last_sweep_at = float(_CACHE_SWEEP_STATE.get("last_sweep_at") or 0.0)
    if (now - last_sweep_at) < max(10, int(sweep_interval_seconds)):
        return
    _CACHE_SWEEP_STATE["last_sweep_at"] = now
    ttl = max(60, int(local_ttl_seconds))
    expired_keys: list[str] = []
    for key, entry in _CACHE_NAME_BY_KEY.items():
        created_at = float((entry or {}).get("created_at") or 0.0)
        if created_at <= 0 or (now - created_at) > ttl:
            expired_keys.append(key)
    for key in expired_keys:
        _CACHE_NAME_BY_KEY.pop(key, None)


def _failure_meta(
    *,
    model: str,
    media_input: str,
    reason: str,
    detail: str,
    error_kind: str | None,
    request_id: str | None = None,
    http_status: int | None = None,
    termination_reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": request_id,
        "model": model,
        "media_input": media_input,
        "finish_reason": None,
        "termination_reason": termination_reason or "failed",
        "safety_blocked": reason == "llm_safety_blocked",
        "retry_attempts": 0,
        "http_status": http_status,
        "error_code": reason,
        "error_kind": error_kind,
        "error_detail": detail[:1000],
    }
    payload.update(_cache_meta_default(bypass_reason="request_failed"))
    return payload


def gemini_generate(
    settings: Settings,
    prompt: str,
    *,
    media_path: str | None = None,
    frame_paths: list[str] | None = None,
    llm_input_mode: LLMInputMode = "auto",
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    response_schema: dict[str, Any] | None = None,
    response_mime_type: str | None = "application/json",
    thinking_level: str | None = None,
    include_thoughts: bool | None = None,
    use_context_cache: bool = True,
    enable_function_calling: bool = True,
    media_resolution: dict[str, Any] | str | None = None,
    max_function_call_rounds: int = 2,
    enable_computer_use: bool = False,
    computer_use_handler: ComputerUseHandler | None = None,
    computer_use_require_confirmation: bool = True,
    computer_use_confirmed: bool = False,
    computer_use_max_steps: int = 3,
    computer_use_timeout_seconds: float = 30.0,
) -> tuple[str | None, str, dict[str, Any]]:
    model_name = str(model or settings.gemini_model).strip() or settings.gemini_model
    normalized_mode = normalize_llm_input_mode(llm_input_mode)
    normalized_media_path = str(media_path or "").strip()
    normalized_frame_paths = list(frame_paths or [])

    if not settings.gemini_api_key:
        return (
            None,
            "none",
            _failure_meta(
                model=model_name,
                media_input="none",
                reason="gemini_api_key_missing",
                detail="gemini api key is missing",
                error_kind="auth",
            ),
        )

    try:
        sdk = load_gemini_sdk()
        genai_types = sdk.genai_types
    except Exception as exc:
        return (
            None,
            "none",
            _failure_meta(
                model=model_name,
                media_input="none",
                reason="llm_runtime_import_failed",
                detail=str(exc),
                error_kind="runtime",
            ),
        )

    try:
        client = build_gemini_client(api_key=settings.gemini_api_key)
    except Exception as exc:
        reason, error_kind, http_status = classify_gemini_exception(exc)
        return (
            None,
            "none",
            _failure_meta(
                model=model_name,
                media_input="none",
                reason=reason,
                detail=str(exc),
                error_kind=error_kind,
                http_status=http_status,
            ),
        )

    _sweep_local_cache(
        local_ttl_seconds=settings.gemini_context_cache_local_ttl_seconds,
        sweep_interval_seconds=settings.gemini_context_cache_sweep_interval_seconds,
    )
    deferred_failure: tuple[str, dict[str, Any]] | None = None

    effective_thinking_level = str(thinking_level or settings.gemini_thinking_level or "high")
    effective_include_thoughts = (
        settings.gemini_include_thoughts if include_thoughts is None else bool(include_thoughts)
    )
    strict_schema_mode = bool(settings.gemini_strict_schema_mode)
    effective_media_resolution = _normalize_media_resolution_policy(media_resolution)
    max_function_call_rounds = max(0, int(max_function_call_rounds))
    computer_use_max_steps = max(0, int(computer_use_max_steps))
    effective_computer_use_timeout = max(0.1, float(computer_use_timeout_seconds))
    allowed_tools: dict[str, Callable[..., dict[str, Any]]] = {
        "select_supporting_frames": select_supporting_frames,
        "build_evidence_citations": build_evidence_citations,
    }
    config_kwargs: dict[str, Any] = {
        "thinking_config": _thinking_config(
            genai_types,
            thinking_level=effective_thinking_level,
            include_thoughts=effective_include_thoughts,
        ),
    }
    if temperature is not None:
        config_kwargs["temperature"] = temperature
    if max_output_tokens is not None:
        config_kwargs["max_output_tokens"] = max_output_tokens
    if response_mime_type:
        config_kwargs["response_mime_type"] = response_mime_type
    if response_schema:
        config_kwargs["response_json_schema"] = response_schema
    tool_defs: list[Any] = []
    if enable_function_calling:
        tool_defs.extend([select_supporting_frames, build_evidence_citations])
    if enable_computer_use:
        tool_defs.append(_build_computer_use_tool(genai_types))
    if tool_defs:
        config_kwargs["tools"] = tool_defs
    config_variants: list[dict[str, Any]] = [dict(config_kwargs)]
    if response_schema and not strict_schema_mode:
        fallback_kwargs = dict(config_kwargs)
        fallback_kwargs.pop("response_json_schema", None)
        config_variants.append(fallback_kwargs)

    def _generate(contents: Any, *, cached_content: str | None = None) -> Any:
        last_exc: Exception | None = None
        for variant in config_variants:
            kwargs = dict(variant)
            if cached_content:
                kwargs["cached_content"] = cached_content
            try:
                config = genai_types.GenerateContentConfig(**kwargs)
                return client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                last_exc = exc
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("gemini_generate_unexpected_empty_config")

    def _generate_with_function_loop(
        contents: Any,
        *,
        cached_content: str | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
        thought_count = 0
        thought_signatures: list[str] = []
        usage_rollup: dict[str, int] = {}
        call_trace: list[dict[str, Any]] = []
        computer_use_steps_used = 0
        rounds = 0
        termination_reason = "no_response"
        finish_reason: str | None = None
        safety_blocked = False
        request_id: str | None = None
        conversation = list(contents) if isinstance(contents, list) else [contents]
        carried_signatures: list[str] = []

        while True:
            rounds += 1
            if carried_signatures:
                conversation.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    "Continue tool reasoning with preserved thought signatures from previous rounds: "
                                    + ", ".join(carried_signatures[:8])
                                )
                            }
                        ],
                    }
                )
            try:
                response = _generate(conversation, cached_content=cached_content)
            except Exception as exc:
                reason, error_kind, http_status = classify_gemini_exception(exc)
                return None, _failure_meta(
                    model=model_name,
                    media_input="text",
                    reason=reason,
                    detail=str(exc),
                    error_kind=error_kind,
                    http_status=http_status,
                    termination_reason="generate_exception",
                )
            request_id = (
                str(
                    getattr(response, "response_id", None)
                    or getattr(response, "id", None)
                    or request_id
                    or ""
                ).strip()
                or request_id
            )
            thought_meta = _collect_thought_metadata(response)
            thought_count += int(thought_meta.get("thought_count") or 0)
            current_signatures = [
                str(item).strip()
                for item in list(thought_meta.get("thought_signatures") or [])
                if str(item).strip()
            ]
            thought_signatures.extend(current_signatures)
            if current_signatures:
                carried_signatures = list(dict.fromkeys(current_signatures))
            for key, value in dict(thought_meta.get("usage") or {}).items():
                if isinstance(value, int):
                    usage_rollup[key] = usage_rollup.get(key, 0) + value
            finish_reason = _extract_finish_reason(response) or finish_reason
            safety_blocked = safety_blocked or _response_is_safety_blocked(response)

            text = _extract_response_text(response)
            if text:
                termination_reason = "text"
                break

            if not (enable_function_calling or enable_computer_use):
                termination_reason = "function_calling_disabled"
                break

            function_calls = _extract_function_calls(response)
            if not function_calls:
                termination_reason = "no_function_call"
                break
            if rounds > max_function_call_rounds:
                termination_reason = "max_function_call_rounds_reached"
                break

            tool_responses: list[dict[str, Any]] = []
            for call in function_calls:
                tool_name = str(call.get("name") or "").strip()
                args = call.get("args")
                if not isinstance(args, dict):
                    args = {}
                result = _execute_function_call(
                    allowed_tools,
                    tool_name=tool_name,
                    args=args,
                    computer_use_handler=computer_use_handler,
                    computer_use_require_confirmation=computer_use_require_confirmation,
                    computer_use_confirmed=computer_use_confirmed,
                    computer_use_timeout_seconds=effective_computer_use_timeout,
                    computer_use_step_limit=computer_use_max_steps,
                    computer_use_steps_used=computer_use_steps_used,
                )
                if tool_name == "computer_use" and result.get("status") == "ok":
                    computer_use_steps_used += 1
                call_trace.append(
                    {
                        "round": rounds,
                        "name": result["name"],
                        "status": result["status"],
                        "args": args,
                    }
                )
                tool_responses.append(result)

            candidate_content = _extract_primary_candidate_content(response)
            if candidate_content is not None:
                conversation.append(candidate_content)
            conversation.append(_build_function_response_content(genai_types, tool_responses))

        deduped_signatures = list(dict.fromkeys(thought_signatures))
        if (
            effective_include_thoughts
            and rounds > 1
            and not deduped_signatures
            and (thought_count > 0 or bool(usage_rollup))
        ):
            return None, _failure_meta(
                model=model_name,
                media_input="text",
                reason="llm_thoughts_required",
                detail="missing thought_signatures in multi-round generation",
                error_kind="contract",
                termination_reason="missing_thought_signatures",
            )
        signature_digest = None
        if deduped_signatures:
            signature_digest = hashlib.sha256(
                "|".join(deduped_signatures).encode("utf-8", errors="ignore")
            ).hexdigest()

        return text if termination_reason == "text" else None, {
            "request_id": request_id,
            "model": model_name,
            "termination_reason": termination_reason,
            "thinking": {
                "enabled": True,
                "level": str(effective_thinking_level).strip().lower(),
                "include_thoughts": effective_include_thoughts,
                "thought_count": thought_count,
                "thought_signatures": deduped_signatures,
                "thought_signature_digest": signature_digest,
                "usage": usage_rollup,
            },
            "function_calling": {
                "enabled": bool(enable_function_calling or enable_computer_use),
                "max_rounds": max_function_call_rounds,
                "rounds_used": rounds,
                "calls": call_trace,
                "termination_reason": termination_reason,
            },
            "finish_reason": finish_reason,
            "safety_blocked": safety_blocked,
            "computer_use": {
                "enabled": bool(enable_computer_use),
                "require_confirmation": bool(computer_use_require_confirmation),
                "confirmed": bool(computer_use_confirmed),
                "max_steps": computer_use_max_steps,
                "steps_used": computer_use_steps_used,
                "timeout_seconds": effective_computer_use_timeout,
            },
            "media_resolution": effective_media_resolution,
        }

    should_try_video = normalized_mode in {"auto", "video_text"} and bool(normalized_media_path)
    if should_try_video:
        try:
            video_upload_path = _prepare_video_proxy_for_gemini(normalized_media_path)
            uploaded = client.files.upload(file=video_upload_path)
            uploaded = _wait_for_uploaded_file_ready(client, uploaded)
            text, metadata = _generate_with_function_loop([uploaded, prompt])
            if text:
                metadata.update(_cache_meta_default(bypass_reason="non_text_mode"))
                return text, "video_text", metadata
            if metadata:
                metadata.setdefault("media_input", "video_text")
                deferred_failure = ("video_text", metadata)
        except Exception as exc:
            reason, error_kind, http_status = classify_gemini_exception(exc)
            deferred_failure = (
                "video_text",
                _failure_meta(
                    model=model_name,
                    media_input="video_text",
                    reason=reason,
                    detail=str(exc),
                    error_kind=error_kind,
                    http_status=http_status,
                ),
            )

    should_try_frames = normalized_mode in {"auto", "video_text", "frames_text"} and bool(
        normalized_frame_paths
    )
    if should_try_frames:
        try:
            frame_parts = _build_frame_parts(
                genai_types,
                normalized_frame_paths,
                limit=max(1, settings.pipeline_max_frames),
                media_resolution_policy=effective_media_resolution,
            )
            if frame_parts:
                text, metadata = _generate_with_function_loop([prompt, *frame_parts])
                if text:
                    metadata.update(_cache_meta_default(bypass_reason="non_text_mode"))
                    return text, "frames_text", metadata
                if metadata:
                    metadata.setdefault("media_input", "frames_text")
                    deferred_failure = ("frames_text", metadata)
        except Exception as exc:
            reason, error_kind, http_status = classify_gemini_exception(exc)
            deferred_failure = (
                "frames_text",
                _failure_meta(
                    model=model_name,
                    media_input="frames_text",
                    reason=reason,
                    detail=str(exc),
                    error_kind=error_kind,
                    http_status=http_status,
                ),
            )

    if normalized_mode in {"auto", "text"}:
        cache_key = _cache_key(model_name, prompt, normalized_mode)
        cached_content_name: str | None = None
        cache_enabled = (
            bool(use_context_cache)
            and bool(settings.gemini_context_cache_enabled)
            and not bool(enable_function_calling or enable_computer_use)
        )
        cache_meta = _cache_meta_default()
        if enable_function_calling or enable_computer_use:
            cache_meta["cache_bypass_reason"] = "cache_incompatible_with_tools"
        elif not cache_enabled:
            cache_meta["cache_bypass_reason"] = "cache_disabled"
        elif len(prompt) < max(0, settings.gemini_context_cache_min_chars):
            cache_meta["cache_bypass_reason"] = "prompt_too_short"
        else:
            try:
                cache_name = _create_cached_content(
                    client,
                    genai_types,
                    model=model_name,
                    prompt=prompt,
                    cache_key=cache_key,
                    ttl_seconds=settings.gemini_context_cache_ttl_seconds,
                    max_keys=settings.gemini_context_cache_max_keys,
                    local_ttl_seconds=settings.gemini_context_cache_local_ttl_seconds,
                )
                if cache_name:
                    cached_content_name = cache_name
            except Exception as exc:
                cache_meta["cache_bypass_reason"] = f"cache_create_failed:{type(exc).__name__}"
                cached_content_name = None

        try:
            if cached_content_name:
                try:
                    text, metadata = _generate_with_function_loop(
                        "Use the cached context and return a strict JSON response.",
                        cached_content=cached_content_name,
                    )
                    if text:
                        metadata.update(
                            {
                                "cache_hit": True,
                                "cache_recreate": False,
                                "cache_bypass_reason": None,
                            }
                        )
                    elif _is_cache_error(
                        RuntimeError(
                            str(metadata.get("error_detail") or metadata.get("error_code") or "")
                        )
                    ):
                        _drop_cached_content(cache_key)
                        try:
                            recreated_name = _create_cached_content(
                                client,
                                genai_types,
                                model=model_name,
                                prompt=prompt,
                                cache_key=cache_key,
                                ttl_seconds=settings.gemini_context_cache_ttl_seconds,
                                max_keys=settings.gemini_context_cache_max_keys,
                                local_ttl_seconds=settings.gemini_context_cache_local_ttl_seconds,
                            )
                        except Exception:
                            recreated_name = None
                        if recreated_name:
                            text, metadata = _generate_with_function_loop(
                                "Use the cached context and return a strict JSON response.",
                                cached_content=recreated_name,
                            )
                            metadata.update(
                                {
                                    "cache_hit": bool(text),
                                    "cache_recreate": True,
                                    "cache_bypass_reason": None if text else "cache_recreate_empty",
                                }
                            )
                        else:
                            text, metadata = _generate_with_function_loop(prompt)
                            metadata.update(
                                {
                                    "cache_hit": False,
                                    "cache_recreate": False,
                                    "cache_bypass_reason": "cache_recreate_failed",
                                }
                            )
                except Exception as cached_exc:
                    if _is_cache_error(cached_exc):
                        _drop_cached_content(cache_key)
                        try:
                            recreated_name = _create_cached_content(
                                client,
                                genai_types,
                                model=model_name,
                                prompt=prompt,
                                cache_key=cache_key,
                                ttl_seconds=settings.gemini_context_cache_ttl_seconds,
                                max_keys=settings.gemini_context_cache_max_keys,
                                local_ttl_seconds=settings.gemini_context_cache_local_ttl_seconds,
                            )
                        except Exception:
                            recreated_name = None
                        if recreated_name:
                            text, metadata = _generate_with_function_loop(
                                "Use the cached context and return a strict JSON response.",
                                cached_content=recreated_name,
                            )
                            metadata.update(
                                {
                                    "cache_hit": bool(text),
                                    "cache_recreate": True,
                                    "cache_bypass_reason": None if text else "cache_recreate_empty",
                                }
                            )
                        else:
                            text, metadata = _generate_with_function_loop(prompt)
                            metadata.update(
                                {
                                    "cache_hit": False,
                                    "cache_recreate": False,
                                    "cache_bypass_reason": "cache_recreate_failed",
                                }
                            )
                    else:
                        text, metadata = _generate_with_function_loop(prompt)
                        metadata.update(
                            {
                                "cache_hit": False,
                                "cache_recreate": False,
                                "cache_bypass_reason": f"cache_bypass:{type(cached_exc).__name__}",
                            }
                        )
            else:
                text, metadata = _generate_with_function_loop(prompt)
                metadata.update(cache_meta)
            if text:
                return text, "text", metadata
            if metadata:
                metadata.setdefault("model", model_name)
                metadata.setdefault("media_input", "text")
                return None, "text", metadata
        except Exception as exc:
            reason, error_kind, http_status = classify_gemini_exception(exc)
            deferred_failure = (
                "text",
                _failure_meta(
                    model=model_name,
                    media_input="text",
                    reason=reason,
                    detail=str(exc),
                    error_kind=error_kind,
                    http_status=http_status,
                ),
            )

    if deferred_failure is not None:
        media_input, meta = deferred_failure
        return None, media_input, meta

    return (
        None,
        "none",
        _failure_meta(
            model=model_name,
            media_input="none",
            reason="llm_no_response",
            detail="no text response from model",
            error_kind="runtime",
            termination_reason="no_response",
        ),
    )
