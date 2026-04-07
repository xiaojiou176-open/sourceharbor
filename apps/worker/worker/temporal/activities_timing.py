from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from temporalio import activity
except ModuleNotFoundError:  # pragma: no cover

    class _ActivityFallback:
        @staticmethod
        def defn(name: str | None = None):
            def _decorator(func):
                return func

            return _decorator

    activity = _ActivityFallback()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _coerce_int(value: Any, *, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw.startswith(("+", "-")):
            sign = -1 if raw.startswith("-") else 1
            raw = raw[1:]
        else:
            sign = 1
        if raw.isdigit():
            return int(raw) * sign
    return fallback


def _local_tz_from_offset(offset_minutes: int) -> timezone:
    return timezone(timedelta(minutes=offset_minutes))


def _resolve_local_timezone(
    *,
    timezone_name: str | None,
    offset_minutes: int,
) -> tuple[tzinfo, str]:
    if isinstance(timezone_name, str) and timezone_name.strip():
        normalized = timezone_name.strip()
        try:
            return ZoneInfo(normalized), normalized
        except ZoneInfoNotFoundError:
            pass
    return _local_tz_from_offset(offset_minutes), f"offset:{offset_minutes}"


def _resolve_local_digest_date(
    *,
    digest_date: str | None,
    timezone_name: str | None = None,
    offset_minutes: int = 0,
) -> date:
    if digest_date:
        return date.fromisoformat(digest_date)
    local_tz, _ = _resolve_local_timezone(
        timezone_name=timezone_name,
        offset_minutes=offset_minutes,
    )
    local_now = datetime.now(UTC).astimezone(local_tz)
    return local_now.date()


def _build_local_day_window_utc(
    *,
    local_day: date,
    timezone_name: str | None = None,
    offset_minutes: int = 0,
) -> tuple[datetime, datetime]:
    local_tz, _ = _resolve_local_timezone(
        timezone_name=timezone_name,
        offset_minutes=offset_minutes,
    )
    start_local = datetime.combine(local_day, time.min, tzinfo=local_tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


@activity.defn(name="resolve_daily_digest_timing_activity")
async def resolve_daily_digest_timing_activity(
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = payload or {}
    run_once = bool(config.get("run_once", False))
    timezone_name = str(config.get("timezone_name") or "").strip() or None
    offset_minutes = _coerce_int(config.get("timezone_offset_minutes"), fallback=0)
    target_hour = max(0, min(23, _coerce_int(config.get("local_hour"), fallback=9)))

    local_tz, resolved_timezone = _resolve_local_timezone(
        timezone_name=timezone_name,
        offset_minutes=offset_minutes,
    )
    now_utc = datetime.now(UTC)
    now_local = now_utc.astimezone(local_tz)
    scheduled_today = now_local.replace(hour=target_hour, minute=0, second=0, microsecond=0)

    wait_before_seconds = 0
    run_local = now_local
    if now_local < scheduled_today and not run_once:
        wait_before_seconds = int((scheduled_today - now_local).total_seconds())
        run_local = scheduled_today

    digest_date = run_local.date().isoformat()
    run_utc = run_local.astimezone(UTC)
    next_run_local = datetime.combine(
        run_local.date() + timedelta(days=1),
        time(hour=target_hour),
        tzinfo=local_tz,
    )
    wait_after_seconds = int((next_run_local.astimezone(UTC) - run_utc).total_seconds())
    if wait_after_seconds < 1:
        wait_after_seconds = 60

    return {
        "ok": True,
        "digest_date": digest_date,
        "wait_before_run_seconds": wait_before_seconds,
        "wait_after_run_seconds": wait_after_seconds,
        "timezone_name": resolved_timezone,
        "timezone_offset_minutes": int(now_local.utcoffset().total_seconds() // 60)
        if now_local.utcoffset()
        else offset_minutes,
    }
