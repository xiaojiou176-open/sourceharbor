from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

DELIVERY_MAX_ATTEMPTS = 5
DELIVERY_RETRY_BACKOFF_MINUTES = [2, 5, 15, 30, 60]


def prepare_delivery_skip_reason(
    *,
    config: dict[str, Any],
    recipient_email: str | None,
    notification_enabled: bool,
    require_daily_digest: bool = False,
) -> str | None:
    if recipient_email is None:
        return "notification recipient email is not configured"
    if not notification_enabled:
        return "notification is disabled by environment"
    if not bool(config.get("enabled")):
        return "notification config is disabled"
    if require_daily_digest and not bool(config.get("daily_digest_enabled")):
        return "daily digest is disabled"
    return None


def classify_delivery_error(error_message: str) -> str:
    normalized = error_message.strip().lower()
    if not normalized:
        return "transient"

    if "not configured" in normalized:
        return "config_error"
    if "401" in normalized or "403" in normalized or "unauthorized" in normalized:
        return "auth"
    if "429" in normalized or "rate limit" in normalized:
        return "rate_limit"
    if any(
        token in normalized
        for token in (
            "timeout",
            "timed out",
            "connection",
            "network",
            "tempor",
            "dns",
            "502",
            "503",
            "504",
        )
    ):
        return "transient"
    return "transient"


def resolve_retry_backoff_minutes(*, attempt_count: int) -> int:
    index = max(0, min(attempt_count - 1, len(DELIVERY_RETRY_BACKOFF_MINUTES) - 1))
    return DELIVERY_RETRY_BACKOFF_MINUTES[index]


def resolve_next_retry_at(
    *,
    attempt_count: int,
    error_kind: str | None,
    now_utc: datetime | None = None,
) -> datetime | None:
    if error_kind in {"auth", "config_error"}:
        return None
    if attempt_count >= DELIVERY_MAX_ATTEMPTS:
        return None
    baseline = now_utc or datetime.now(UTC)
    backoff_minutes = resolve_retry_backoff_minutes(attempt_count=attempt_count)
    return baseline + timedelta(minutes=backoff_minutes)
