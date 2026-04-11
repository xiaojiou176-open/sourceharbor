from __future__ import annotations

import re
from typing import Any, Literal

from worker.config import Settings

PipelineMode = Literal["full", "text_only", "refresh_comments", "refresh_llm"]
LLMInputMode = Literal["auto", "text", "video_text", "frames_text"]
MediaResolution = Literal["low", "medium", "high", "ultra_high"]
_STRING_ITEM_KEYS = ("text", "summary", "title", "content", "label", "value")
_DEFAULT_LIST_LIMIT = 12
_COMMENT_SORTS = {"hot", "new"}
_PIPELINE_MODES = {"text_only", "refresh_comments", "refresh_llm"}
_ANALYSIS_MODES = {"advanced", "economy"}


def coerce_bool(value: Any, default: bool = False) -> bool:
    fallback = bool(default)
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return fallback


def _coerce_optional_float(value: Any) -> float | None:
    return coerce_float(value, None)


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_media_resolution(
    value: Any, *, default: MediaResolution = "medium"
) -> MediaResolution:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"low", "medium", "high", "ultra_high"}:
        return text  # type: ignore[return-value]
    return default


def _normalize_media_resolution_policy(
    value: Any,
    *,
    default: MediaResolution = "medium",
) -> dict[str, MediaResolution]:
    if isinstance(value, dict):
        base = _normalize_media_resolution(value.get("default"), default=default)
        return {
            "default": base,
            "frame": _normalize_media_resolution(value.get("frame"), default=base),
            "image": _normalize_media_resolution(value.get("image"), default=base),
            "pdf": _normalize_media_resolution(value.get("pdf"), default=base),
        }

    base = _normalize_media_resolution(value, default=default)
    return {"default": base, "frame": base, "image": base, "pdf": base}


