from __future__ import annotations

import hashlib
import mimetypes
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

_ALLOWED_MEDIA_RESOLUTION = {"low", "medium", "high", "ultra_high"}
ComputerUseHandler = Callable[..., dict[str, Any]]


def _part_is_thought(part: Any) -> bool:
    thought_flag = getattr(part, "thought", None)
    if isinstance(thought_flag, bool):
        return thought_flag
    if isinstance(part, dict):
        raw = part.get("thought")
        if isinstance(raw, bool):
            return raw
    return False


def _extract_response_text(response: Any) -> str | None:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list):
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None)
            if not isinstance(parts, list):
                continue
            chunks: list[str] = []
            for part in parts:
                if _part_is_thought(part):
                    continue
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    chunks.append(part_text.strip())
            if chunks:
                return "\n".join(chunks)
    return None


def _normalize_media_resolution(value: Any, *, default: str = "medium") -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in _ALLOWED_MEDIA_RESOLUTION:
        return text
    return default


def _normalize_media_resolution_policy(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        base = _normalize_media_resolution(value.get("default"), default="medium")
        return {
            "default": base,
            "frame": _normalize_media_resolution(value.get("frame"), default=base),
            "image": _normalize_media_resolution(value.get("image"), default=base),
            "pdf": _normalize_media_resolution(value.get("pdf"), default=base),
        }
    base = _normalize_media_resolution(value, default="medium")
    return {"default": base, "frame": base, "image": base, "pdf": base}


def _part_media_resolution(
    policy: dict[str, str], *, mime_type: str, kind: str | None = None
) -> str:
    if kind and kind in policy:
        return policy[kind]
    mime = (mime_type or "").strip().lower()
    if mime.startswith("image/"):
        return policy.get("image", policy["default"])
    if mime == "application/pdf":
        return policy.get("pdf", policy["default"])
    return policy["default"]


def _part_from_bytes(
    genai_types: Any, *, data: bytes, mime_type: str, media_resolution: str
) -> Any:
    part_cls = getattr(genai_types, "Part", None)
    if part_cls is None:
        return {"mime_type": mime_type, "data": data, "media_resolution": media_resolution}

    normalized_resolution = _normalize_media_resolution(media_resolution)
    enum_value = None
    enum_cls = getattr(genai_types, "PartMediaResolutionLevel", None)
    if enum_cls is not None:
        enum_name = f"MEDIA_RESOLUTION_{normalized_resolution.upper()}"
        enum_value = getattr(enum_cls, enum_name, None)

    for kwargs in (
        {
            "data": data,
            "mime_type": mime_type,
            "media_resolution": enum_value,
        }
        if enum_value is not None
        else None,
        {"data": data, "mime_type": mime_type, "media_resolution": normalized_resolution},
        {"data": data, "mime_type": mime_type},
    ):
        if kwargs is None:
            continue
        try:
            return part_cls.from_bytes(**kwargs)
        except Exception:
            continue
    return {"mime_type": mime_type, "data": data, "media_resolution": normalized_resolution}


def _build_frame_parts(
    genai_types: Any,
    frame_paths: list[str],
    *,
    limit: int,
    media_resolution_policy: dict[str, str],
) -> list[Any]:
    parts: list[Any] = []
    for frame_path in frame_paths[:limit]:
        path = Path(frame_path)
        if not path.exists() or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if not data:
            continue
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        media_resolution = _part_media_resolution(
            media_resolution_policy,
            mime_type=mime_type,
            kind="frame",
        )
        parts.append(
            _part_from_bytes(
                genai_types,
                data=data,
                mime_type=mime_type,
                media_resolution=media_resolution,
            )
        )
    return parts


def _thinking_config(genai_types: Any, *, thinking_level: str, include_thoughts: bool) -> Any:
    level = (thinking_level or "high").strip().lower()
    if level not in {"minimal", "low", "medium", "high"}:
        level = "high"
    return genai_types.ThinkingConfig(
        thinking_level=level.upper(),
        include_thoughts=include_thoughts,
    )


def _cache_meta_default(*, bypass_reason: str | None = None) -> dict[str, Any]:
    return {
        "cache_hit": False,
        "cache_recreate": False,
        "cache_bypass_reason": bypass_reason,
    }


def _is_cache_error(exc: Exception) -> bool:
    message = str(exc or "").strip().lower()
    if not message:
        return False
    return any(
        token in message
        for token in (
            "cached_content",
            "cache",
            "not found",
            "404",
            "invalid argument",
            "resource_exhausted",
            "failed_precondition",
        )
    )


def _build_computer_use_tool(genai_types: Any) -> Any:
    tool_cls = getattr(genai_types, "Tool", None)
    if tool_cls is not None:
        computer_use_cls = getattr(genai_types, "ComputerUse", None)
        if computer_use_cls is not None:
            try:
                return tool_cls(computer_use=computer_use_cls())
            except Exception:
                pass
        for payload in (
            {"computer_use": {}},
            {"computer_use": {"environment": "BROWSER"}},
            {"computer_use": True},
        ):
            try:
                return tool_cls(**payload)
            except Exception:
                continue
    return {"computer_use": {}}


def execute_computer_use_action(
    handler: ComputerUseHandler | None,
    *,
    args: dict[str, Any],
    require_confirmation: bool,
    confirmed: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    if handler is None:
        return {
            "status": "blocked",
            "response": {"error": "computer_use_handler_missing"},
        }
    if require_confirmation and not confirmed:
        return {
            "status": "blocked",
            "response": {"error": "computer_use_confirmation_required"},
        }

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(handler, **args)
        try:
            response = future.result(timeout=max(0.1, timeout_seconds))
        except FutureTimeoutError:
            return {
                "status": "failed",
                "response": {"error": "computer_use_timeout"},
            }
        except Exception as exc:
            return {
                "status": "failed",
                "response": {
                    "error": "computer_use_execution_failed",
                    "detail": str(exc),
                },
            }
    if not isinstance(response, dict):
        response = {"result": response}
    return {"status": "ok", "response": response}


def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, list):
        return calls
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None)
        if not isinstance(parts, list):
            continue
        for part in parts:
            function_call = getattr(part, "function_call", None)
            if function_call is None and isinstance(part, dict):
                function_call = part.get("function_call")
            if function_call is None:
                continue

            if isinstance(function_call, dict):
                name = str(function_call.get("name") or "").strip()
                args = function_call.get("args")
            else:
                name = str(getattr(function_call, "name", "") or "").strip()
                args = getattr(function_call, "args", None)
            if not name:
                continue

            if not isinstance(args, dict):
                args = {}
            calls.append({"name": name, "args": dict(args)})
    return calls


