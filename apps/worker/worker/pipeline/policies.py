from __future__ import annotations

from typing import Any

from worker.config import Settings
from worker.pipeline.runner_policies import (
    apply_comments_policy,
    build_comments_policy,
    build_frame_policy,
    build_llm_policy_section,
    coerce_bool,
    coerce_float,
    coerce_int,
    coerce_str_list,
    dedupe_keep_order,
    default_comment_sort_for_platform,
    digest_is_chinese,
    extract_json_object,
    frame_paths_from_frames,
    llm_media_input_dimension,
    normalize_llm_input_mode,
    normalize_overrides_payload,
    normalize_pipeline_mode,
    outline_is_chinese,
    override_section,
    refresh_llm_media_input_dimension,
)
from worker.pipeline.runner_policies import (
    build_llm_policy as _build_llm_policy,
)
from worker.pipeline.types import RetryCategory

__all__ = [
    "apply_comments_policy",
    "build_comments_policy",
    "build_frame_policy",
    "build_llm_policy",
    "build_llm_policy_section",
    "build_retry_policy",
    "classify_error",
    "coerce_bool",
    "coerce_float",
    "coerce_int",
    "coerce_str_list",
    "dedupe_keep_order",
    "default_comment_sort_for_platform",
    "digest_is_chinese",
    "extract_json_object",
    "frame_paths_from_frames",
    "llm_media_input_dimension",
    "normalize_llm_input_mode",
    "normalize_overrides_payload",
    "normalize_pipeline_mode",
    "outline_is_chinese",
    "override_section",
    "pipeline_llm_fail_on_provider_error",
    "pipeline_llm_hard_required",
    "pipeline_llm_max_retries",
    "refresh_llm_media_input_dimension",
    "retry_delay_seconds",
]


_RATE_LIMIT_ERROR_TOKENS = ("429", "rate limit", "too many request")
_AUTH_ERROR_TOKENS = (
    "401",
    "403",
    "unauthorized",
    "forbidden",
    "invalid api key",
    "authentication",
    "permission denied",
    "api_key_missing",
)
_TRANSIENT_ERROR_TOKENS = (
    "timeout",
    "timed out",
    "econn",
    "connection reset",
    "network",
    "temporary",
    "service unavailable",
    "non_zero_exit",
    "provider_unavailable",
    "gemini_error",
    "provider_error",
    "llm_provider",
    "llm_output_invalid",
)


def _normalized_error_parts(*values: str | None) -> tuple[str, ...]:
    parts: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip().lower()
        if normalized:
            parts.append(normalized)
    if len(parts) > 1:
        parts.append(" ".join(parts))
    return tuple(parts)


def _contains_error_token(parts: tuple[str, ...], tokens: tuple[str, ...]) -> bool:
    return any(token in part for part in parts for token in tokens)


def _coerce_non_negative_backoff(value: Any, default: float) -> float:
    parsed = coerce_float(value, default)
    if parsed is None:
        return max(0.0, default)
    return max(0.0, parsed)


def pipeline_llm_hard_required(
    settings: Settings, llm_policy: dict[str, Any] | None = None
) -> bool:
    policy = dict(llm_policy or {})
    if "hard_required" in policy:
        return coerce_bool(policy.get("hard_required"), default=True)
    if not hasattr(settings, "pipeline_llm_hard_required"):
        return True
    raw_value = settings.pipeline_llm_hard_required
    return coerce_bool(raw_value, default=True)


def pipeline_llm_fail_on_provider_error(
    settings: Settings,
    llm_policy: dict[str, Any] | None = None,
) -> bool:
    policy = dict(llm_policy or {})
    if "fail_on_provider_error" in policy:
        return coerce_bool(policy.get("fail_on_provider_error"), default=True)
    if not hasattr(settings, "pipeline_llm_fail_on_provider_error"):
        return True
    raw_value = settings.pipeline_llm_fail_on_provider_error
    return coerce_bool(raw_value, default=True)


def pipeline_llm_max_retries(
    settings: Settings, llm_policy: dict[str, Any] | None = None
) -> int | None:
    policy = dict(llm_policy or {})
    if "max_retries" in policy:
        try:
            retries = int(policy.get("max_retries"))
        except (TypeError, ValueError):
            return None
        return retries if retries >= 0 else None

    raw = getattr(settings, "pipeline_llm_max_retries", None)
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = 0
    return max(0, parsed)