def _normalize_analysis_mode(value: Any, *, default: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in _ANALYSIS_MODES:
        return text
    return default


def normalize_overrides_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return dict(value)


def override_section(overrides: dict[str, Any], section: str) -> dict[str, Any]:
    value = overrides.get(section)
    if not isinstance(value, dict):
        return {}
    return dict(value)


def _coerce_positive_int(value: Any) -> int | None:
    parsed = coerce_int(value)
    if parsed <= 0:
        return None
    return parsed


def _coerce_timeout_seconds(value: Any, *, default: float) -> float:
    parsed = _coerce_optional_float(value)
    if parsed is None or parsed == 0:
        return default
    return max(0.1, parsed)


def _normalize_comment_sort(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in _COMMENT_SORTS:
        return text
    return None


def default_comment_sort_for_platform(platform: str) -> str:
    if platform == "youtube":
        return "hot"
    return "like"


def build_comments_policy(
    settings: Settings, overrides: dict[str, Any], *, platform: str
) -> dict[str, Any]:
    section = override_section(overrides, "comments")
    top_n = max(1, coerce_int(section.get("top_n"), settings.comments_top_n))
    replies_per_comment = max(
        0,
        coerce_int(section.get("replies_per_comment"), settings.comments_replies_per_comment),
    )
    sort_text = _normalize_comment_sort(section.get("sort"))
    if sort_text is None:
        sort_text = default_comment_sort_for_platform(platform)
    return {
        "top_n": top_n,
        "replies_per_comment": replies_per_comment,
        "sort": sort_text,
    }


def build_frame_policy(settings: Settings, overrides: dict[str, Any]) -> dict[str, Any]:
    section = override_section(overrides, "frames")
    method = str(section.get("method") or "fps").strip().lower()
    if method not in {"fps", "scene"}:
        method = "fps"
    max_frames = max(1, coerce_int(section.get("max_frames"), settings.pipeline_max_frames))
    return {"method": method, "max_frames": max_frames}


def build_llm_policy_section(
    default_model: str,
    section: dict[str, Any],
    *,
    allow_computer_use: bool,
) -> dict[str, Any]:
    model = str(section.get("model") or default_model).strip() or default_model
    temperature = _coerce_optional_float(section.get("temperature"))
    if temperature is not None:
        temperature = min(2.0, max(0.0, temperature))
    max_output_tokens = _coerce_positive_int(section.get("max_output_tokens"))
    max_function_call_rounds = max(0, coerce_int(section.get("max_function_call_rounds"), 2))
    include_thoughts = coerce_bool(section.get("include_thoughts"))
    requested_computer_use = coerce_bool(section.get("enable_computer_use"))
    enable_computer_use = bool(allow_computer_use and requested_computer_use)
    computer_use_require_confirmation = coerce_bool(
        section.get("computer_use_require_confirmation"),
        default=True,
    )
    computer_use_max_steps = max(0, coerce_int(section.get("computer_use_max_steps")))
    computer_use_timeout_seconds = _coerce_timeout_seconds(
        section.get("computer_use_timeout_seconds"),
        default=30.0,
    )
    media_resolution = _normalize_media_resolution_policy(section.get("media_resolution"))
    return {
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "max_function_call_rounds": max_function_call_rounds,
        "include_thoughts": include_thoughts,
        "enable_computer_use": enable_computer_use,
        "computer_use_require_confirmation": computer_use_require_confirmation,
        "computer_use_max_steps": computer_use_max_steps,
        "computer_use_timeout_seconds": computer_use_timeout_seconds,
        "media_resolution": media_resolution,
    }


def build_llm_policy(
    settings: Settings,
    overrides: dict[str, Any],
    *,
    content_type: str | None = None,
) -> dict[str, Any]:
    section = override_section(overrides, "llm")
    speed_priority = coerce_bool(section.get("speed_priority"))
    thinking_level = str(section.get("thinking_level") or "").strip().lower()
    if thinking_level not in {"minimal", "low", "medium", "high"}:
        thinking_level = "low" if speed_priority else "high"
    include_thoughts = coerce_bool(
        section.get("include_thoughts"),
        default=bool(settings.gemini_include_thoughts),
    )
    media_resolution = _normalize_media_resolution_policy(
        section.get("media_resolution"), default="medium"
    )
    normalized_content_type = str(content_type or "video").strip().lower() or "video"
    is_video_content = normalized_content_type == "video"
    raw_stage_section = {}
    raw_stage_value = section.get("raw_stage")
    if isinstance(raw_stage_value, dict):
        raw_stage_section.update(raw_stage_value)
    top_level_raw_stage = override_section(overrides, "raw_stage")
    if top_level_raw_stage:
        raw_stage_section = {**raw_stage_section, **top_level_raw_stage}
    for key in (
        "analysis_mode",
        "video_first",
        "video_input_required",
        "preprocess_enabled",
        "preprocess_model",
        "preprocess_input_mode",
        "review_required",
        "review_model",
        "review_input_mode",
        "primary_input_mode",
    ):
        if key in section and key not in raw_stage_section:
            raw_stage_section[key] = section[key]
    analysis_mode = _normalize_analysis_mode(
        raw_stage_section.get("analysis_mode"),
        default="advanced" if is_video_content else "economy",
    )
    video_first = bool(
        is_video_content and coerce_bool(raw_stage_section.get("video_first"), default=True)
    )
    video_input_required = bool(
        is_video_content
        and coerce_bool(
            raw_stage_section.get("video_input_required"),
            default=video_first,
        )
    )
    preprocess_enabled = bool(
        is_video_content
        and coerce_bool(
            raw_stage_section.get("preprocess_enabled"),
            default=analysis_mode == "advanced",
        )
    )
    review_required = bool(
        is_video_content
        and coerce_bool(
            raw_stage_section.get("review_required"),
            default=analysis_mode == "advanced",
        )
    )
    preprocess_model = (
        str(raw_stage_section.get("preprocess_model") or settings.gemini_fast_model).strip()
        or settings.gemini_fast_model
    )
    preprocess_input_mode = normalize_llm_input_mode(
        raw_stage_section.get("preprocess_input_mode") or "text"
    )
    primary_input_mode = normalize_llm_input_mode(
        raw_stage_section.get("primary_input_mode") or "video_text"
    )
    review_model = (
        str(raw_stage_section.get("review_model") or settings.gemini_model).strip()
        or settings.gemini_model
    )
    review_input_mode = normalize_llm_input_mode(
        raw_stage_section.get("review_input_mode") or "video_text"
    )
    section = {
        **section,
        "include_thoughts": include_thoughts,
        "media_resolution": media_resolution,
        "analysis_mode": analysis_mode,
    }

    default_model = settings.gemini_model
    if speed_priority and "model" not in section:
        default_model = settings.gemini_fast_model

    outline_section = {**section, **override_section(overrides, "llm_outline")}
    digest_section = {**section, **override_section(overrides, "llm_digest")}

    outline_default_model = settings.gemini_outline_model
    if speed_priority and "model" not in outline_section:
        outline_default_model = settings.gemini_fast_model
    digest_default_model = settings.gemini_digest_model
    if speed_priority and "model" not in digest_section:
        digest_default_model = settings.gemini_fast_model

    allow_computer_use = bool(settings.gemini_computer_use_enabled)
    outline = build_llm_policy_section(
        outline_default_model,
        outline_section,
        allow_computer_use=allow_computer_use,
    )
    digest = build_llm_policy_section(
        digest_default_model,
        digest_section,
        allow_computer_use=allow_computer_use,
    )
    model = str(section.get("model") or default_model).strip() or default_model
    temperature = _coerce_optional_float(section.get("temperature"))
    if temperature is not None:
        temperature = min(2.0, max(0.0, temperature))
    max_output_tokens = _coerce_positive_int(section.get("max_output_tokens"))
    max_function_call_rounds = max(0, coerce_int(section.get("max_function_call_rounds"), 2))
    requested_computer_use = coerce_bool(
        section.get("enable_computer_use"),
        default=allow_computer_use,
    )
    enable_computer_use = bool(allow_computer_use and requested_computer_use)
    computer_use_require_confirmation = coerce_bool(
        section.get("computer_use_require_confirmation"),
        default=bool(settings.gemini_computer_use_require_confirmation),
    )
    computer_use_max_steps = max(
        0,
        coerce_int(
            section.get("computer_use_max_steps"), int(settings.gemini_computer_use_max_steps)
        ),
    )
    computer_use_timeout_seconds = _coerce_timeout_seconds(
        section.get("computer_use_timeout_seconds"),
        default=float(settings.gemini_computer_use_timeout_seconds),
    )
    return {
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "max_function_call_rounds": max_function_call_rounds,
        "speed_priority": speed_priority,
        "thinking_level": thinking_level,
        "analysis_mode": analysis_mode,
        "include_thoughts": include_thoughts,
        "enable_computer_use": enable_computer_use,
        "computer_use_require_confirmation": computer_use_require_confirmation,
        "computer_use_max_steps": computer_use_max_steps,
        "computer_use_timeout_seconds": computer_use_timeout_seconds,
        "media_resolution": media_resolution,
        "raw_stage": {
            "analysis_mode": analysis_mode,
            "content_type": normalized_content_type,
            "video_first": video_first,
            "video_input_required": video_input_required,
            "preprocess_enabled": preprocess_enabled,
            "preprocess_model": preprocess_model,
            "preprocess_input_mode": preprocess_input_mode,
            "primary_input_mode": primary_input_mode,
            "review_required": review_required,
            "review_model": review_model,
            "review_input_mode": review_input_mode,
        },
        "outline": outline,
        "digest": digest,
    }


def apply_comments_policy(
    comments_payload: dict[str, Any],
    *,
    policy: dict[str, Any],
    platform: str,
) -> dict[str, Any]:
    top_n = max(1, coerce_int(policy.get("top_n"), coerce_int(comments_payload.get("top_n"), 10)))
    replies_per_comment = max(
        0,
        coerce_int(
            policy.get("replies_per_comment"),
            coerce_int(comments_payload.get("replies_per_comment"), 10),
        ),
    )
    requested_sort = _normalize_comment_sort(policy.get("sort"))
    if requested_sort is None:
        raw_payload_sort = comments_payload.get("sort")
        requested_sort = "" if raw_payload_sort is None else str(raw_payload_sort).strip().lower()
    if not requested_sort:
        requested_sort = default_comment_sort_for_platform(platform)

    top_comments: list[dict[str, Any]] = []
    raw_top_comments = comments_payload.get("top_comments")
    if isinstance(raw_top_comments, list):
        for item in raw_top_comments:
            if isinstance(item, dict):
                top_comments.append(dict(item))

    if requested_sort == "new":
        top_comments.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
    else:
        top_comments.sort(key=lambda item: coerce_int(item.get("like_count"), 0), reverse=True)

    normalized_comments: list[dict[str, Any]] = []
    replies_index: dict[str, list[dict[str, Any]]] = {}
    for item in top_comments[:top_n]:
        replies: list[dict[str, Any]] = []
        raw_replies = item.get("replies")
        if isinstance(raw_replies, list):
            for reply in raw_replies[:replies_per_comment]:
                if isinstance(reply, dict):
                    replies.append(dict(reply))
        normalized_item = {**item, "replies": replies}
        normalized_comments.append(normalized_item)
        comment_id = str(normalized_item.get("comment_id") or "").strip()
        if comment_id:
            replies_index[comment_id] = replies

    return {
        **comments_payload,
        "sort": requested_sort,
        "top_n": top_n,
        "replies_per_comment": replies_per_comment,
        "top_comments": normalized_comments,
        "replies": replies_index,
    }


def normalize_pipeline_mode(value: Any) -> PipelineMode:
    text = "" if value is None else str(value).strip().lower()
    if text == "full":
        return "full"
    if text in _PIPELINE_MODES:
        return text  # type: ignore[return-value]
    return "full"


def normalize_llm_input_mode(value: Any) -> LLMInputMode:
    text = str(value or "auto").strip().lower()
    if text in {"auto", "text", "video_text", "frames_text"}:
        return text  # type: ignore[return-value]
    return "auto"


def frame_paths_from_frames(frames: list[dict[str, Any]], *, limit: int = 8) -> list[str]:
    paths: list[str] = []
    for item in frames:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path:
            continue
        if path in paths:
            continue
        paths.append(path)
        if len(paths) >= limit:
            break
    return paths


def llm_media_input_dimension(state: dict[str, Any]) -> dict[str, Any]:
    media_path = str(state.get("media_path") or "").strip()
    frames = list(state.get("frames") or [])
    frame_paths = frame_paths_from_frames(frames, limit=200)
    return {
        "video_available": bool(media_path),
        "frame_count": len(frame_paths),
    }


def refresh_llm_media_input_dimension(state: dict[str, Any]) -> None:
    state["llm_media_input"] = llm_media_input_dimension(state)


def _coerce_str_item(item: Any) -> str | None:
    if isinstance(item, str):
        text = item.strip()
        return text or None
    if isinstance(item, dict):
        for key in _STRING_ITEM_KEYS:
            candidate = item.get(key)
            if not isinstance(candidate, str):
                continue
            text = candidate.strip()
            if text:
                return text
        return None
    if isinstance(item, (int, float)):
        text = str(item).strip()
        return text or None
    return None


def coerce_str_list(values: Any, *, limit: int | None = None) -> list[str]:
    effective_limit = _DEFAULT_LIST_LIMIT if limit is None else limit
    if not isinstance(values, list) or effective_limit <= 0:
        return []
    normalized: list[str] = []
    for item in values:
        text = _coerce_str_item(item)
        if text is None:
            continue
        normalized.append(text)
        if len(normalized) == effective_limit:
            break
    return normalized


def dedupe_keep_order(values: list[str], *, limit: int | None = None) -> list[str]:
    effective_limit = _DEFAULT_LIST_LIMIT if limit is None else limit
    if effective_limit <= 0:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
        if len(result) == effective_limit:
            break
    return result


def extract_json_object(text: str) -> str:
    content = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", content, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        return content[start : end + 1]
    return content


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def outline_is_chinese(payload: dict[str, Any]) -> bool:
    candidates: list[str] = [str(payload.get("title") or "")]
    chapters = payload.get("chapters")
    if isinstance(chapters, list):
        for chapter in chapters[:4]:
            if not isinstance(chapter, dict):
                continue
            candidates.append(str(chapter.get("title") or ""))
            candidates.append(str(chapter.get("summary") or ""))
    text = " ".join(item for item in candidates if item).strip()
    return contains_cjk(text)


def digest_is_chinese(payload: dict[str, Any]) -> bool:
    candidates: list[str] = [str(payload.get("title") or ""), str(payload.get("summary") or "")]
    for key in ("tldr", "highlights", "action_items"):
        values = payload.get(key)
        if isinstance(values, list):
            candidates.extend(str(item) for item in values[:4])
    text = " ".join(item for item in candidates if item).strip()
    return contains_cjk(text)