def _execute_function_call(
    allowed_tools: dict[str, Callable[..., dict[str, Any]]],
    *,
    tool_name: str,
    args: dict[str, Any],
    computer_use_handler: ComputerUseHandler | None,
    computer_use_require_confirmation: bool,
    computer_use_confirmed: bool,
    computer_use_timeout_seconds: float,
    computer_use_step_limit: int,
    computer_use_steps_used: int,
) -> dict[str, Any]:
    if tool_name == "computer_use":
        if computer_use_step_limit >= 0 and computer_use_steps_used >= computer_use_step_limit:
            return {
                "name": tool_name,
                "status": "blocked",
                "response": {"error": "computer_use_max_steps_reached"},
            }
        result = execute_computer_use_action(
            computer_use_handler,
            args=args,
            require_confirmation=computer_use_require_confirmation,
            confirmed=computer_use_confirmed,
            timeout_seconds=computer_use_timeout_seconds,
        )
        return {"name": tool_name, **result}

    tool = allowed_tools.get(tool_name)
    if tool is None:
        return {
            "name": tool_name,
            "status": "blocked",
            "response": {"error": f"tool_not_allowed:{tool_name}"},
        }
    try:
        response = tool(**args)
    except Exception as exc:
        return {
            "name": tool_name,
            "status": "failed",
            "response": {"error": f"tool_execution_failed:{tool_name}", "detail": str(exc)},
        }
    if not isinstance(response, dict):
        response = {"result": response}
    return {"name": tool_name, "status": "ok", "response": response}


def _extract_primary_candidate_content(response: Any) -> Any | None:
    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list) and candidates:
        return getattr(candidates[0], "content", None)
    return None