def build_llm_policy(
    settings: Settings,
    overrides: dict[str, Any],
    *,
    content_type: str | None = None,
) -> dict[str, Any]:
    section = override_section(overrides, "llm")
    policy = _build_llm_policy(settings, overrides, content_type=content_type)
    policy["hard_required"] = pipeline_llm_hard_required(settings, section)
    policy["fail_on_provider_error"] = pipeline_llm_fail_on_provider_error(settings, section)
    policy["max_retries"] = pipeline_llm_max_retries(settings, section)
    return policy


def build_retry_policy(
    settings: Settings,
    *,
    step_name: str,
    llm_policy: dict[str, Any] | None = None,
) -> dict[RetryCategory, dict[str, float | int]]:
    base_retries = max(0, coerce_int(getattr(settings, "pipeline_retry_attempts", None), 2))
    base_backoff = _coerce_non_negative_backoff(
        getattr(settings, "pipeline_retry_backoff_seconds", None),
        1.0,
    )

    policy: dict[RetryCategory, dict[str, float | int]] = {
        "transient": {
            "retries": max(
                0,
                coerce_int(
                    getattr(settings, "pipeline_retry_transient_attempts", None), base_retries
                ),
            ),
            "backoff": max(
                0.0,
                coerce_float(
                    getattr(settings, "pipeline_retry_transient_backoff_seconds", None),
                    base_backoff,
                ),
            ),
            "max_backoff": max(
                0.0,
                coerce_float(
                    getattr(settings, "pipeline_retry_transient_max_backoff_seconds", None),
                    base_backoff * 8,
                ),
            ),
        },
        "rate_limit": {
            "retries": max(
                0,
                coerce_int(
                    getattr(settings, "pipeline_retry_rate_limit_attempts", None),
                    max(base_retries, 3),
                ),
            ),
            "backoff": max(
                0.0,
                coerce_float(
                    getattr(settings, "pipeline_retry_rate_limit_backoff_seconds", None),
                    base_backoff * 2,
                ),
            ),
            "max_backoff": max(
                0.0,
                coerce_float(
                    getattr(settings, "pipeline_retry_rate_limit_max_backoff_seconds", None),
                    max(base_backoff * 16, 1.0),
                ),
            ),
        },
        "auth": {
            "retries": max(
                0,
                coerce_int(getattr(settings, "pipeline_retry_auth_attempts", None)),
            ),
            "backoff": max(
                0.0,
                coerce_float(
                    getattr(settings, "pipeline_retry_auth_backoff_seconds", None), base_backoff
                ),
            ),
            "max_backoff": max(
                0.0,
                coerce_float(
                    getattr(settings, "pipeline_retry_auth_max_backoff_seconds", None),
                    base_backoff * 2,
                ),
            ),
        },
        "fatal": {
            "retries": max(0, coerce_int(getattr(settings, "pipeline_retry_fatal_attempts", None))),
            "backoff": 0.0,
            "max_backoff": 0.0,
        },
    }

    if step_name in {"llm_outline", "llm_digest"}:
        llm_retries = pipeline_llm_max_retries(settings, llm_policy)
        if llm_retries is not None:
            policy["transient"]["retries"] = llm_retries
            policy["rate_limit"]["retries"] = llm_retries
            policy["auth"]["retries"] = llm_retries
            policy["fatal"]["retries"] = llm_retries

    return policy


def retry_delay_seconds(policy: dict[str, float | int], retries_used: int) -> float:
    backoff = max(0.0, float(policy.get("backoff", 0.0)))
    if backoff == 0:
        return 0.0
    max_backoff = max(0.0, float(policy.get("max_backoff", backoff)))
    delay = backoff * (2 ** max(0, retries_used))
    return min(delay, max_backoff)


def classify_error(reason: str | None, error: str | None) -> RetryCategory:
    parts = _normalized_error_parts(reason, error)

    if _contains_error_token(parts, _RATE_LIMIT_ERROR_TOKENS):
        return "rate_limit"

    if _contains_error_token(parts, _AUTH_ERROR_TOKENS):
        return "auth"

    if _contains_error_token(parts, _TRANSIENT_ERROR_TOKENS):
        return "transient"

    return "fatal"
