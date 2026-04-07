from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, unquote
from uuid import UUID

ApiCall = Callable[..., dict[str, Any]]

_DEFAULT_MAX_BASE64_BYTES = 2 * 1024 * 1024
_ERROR_VALUE_HASH_INPUT_LIMIT = 4096
_WORKFLOW_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)\b((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+"),
    re.compile(r'(?i)(["\'](?:api[_-]?key|token|secret|password)["\']\s*:\s*["\'])[^"\']+'),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
]


def _env_positive_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


DEFAULT_MAX_BASE64_BYTES = _env_positive_int(
    "SOURCE_HARBOR_MCP_MAX_BASE64_BYTES", _DEFAULT_MAX_BASE64_BYTES
)


def is_error_payload(payload: dict[str, Any]) -> bool:
    return {"code", "message", "details"}.issubset(payload.keys())


def to_optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def to_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_optional_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def to_optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def to_optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse_bounded_int(
    value: Any,
    *,
    field: str,
    min_value: int | None = None,
    max_value: int | None = None,
    required: bool = False,
) -> tuple[int | None, str | None]:
    if value is None:
        if required:
            return None, f"{field} is required"
        return None, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, f"{field} must be an integer"
    if min_value is not None and value < min_value:
        return None, f"{field} must be >= {min_value}"
    if max_value is not None and value > max_value:
        return None, f"{field} must be <= {max_value}"
    return value, None


def parse_bool(value: Any, *, field: str, required: bool = False) -> tuple[bool | None, str | None]:
    if value is None:
        if required:
            return None, f"{field} is required"
        return None, None
    if not isinstance(value, bool):
        return None, f"{field} must be a boolean"
    return value, None


def invalid_argument(
    message: str,
    *,
    method: str,
    path: str,
    field: str | None = None,
    value: Any | None = None,
) -> dict[str, Any]:
    details: dict[str, Any] = {"method": method, "path": path}
    if field is not None:
        details["field"] = field
    if value is not None:
        details["value"] = _summarize_invalid_value(value)
    return {
        "code": "INVALID_ARGUMENT",
        "message": message,
        "details": details,
    }


def sanitize_error_payload(payload: dict[str, Any]) -> dict[str, Any]:
    code = to_optional_str(payload.get("code")) or "UPSTREAM_ERROR"
    message_text = _stringify_invalid_value(payload.get("message"))
    message = _redact_sensitive_text(message_text).strip() or "Upstream request failed."
    details = _normalize_error_details(payload.get("details"))
    return {
        "code": code,
        "message": message,
        "details": details,
    }


def _stringify_invalid_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            return repr(value)
    return str(value)


def _summarize_invalid_value(value: Any) -> str:
    text = _stringify_invalid_value(value)
    limited_text = text[:_ERROR_VALUE_HASH_INPUT_LIMIT]
    digest = hashlib.sha256(limited_text.encode("utf-8", errors="replace")).hexdigest()[:12]
    return (
        f"<redacted type={type(value).__name__} len={len(text)} "
        f"hash_input={len(limited_text)} sha256={digest}>"
    )


def _redact_sensitive_text(value: str) -> str:
    text = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        text = pattern.sub(
            lambda m: f"{m.group(1)}[REDACTED]" if m.groups() else "[REDACTED]", text
        )
    return text


def _normalize_error_details(raw_details: Any) -> dict[str, Any]:
    source = raw_details if isinstance(raw_details, dict) else {}
    details: dict[str, Any] = {}
    method = to_optional_str(source.get("method"))
    if method is not None:
        details["method"] = method
    path = to_optional_str(source.get("path"))
    if path is not None:
        details["path"] = path
    field = to_optional_str(source.get("field"))
    if field is not None:
        details["field"] = field
    status_code = source.get("status_code")
    if isinstance(status_code, int) and not isinstance(status_code, bool):
        details["status_code"] = status_code

    value = source.get("value")
    if value is not None:
        details["value"] = _summarize_invalid_value(value)
    for key in ("error", "body", "body_preview"):
        if source.get(key) is None:
            continue
        details[key] = _redact_sensitive_text(_stringify_invalid_value(source.get(key)))
    return details


def parse_uuid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return str(UUID(text))
    except ValueError:
        return None


def parse_workflow_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text if _WORKFLOW_ID_PATTERN.fullmatch(text) else None


def url_path_segment(value: str) -> str:
    return quote(value, safe="")


def parse_artifact_relative_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    text = unquote(text)
    if "\x00" in text:
        return None
    # Reject still-encoded octets to avoid obvious double-decoding bypasses.
    if re.search(r"%[0-9A-Fa-f]{2}", text):
        return None
    if text.startswith(("/", "\\", "~")):
        return None
    if "://" in text:
        return None
    if _WINDOWS_DRIVE_PATTERN.match(text):
        return None

    posix_value = text.replace("\\", "/")
    path = PurePosixPath(posix_value)
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts:
        return None
    if any(part == ".." for part in parts):
        return None
    normalized = PurePosixPath(*parts).as_posix()
    return normalized or None


def validate_object_keys(
    value: Any, *, allowed_keys: set[str]
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, dict):
        return None, "must be an object"
    unknown_keys = sorted(key for key in value if isinstance(key, str) and key not in allowed_keys)
    if unknown_keys:
        return None, f"contains unsupported keys: {', '.join(unknown_keys)}"
    non_string_keys = [str(key) for key in value if not isinstance(key, str)]
    if non_string_keys:
        return None, "contains non-string keys"
    return dict(value), None


def validate_base64_size(
    value: Any, *, max_bytes: int = DEFAULT_MAX_BASE64_BYTES
) -> tuple[bool, str | None]:
    if not isinstance(value, str):
        return False, "must be a base64 string"
    max_encoded_len = ((max_bytes + 2) // 3) * 4
    if len(value) > max_encoded_len:
        return False, f"decoded payload exceeds {max_bytes} bytes"
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        return False, "must be valid base64"
    if len(raw) > max_bytes:
        return False, f"decoded payload exceeds {max_bytes} bytes"
    return True, None