def _build_function_response_part(genai_types: Any, *, name: str, payload: dict[str, Any]) -> Any:
    part_cls = getattr(genai_types, "Part", None)
    if part_cls is not None:
        try:
            return part_cls.from_function_response(
                name=name,
                response=payload,
            )
        except Exception:
            pass
    return {"function_response": {"name": name, "response": payload}}


def _build_function_response_content(genai_types: Any, responses: list[dict[str, Any]]) -> Any:
    parts = [
        _build_function_response_part(genai_types, name=item["name"], payload=item["response"])
        for item in responses
    ]

    content_cls = getattr(genai_types, "Content", None)
    if content_cls is not None:
        for role in ("tool", "user"):
            try:
                return content_cls(role=role, parts=parts)
            except Exception:
                continue
    return {"role": "tool", "parts": parts}


def _collect_thought_metadata(response: Any) -> dict[str, Any]:
    thought_count = 0
    thought_signatures: list[str] = []

    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list):
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None)
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not _part_is_thought(part):
                    continue
                thought_count += 1
                signature = getattr(part, "signature", None)
                if signature is None:
                    signature = getattr(part, "thought_signature", None)
                if isinstance(signature, bytes):
                    thought_signatures.append(signature.hex())
                elif isinstance(signature, str) and signature.strip():
                    thought_signatures.append(signature.strip())
                else:
                    text = getattr(part, "text", None)
                    if isinstance(text, str) and text.strip():
                        thought_signatures.append(
                            hashlib.sha256(
                                text.strip().encode("utf-8", errors="ignore")
                            ).hexdigest()
                        )

    usage = getattr(response, "usage_metadata", None)
    usage_payload: dict[str, Any] = {}
    if usage is not None:
        for key in (
            "prompt_token_count",
            "candidates_token_count",
            "total_token_count",
            "thoughts_token_count",
        ):
            value = getattr(usage, key, None)
            if isinstance(value, int):
                usage_payload[key] = value

    deduped_signatures = list(dict.fromkeys(thought_signatures))
    signature_digest = ""
    if deduped_signatures:
        signature_digest = hashlib.sha256(
            "|".join(deduped_signatures).encode("utf-8", errors="ignore")
        ).hexdigest()

    return {
        "thought_count": thought_count,
        "thought_signatures": deduped_signatures,
        "thought_signature_digest": signature_digest or None,
        "usage": usage_payload,
    }


def _extract_finish_reason(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, list) or not candidates:
        return None
    first = candidates[0]
    raw = getattr(first, "finish_reason", None)
    if raw is None and isinstance(first, dict):
        raw = first.get("finish_reason")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _response_is_safety_blocked(response: Any) -> bool:
    reason = (_extract_finish_reason(response) or "").upper()
    if "SAFETY" in reason:
        return True
    candidates = getattr(response, "candidates", None)
    if isinstance(candidates, list):
        for candidate in candidates:
            ratings = getattr(candidate, "safety_ratings", None)
            if ratings is None and isinstance(candidate, dict):
                ratings = candidate.get("safety_ratings")
            if isinstance(ratings, list) and ratings:
                return True
    return False


def classify_gemini_exception(exc: Exception) -> tuple[str, str | None, int | None]:
    text = str(exc or "").strip()
    lower = text.lower()
    status_match = re.search(r"\b(?:status|code)\s*[:=]?\s*(\d{3})\b", lower)
    http_status = int(status_match.group(1)) if status_match else None

    if "api key" in lower or "permission" in lower or "unauth" in lower or "forbidden" in lower:
        return "llm_auth_error", "auth", http_status
    if "quota" in lower or "resource_exhausted" in lower:
        return "llm_quota_exceeded", "quota", http_status
    if "429" in lower or "rate limit" in lower:
        return "llm_rate_limited", "transient", http_status
    if "safety" in lower or "blocked" in lower:
        return "llm_safety_blocked", "policy", http_status
    if "invalid argument" in lower or "400" in lower or "bad request" in lower:
        return "llm_invalid_request", "request", http_status
    if "timeout" in lower or "deadline" in lower:
        return "llm_timeout", "timeout", http_status
    if "503" in lower or "502" in lower or "500" in lower or "internal" in lower:
        return "llm_upstream_5xx", "transient", http_status
    if "connection" in lower or "network" in lower or "dns" in lower:
        return "llm_transport_error", "transient", http_status
    return "llm_unknown_error", None, http_status
