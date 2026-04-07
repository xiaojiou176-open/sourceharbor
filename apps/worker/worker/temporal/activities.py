from __future__ import annotations

from typing import Any

from worker.temporal import activities_delivery as _delivery
from worker.temporal import activities_job_state as _job_state
from worker.temporal import activities_timing as _timing
from worker.temporal.activities_entry import *  # noqa: F403

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


_JOB_STATE_PATCHABLES = (
    "Settings",
    "SQLiteStateStore",
    "PostgresBusinessStore",
    "_to_pipeline_final_status",
    "_resolve_degradation_count",
    "_resolve_last_error_code",
)

_DELIVERY_PATCHABLES = (
    "Settings",
    "PostgresBusinessStore",
    "_coerce_int",
    "_resolve_local_digest_date",
    "_safe_read_text",
    "_build_video_digest_markdown",
    "_build_daily_digest_markdown",
    "_load_daily_digest_jobs",
    "_normalize_email",
    "_send_with_resend",
    "_get_or_init_notification_config",
    "_prepare_delivery_skip_reason",
    "_classify_delivery_error",
    "_resolve_next_retry_at",
    "_mark_delivery_state",
    "_fetch_job_digest_record",
    "_insert_video_digest_delivery",
    "_insert_daily_digest_delivery",
    "_get_existing_video_digest",
    "_get_existing_daily_digest",
    "_claim_due_failed_deliveries",
    "_load_due_failed_deliveries",
    "_extract_daily_digest_date",
    "_extract_timezone_name",
    "_extract_timezone_offset_minutes",
    "_build_retry_failure_payload",
)


def _sync_symbols(target_module: Any, names: tuple[str, ...]) -> None:
    current = globals()
    for name in names:
        if name in current:
            setattr(target_module, name, current[name])


@activity.defn(name="run_pipeline_activity")
async def run_pipeline_activity(payload: dict[str, Any]) -> dict[str, Any]:
    _sync_symbols(_job_state, _JOB_STATE_PATCHABLES)
    return await _job_state.run_pipeline_activity(payload)


@activity.defn(name="send_video_digest_activity")
async def send_video_digest_activity(payload: dict[str, Any]) -> dict[str, Any]:
    _sync_symbols(_delivery, _DELIVERY_PATCHABLES)
    return await _delivery.send_video_digest_activity(payload)


@activity.defn(name="send_daily_digest_activity")
async def send_daily_digest_activity(payload: dict[str, Any]) -> dict[str, Any]:
    _sync_symbols(_delivery, _DELIVERY_PATCHABLES)
    return await _delivery.send_daily_digest_activity(payload)


@activity.defn(name="retry_failed_deliveries_activity")
async def retry_failed_deliveries_activity(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    _sync_symbols(_delivery, _DELIVERY_PATCHABLES)
    return await _delivery.retry_failed_deliveries_activity(payload)


mark_running_activity = _job_state.mark_running_activity
mark_succeeded_activity = _job_state.mark_succeeded_activity
mark_failed_activity = _job_state.mark_failed_activity
reconcile_stale_queued_jobs_activity = _job_state.reconcile_stale_queued_jobs_activity
resolve_daily_digest_timing_activity = _timing.resolve_daily_digest_timing_activity
