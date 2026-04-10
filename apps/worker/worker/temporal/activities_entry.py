from __future__ import annotations

import uuid
from typing import Any

from apps.api.app.db import SessionLocal
from apps.api.app.services.reader_pipeline import ReaderPipelineService
from worker.config import Settings
from worker.state.postgres_store import PostgresBusinessStore
from worker.state.sqlite_store import SQLiteStateStore
from worker.temporal.activities_cleanup import cleanup_workspace_media_files
from worker.temporal.activities_delivery import (
    _build_retry_failure_payload,
    _claim_due_failed_deliveries,
    _classify_delivery_error,
    _extract_daily_digest_date,
    _extract_timezone_name,
    _extract_timezone_offset_minutes,
    _fetch_job_digest_record,
    _get_existing_daily_digest,
    _get_existing_video_digest,
    _get_or_init_notification_config,
    _insert_daily_digest_delivery,
    _insert_video_digest_delivery,
    _load_due_failed_deliveries,
    _mark_delivery_state,
    _prepare_delivery_skip_reason,
    _resolve_next_retry_at,
    retry_failed_deliveries_activity,
    send_daily_digest_activity,
    send_video_digest_activity,
)
from worker.temporal.activities_email import (
    is_sensitive_query_key as _is_sensitive_query_key,
)
from worker.temporal.activities_email import (
    normalize_email as _normalize_email,
)
from worker.temporal.activities_email import (
    render_markdown_html as _render_markdown_html,
)
from worker.temporal.activities_email import (
    sanitize_text_preview as _sanitize_text_preview,
)
from worker.temporal.activities_email import (
    sanitize_url_for_payload as _sanitize_url_for_payload,
)
from worker.temporal.activities_email import (
    send_with_resend as _send_with_resend,
)
from worker.temporal.activities_email import (
    to_html as _to_html,
)
from worker.temporal.activities_health import provider_canary_activity
from worker.temporal.activities_job_state import (
    _resolve_degradation_count,
    _resolve_last_error_code,
    _to_pipeline_final_status,
    mark_failed_activity,
    mark_running_activity,
    mark_succeeded_activity,
    reconcile_stale_queued_jobs_activity,
    run_pipeline_activity,
)
from worker.temporal.activities_poll import poll_feeds_activity, run_poll_feeds_once
from worker.temporal.activities_reports import (
    _build_daily_digest_markdown,
    _build_video_digest_markdown,
    _load_daily_digest_jobs,
    _safe_read_text,
)
from worker.temporal.activities_timing import (
    _build_local_day_window_utc,
    _coerce_int,
    _resolve_local_digest_date,
    _resolve_local_timezone,
    _utc_now_iso,
    resolve_daily_digest_timing_activity,
)

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


