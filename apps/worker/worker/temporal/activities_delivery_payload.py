from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any


def extract_daily_digest_date(payload_json: Any) -> date | None:
    if not isinstance(payload_json, dict):
        return None
    raw = payload_json.get("digest_date")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def extract_timezone_name(payload_json: Any) -> str | None:
    if not isinstance(payload_json, dict):
        return None
    raw = payload_json.get("timezone_name")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def extract_timezone_offset_minutes(
    payload_json: Any,
    *,
    coerce_int: Callable[[Any, int], int],
) -> int:
    if not isinstance(payload_json, dict):
        return 0
    return coerce_int(payload_json.get("timezone_offset_minutes"), 0)


def build_retry_failure_payload(
    *,
    error_message: str,
    attempt_count: int,
    classify_delivery_error: Callable[[str], str],
    resolve_next_retry_at: Callable[..., datetime | None],
) -> tuple[str, datetime | None]:
    error_kind = classify_delivery_error(error_message)
    next_retry_at = resolve_next_retry_at(
        attempt_count=attempt_count,
        error_kind=error_kind,
    )
    return error_kind, next_retry_at
