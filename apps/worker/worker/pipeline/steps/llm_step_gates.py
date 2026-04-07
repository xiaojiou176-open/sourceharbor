from __future__ import annotations

from typing import Any

from worker.pipeline.policies import coerce_int
from worker.pipeline.types import PipelineContext


def _semantic_len(text: str) -> int:
    content = "".join(ch for ch in str(text or "").strip() if ch.isalnum())
    return len(content)


def _has_meaningful_line(items: list[str], *, min_len: int) -> bool:
    return any(_semantic_len(item) >= min_len for item in items)


def _outline_quality_ok(payload: dict[str, Any]) -> bool:
    highlights = [str(item) for item in payload.get("highlights") or [] if str(item).strip()]
    if not _has_meaningful_line(highlights, min_len=8):
        return False
    chapters = payload.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return False
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        summary_len = _semantic_len(str(chapter.get("summary") or ""))
        bullets = [str(item) for item in chapter.get("bullets") or [] if str(item).strip()]
        if summary_len >= 10 or _has_meaningful_line(bullets, min_len=8):
            return True
    return False


def _digest_quality_ok(payload: dict[str, Any]) -> bool:
    summary = str(payload.get("summary") or "")
    if _semantic_len(summary) < 20:
        return False
    highlights = [str(item) for item in payload.get("highlights") or [] if str(item).strip()]
    return _has_meaningful_line(highlights, min_len=8)


def _thinking_level_from_policy(llm_policy: dict[str, Any]) -> str:
    speed_priority = bool(llm_policy.get("speed_priority"))
    raw_value = llm_policy.get("thinking_level")
    if raw_value is None:
        return "low" if speed_priority else "high"

    raw = str(raw_value).strip().lower()
    if not raw:
        return "low" if speed_priority else "high"
    if raw == "minimal":
        return "low"
    if raw == "low":
        return "low"
    if raw == "medium":
        return "medium"
    return "high"


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _max_function_call_rounds(llm_policy: dict[str, Any], section_policy: dict[str, Any]) -> int:
    if "max_function_call_rounds" in section_policy:
        raw = section_policy.get("max_function_call_rounds")
    else:
        raw = llm_policy.get("max_function_call_rounds")
    parsed = coerce_int(raw, 2)
    return max(0, parsed)


def _include_thoughts_from_policy(
    ctx: PipelineContext,
    llm_policy: dict[str, Any],
    section_policy: dict[str, Any],
) -> bool:
    default_value = bool(ctx.settings.gemini_include_thoughts)
    if "include_thoughts" in section_policy:
        return _coerce_bool(section_policy.get("include_thoughts"), default=default_value)
    if "include_thoughts" in llm_policy:
        return _coerce_bool(llm_policy.get("include_thoughts"), default=default_value)
    return default_value


def _media_resolution_from_policy(
    llm_policy: dict[str, Any],
    section_policy: dict[str, Any],
) -> dict[str, Any]:
    raw = section_policy.get("media_resolution", llm_policy.get("media_resolution"))
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        return {"default": raw.strip().lower()}
    return {}


def build_computer_use_options(
    ctx: PipelineContext,
    llm_policy: dict[str, Any],
    section_policy: dict[str, Any],
) -> dict[str, Any]:
    enabled_default = bool(ctx.settings.gemini_computer_use_enabled)
    require_confirmation_default = bool(ctx.settings.gemini_computer_use_require_confirmation)
    max_steps_default = max(0, int(ctx.settings.gemini_computer_use_max_steps))
    timeout_default = max(0.1, float(ctx.settings.gemini_computer_use_timeout_seconds))

    requested_computer_use = _coerce_bool(
        section_policy.get("enable_computer_use", llm_policy.get("enable_computer_use")),
        default=enabled_default,
    )
    enable_computer_use = bool(enabled_default and requested_computer_use)
    require_confirmation = _coerce_bool(
        section_policy.get(
            "computer_use_require_confirmation",
            llm_policy.get("computer_use_require_confirmation"),
        ),
        default=require_confirmation_default,
    )
    max_steps = coerce_int(
        section_policy.get("computer_use_max_steps", llm_policy.get("computer_use_max_steps")),
        max_steps_default,
    )
    timeout_raw = section_policy.get(
        "computer_use_timeout_seconds",
        llm_policy.get("computer_use_timeout_seconds"),
    )
    try:
        timeout_seconds = float(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = None
    if timeout_seconds is None or timeout_seconds == 0:
        timeout_seconds = timeout_default

    return {
        "enable_computer_use": bool(enable_computer_use),
        "computer_use_require_confirmation": bool(require_confirmation),
        "computer_use_max_steps": max(0, int(max_steps)),
        "computer_use_timeout_seconds": max(0.1, timeout_seconds),
    }