@activity.defn(name="cleanup_workspace_activity")
async def cleanup_workspace_activity(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    payload = payload or {}
    older_than_hours = max(1, _coerce_int(payload.get("older_than_hours"), fallback=24))
    cache_older_than_hours = max(
        1,
        _coerce_int(
            payload.get("cache_older_than_hours"),
            fallback=older_than_hours,
        ),
    )
    cache_max_size_mb = max(
        1,
        _coerce_int(
            payload.get("cache_max_size_mb"),
            fallback=1024,
        ),
    )
    return cleanup_workspace_media_files(
        workspace_dir=str(payload.get("workspace_dir") or settings.pipeline_workspace_dir),
        older_than_hours=older_than_hours,
        cache_dir=(
            str(payload.get("cache_dir"))
            if isinstance(payload.get("cache_dir"), str) and str(payload.get("cache_dir")).strip()
            else None
        ),
        cache_older_than_hours=cache_older_than_hours,
        cache_max_size_mb=cache_max_size_mb,
    )


@activity.defn(name="load_consumption_batch_activity")
async def load_consumption_batch_activity(payload: dict[str, Any]) -> dict[str, Any]:
    batch_id = str(payload.get("consumption_batch_id") or "").strip()
    if not batch_id:
        raise ValueError("consumption_batch_id is required")
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return pg_store.get_consumption_batch(batch_id=batch_id)


@activity.defn(name="prepare_consumption_batch_activity")
async def prepare_consumption_batch_activity(payload: dict[str, Any]) -> dict[str, Any]:
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    max_items = payload.get("max_items")
    if isinstance(max_items, bool):
        max_items = 200
    elif isinstance(max_items, int):
        max_items = max(1, min(1000, max_items))
    else:
        max_items = 200
    return pg_store.prepare_consumption_batch(
        trigger_mode=str(payload.get("trigger_mode") or "auto"),
        window_id=str(payload.get("window_id") or "").strip() or None,
        timezone_name=str(payload.get("timezone_name") or "").strip()
        or settings.digest_local_timezone,
        requested_by=str(payload.get("requested_by") or "").strip() or None,
        requested_trace_id=str(payload.get("requested_trace_id") or "").strip() or None,
        subscription_id=str(payload.get("subscription_id") or "").strip() or None,
        platform=str(payload.get("platform") or "").strip() or None,
        max_items=max_items,
    )


@activity.defn(name="mark_consumption_batch_materialized_activity")
async def mark_consumption_batch_materialized_activity(payload: dict[str, Any]) -> dict[str, Any]:
    batch_id = str(payload.get("consumption_batch_id") or "").strip()
    if not batch_id:
        raise ValueError("consumption_batch_id is required")
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return pg_store.mark_consumption_batch_materialized(
        batch_id=batch_id,
        processed_job_count=int(payload.get("processed_job_count") or 0),
        succeeded_job_count=int(payload.get("succeeded_job_count") or 0),
        failed_job_count=int(payload.get("failed_job_count") or 0),
        process_summary_json=dict(payload.get("process_summary_json") or {}),
    )


@activity.defn(name="mark_consumption_batch_closed_activity")
async def mark_consumption_batch_closed_activity(payload: dict[str, Any]) -> dict[str, Any]:
    batch_id = str(payload.get("consumption_batch_id") or "").strip()
    if not batch_id:
        raise ValueError("consumption_batch_id is required")
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return pg_store.mark_consumption_batch_closed(
        batch_id=batch_id,
        process_summary_json=dict(payload.get("process_summary_json") or {}),
    )


@activity.defn(name="materialize_reader_batch_activity")
async def materialize_reader_batch_activity(payload: dict[str, Any]) -> dict[str, Any]:
    batch_id = str(payload.get("consumption_batch_id") or "").strip()
    if not batch_id:
        raise ValueError("consumption_batch_id is required")
    db = SessionLocal()
    try:
        service = ReaderPipelineService(db)
        return service.materialize_batch(batch_id=uuid.UUID(batch_id))
    finally:
        db.close()


@activity.defn(name="mark_consumption_batch_failed_activity")
async def mark_consumption_batch_failed_activity(payload: dict[str, Any]) -> dict[str, Any]:
    batch_id = str(payload.get("consumption_batch_id") or "").strip()
    if not batch_id:
        raise ValueError("consumption_batch_id is required")
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return pg_store.mark_consumption_batch_failed(
        batch_id=batch_id,
        error_message=str(payload.get("error") or "consumption_batch_failed"),
        reset_items_to_pending=bool(payload.get("reset_items_to_pending", True)),
    )


__all__ = [
    "PostgresBusinessStore",
    "SQLiteStateStore",
    "Settings",
    "_build_daily_digest_markdown",
    "_build_local_day_window_utc",
    "_build_retry_failure_payload",
    "_build_video_digest_markdown",
    "_claim_due_failed_deliveries",
    "_classify_delivery_error",
    "_coerce_int",
    "_extract_daily_digest_date",
    "_extract_timezone_name",
    "_extract_timezone_offset_minutes",
    "_fetch_job_digest_record",
    "_get_existing_daily_digest",
    "_get_existing_video_digest",
    "_get_or_init_notification_config",
    "_insert_daily_digest_delivery",
    "_insert_video_digest_delivery",
    "_is_sensitive_query_key",
    "_load_daily_digest_jobs",
    "_load_due_failed_deliveries",
    "_mark_delivery_state",
    "_normalize_email",
    "_prepare_delivery_skip_reason",
    "_render_markdown_html",
    "_resolve_degradation_count",
    "_resolve_last_error_code",
    "_resolve_local_digest_date",
    "_resolve_local_timezone",
    "_resolve_next_retry_at",
    "_safe_read_text",
    "_sanitize_text_preview",
    "_sanitize_url_for_payload",
    "_send_with_resend",
    "_to_html",
    "_to_pipeline_final_status",
    "_utc_now_iso",
    "cleanup_workspace_activity",
    "cleanup_workspace_media_files",
    "load_consumption_batch_activity",
    "materialize_reader_batch_activity",
    "mark_failed_activity",
    "mark_consumption_batch_closed_activity",
    "mark_consumption_batch_failed_activity",
    "mark_consumption_batch_materialized_activity",
    "mark_running_activity",
    "mark_succeeded_activity",
    "poll_feeds_activity",
    "prepare_consumption_batch_activity",
    "provider_canary_activity",
    "reconcile_stale_queued_jobs_activity",
    "resolve_daily_digest_timing_activity",
    "retry_failed_deliveries_activity",
    "run_pipeline_activity",
    "run_poll_feeds_once",
    "send_daily_digest_activity",
    "send_video_digest_activity",
]
