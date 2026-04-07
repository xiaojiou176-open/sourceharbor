from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from worker.config import Settings
from worker.state.postgres_store import PostgresBusinessStore
from worker.temporal.activities_delivery_payload import (
    build_retry_failure_payload as _build_retry_failure_payload_impl,
)
from worker.temporal.activities_delivery_payload import (
    extract_daily_digest_date as _extract_daily_digest_date_impl,
)
from worker.temporal.activities_delivery_payload import (
    extract_timezone_name as _extract_timezone_name_impl,
)
from worker.temporal.activities_delivery_payload import (
    extract_timezone_offset_minutes as _extract_timezone_offset_minutes_impl,
)
from worker.temporal.activities_delivery_policy import (
    classify_delivery_error as _classify_delivery_error,
)
from worker.temporal.activities_delivery_policy import (
    prepare_delivery_skip_reason as _prepare_delivery_skip_reason,
)
from worker.temporal.activities_delivery_policy import (
    resolve_next_retry_at as _resolve_next_retry_at,
)
from worker.temporal.activities_delivery_retry import retry_failed_deliveries_activity_impl
from worker.temporal.activities_delivery_send import (
    send_daily_digest_activity_impl,
    send_video_digest_activity_impl,
)
from worker.temporal.activities_email import normalize_email as _normalize_email
from worker.temporal.activities_email import send_with_resend as _send_with_resend
from worker.temporal.activities_reports import (
    _build_daily_digest_markdown,
    _build_video_digest_markdown,
    _load_daily_digest_jobs,
    _safe_read_text,
)
from worker.temporal.activities_timing import _coerce_int, _resolve_local_digest_date

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


DELIVERY_RETRY_CLAIM_TIMEOUT_MINUTES = 15


def _get_or_init_notification_config(conn: Any) -> dict[str, Any]:
    row = (
        conn.execute(
            text(
                """
            SELECT
                enabled,
                to_email,
                daily_digest_enabled
            FROM notification_configs
            WHERE singleton_key = 1
            LIMIT 1
            """
            )
        )
        .mappings()
        .first()
    )
    if row is not None:
        return dict(row)

    conn.execute(
        text(
            """
            INSERT INTO notification_configs (
                singleton_key,
                enabled,
                daily_digest_enabled,
                failure_alert_enabled,
                created_at,
                updated_at
            )
            VALUES (1, FALSE, FALSE, TRUE, NOW(), NOW())
            ON CONFLICT (singleton_key) DO NOTHING
            """
        )
    )
    loaded = (
        conn.execute(
            text(
                """
            SELECT
                enabled,
                to_email,
                daily_digest_enabled
            FROM notification_configs
            WHERE singleton_key = 1
            LIMIT 1
            """
            )
        )
        .mappings()
        .first()
    )
    if loaded is None:
        return {"enabled": False, "to_email": None, "daily_digest_enabled": False}
    return dict(loaded)


def _mark_delivery_state(
    pg_store: PostgresBusinessStore,
    *,
    delivery_id: str,
    status: str,
    error_message: str | None = None,
    provider_message_id: str | None = None,
    sent: bool = False,
    record_attempt: bool = False,
    last_error_kind: str | None = None,
    next_retry_at: datetime | None = None,
    clear_retry_meta: bool = False,
    expected_status: str | None = None,
    expected_attempt_count: int | None = None,
) -> dict[str, Any]:
    with pg_store._engine.begin() as conn:  # type: ignore[attr-defined]
        row = (
            conn.execute(
                text(
                    """
                UPDATE notification_deliveries
                SET
                    status = :status,
                    error_message = :error_message,
                    provider_message_id = :provider_message_id,
                    sent_at = CASE WHEN :sent THEN NOW() ELSE sent_at END,
                    attempt_count = CASE
                        WHEN :record_attempt THEN attempt_count + 1
                        ELSE attempt_count
                    END,
                    last_attempt_at = CASE
                        WHEN :record_attempt THEN NOW()
                        ELSE last_attempt_at
                    END,
                    last_error_kind = CASE
                        WHEN :clear_retry_meta THEN NULL
                        WHEN CAST(:last_error_kind AS TEXT) IS NULL THEN last_error_kind
                        ELSE CAST(:last_error_kind AS TEXT)
                    END,
                    next_retry_at = CASE
                        WHEN :clear_retry_meta THEN NULL
                        ELSE CAST(:next_retry_at AS TIMESTAMPTZ)
                    END
                WHERE id = CAST(:delivery_id AS UUID)
                  AND (
                      CAST(:expected_status AS TEXT) IS NULL
                      OR status = CAST(:expected_status AS TEXT)
                  )
                  AND (
                      CAST(:expected_attempt_count AS INTEGER) IS NULL
                      OR attempt_count = CAST(:expected_attempt_count AS INTEGER)
                  )
                RETURNING
                    id::text AS delivery_id,
                    status,
                    provider_message_id,
                    error_message,
                    sent_at,
                    attempt_count,
                    last_attempt_at,
                    next_retry_at,
                    last_error_kind
                """
                ),
                {
                    "delivery_id": delivery_id,
                    "status": status,
                    "error_message": error_message,
                    "provider_message_id": provider_message_id,
                    "sent": sent,
                    "record_attempt": record_attempt,
                    "last_error_kind": last_error_kind,
                    "next_retry_at": next_retry_at,
                    "clear_retry_meta": clear_retry_meta,
                    "expected_status": expected_status,
                    "expected_attempt_count": expected_attempt_count,
                },
            )
            .mappings()
            .first()
        )
        if row is not None:
            return dict(row)
        existing = (
            conn.execute(
                text(
                    """
                SELECT
                    id::text AS delivery_id,
                    status,
                    provider_message_id,
                    error_message,
                    sent_at,
                    attempt_count,
                    last_attempt_at,
                    next_retry_at,
                    last_error_kind
                FROM notification_deliveries
                WHERE id = CAST(:delivery_id AS UUID)
                LIMIT 1
                """
                ),
                {"delivery_id": delivery_id},
            )
            .mappings()
            .first()
        )
        if existing is None:
            raise ValueError(f"delivery not found: {delivery_id}")
        payload = dict(existing)
        payload["conflict"] = True
        payload["expected_status"] = expected_status
        payload["expected_attempt_count"] = expected_attempt_count
        return payload


def _fetch_job_digest_record(conn: Any, *, job_id: str) -> dict[str, Any]:
    row = (
        conn.execute(
            text(
                """
            SELECT
                j.id::text AS job_id,
                j.status,
                j.pipeline_final_status,
                j.artifact_digest_md,
                j.updated_at,
                v.platform,
                v.video_uid,
                v.title,
                v.source_url
            FROM jobs j
            JOIN videos v ON v.id = j.video_id
            WHERE j.id = CAST(:job_id AS UUID)
            LIMIT 1
            """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError(f"job not found: {job_id}")
    return dict(row)


def _insert_video_digest_delivery(
    conn: Any,
    *,
    job: dict[str, Any],
    recipient_email: str,
    subject: str,
    payload_json: dict[str, Any],
) -> dict[str, Any] | None:
    conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"video_digest:{job['job_id']}"},
    )
    existing = (
        conn.execute(
            text(
                """
            SELECT
                id::text AS delivery_id,
                status,
                recipient_email,
                subject,
                provider_message_id,
                error_message,
                sent_at,
                attempt_count,
                last_attempt_at,
                next_retry_at,
                last_error_kind
            FROM notification_deliveries
            WHERE kind = 'video_digest'
              AND job_id = CAST(:job_id AS UUID)
              AND (
                  status IN ('queued', 'sent', 'skipped')
                  OR (status = 'failed' AND next_retry_at IS NOT NULL)
              )
            ORDER BY created_at DESC
            LIMIT 1
            """
            ),
            {"job_id": job["job_id"]},
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return None

    created = (
        conn.execute(
            text(
                """
            INSERT INTO notification_deliveries (
                kind,
                status,
                recipient_email,
                subject,
                provider,
                payload_json,
                job_id,
                created_at
            )
            VALUES (
                'video_digest',
                'queued',
                :recipient_email,
                :subject,
                'resend',
                CAST(:payload_json AS JSONB),
                CAST(:job_id AS UUID),
                NOW()
            )
            RETURNING
                id::text AS delivery_id,
                status,
                recipient_email,
                subject,
                attempt_count,
                last_attempt_at,
                next_retry_at,
                last_error_kind
            """
            ),
            {
                "recipient_email": recipient_email,
                "subject": subject,
                "payload_json": json.dumps(payload_json, ensure_ascii=False),
                "job_id": job["job_id"],
            },
        )
        .mappings()
        .one()
    )
    return dict(created)


def _insert_daily_digest_delivery(
    conn: Any,
    *,
    digest_date: date,
    recipient_email: str,
    subject: str,
    payload_json: dict[str, Any],
) -> dict[str, Any] | None:
    conn.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"daily_digest:{digest_date.isoformat()}"},
    )
    existing = (
        conn.execute(
            text(
                """
            SELECT
                id::text AS delivery_id,
                status,
                recipient_email,
                subject,
                provider_message_id,
                error_message,
                sent_at,
                attempt_count,
                last_attempt_at,
                next_retry_at,
                last_error_kind
            FROM notification_deliveries
            WHERE kind = 'daily_digest'
              AND job_id IS NULL
              AND COALESCE(payload_json->>'digest_scope', '') = 'daily'
              AND COALESCE(payload_json->>'digest_date', '') = :digest_date
              AND (
                  status IN ('queued', 'sent', 'skipped')
                  OR (status = 'failed' AND next_retry_at IS NOT NULL)
              )
            ORDER BY created_at DESC
            LIMIT 1
            """
            ),
            {"digest_date": digest_date.isoformat()},
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return None

    created = (
        conn.execute(
            text(
                """
            INSERT INTO notification_deliveries (
                kind,
                status,
                recipient_email,
                subject,
                provider,
                payload_json,
                created_at
            )
            VALUES (
                'daily_digest',
                'queued',
                :recipient_email,
                :subject,
                'resend',
                CAST(:payload_json AS JSONB),
                NOW()
            )
            RETURNING
                id::text AS delivery_id,
                status,
                recipient_email,
                subject,
                attempt_count,
                last_attempt_at,
                next_retry_at,
                last_error_kind
            """
            ),
            {
                "recipient_email": recipient_email,
                "subject": subject,
                "payload_json": json.dumps(payload_json, ensure_ascii=False),
            },
        )
        .mappings()
        .one()
    )
    return dict(created)


def _get_existing_video_digest(conn: Any, *, job_id: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
            SELECT
                id::text AS delivery_id,
                status,
                recipient_email,
                subject,
                provider_message_id,
                error_message,
                sent_at,
                attempt_count,
                last_attempt_at,
                next_retry_at,
                last_error_kind
            FROM notification_deliveries
            WHERE kind = 'video_digest'
              AND job_id = CAST(:job_id AS UUID)
              AND (
                  status IN ('queued', 'sent', 'skipped')
                  OR (status = 'failed' AND next_retry_at IS NOT NULL)
              )
            ORDER BY created_at DESC
            LIMIT 1
            """
            ),
            {"job_id": job_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def _get_existing_daily_digest(conn: Any, *, digest_date: date) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
            SELECT
                id::text AS delivery_id,
                status,
                recipient_email,
                subject,
                provider_message_id,
                error_message,
                sent_at,
                attempt_count,
                last_attempt_at,
                next_retry_at,
                last_error_kind
            FROM notification_deliveries
            WHERE kind = 'daily_digest'
              AND job_id IS NULL
              AND COALESCE(payload_json->>'digest_scope', '') = 'daily'
              AND COALESCE(payload_json->>'digest_date', '') = :digest_date
              AND (
                  status IN ('queued', 'sent', 'skipped')
                  OR (status = 'failed' AND next_retry_at IS NOT NULL)
              )
            ORDER BY created_at DESC
            LIMIT 1
            """
            ),
            {"digest_date": digest_date.isoformat()},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def _claim_due_failed_deliveries(
    conn: Any,
    *,
    limit: int,
    claim_timeout_minutes: int = DELIVERY_RETRY_CLAIM_TIMEOUT_MINUTES,
) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            text(
                """
            WITH due AS (
                SELECT id
                FROM notification_deliveries
                WHERE (
                    (
                        status = 'failed'
                        AND next_retry_at IS NOT NULL
                        AND next_retry_at <= NOW()
                    )
                    OR (
                        status = 'queued'
                        AND updated_at <= NOW() - (
                            CAST(:claim_timeout_minutes AS TEXT) || ' minutes'
                        )::INTERVAL
                        AND (
                            (
                                next_retry_at IS NOT NULL
                                AND next_retry_at <= NOW()
                                AND attempt_count > 0
                            )
                            OR (
                                next_retry_at IS NULL
                                AND attempt_count = 0
                            )
                        )
                    )
                )
                ORDER BY next_retry_at ASC, created_at ASC
                LIMIT :limit
                FOR UPDATE SKIP LOCKED
            )
            UPDATE notification_deliveries AS d
            SET
                status = 'queued',
                updated_at = NOW()
            FROM due
            WHERE d.id = due.id
            RETURNING
                d.id::text AS delivery_id,
                d.kind,
                d.status,
                d.recipient_email,
                d.subject,
                d.payload_json,
                d.job_id::text AS job_id,
                d.attempt_count,
                d.last_attempt_at,
                d.next_retry_at,
                d.last_error_kind
            """
            ),
            {
                "limit": limit,
                "claim_timeout_minutes": max(1, int(claim_timeout_minutes)),
            },
        )
        .mappings()
        .all()
    )
    return [dict(item) for item in rows]


def _load_due_failed_deliveries(
    conn: Any,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    return _claim_due_failed_deliveries(conn, limit=limit)


def _extract_daily_digest_date(payload_json: Any) -> date | None:
    return _extract_daily_digest_date_impl(payload_json)


def _extract_timezone_name(payload_json: Any) -> str | None:
    return _extract_timezone_name_impl(payload_json)


def _extract_timezone_offset_minutes(payload_json: Any) -> int:
    return _extract_timezone_offset_minutes_impl(
        payload_json,
        coerce_int=lambda value, fallback: _coerce_int(value, fallback=fallback),
    )


def _build_retry_failure_payload(
    *,
    error_message: str,
    attempt_count: int,
) -> tuple[str, datetime | None]:
    return _build_retry_failure_payload_impl(
        error_message=error_message,
        attempt_count=attempt_count,
        classify_delivery_error=_classify_delivery_error,
        resolve_next_retry_at=_resolve_next_retry_at,
    )


@activity.defn(name="retry_failed_deliveries_activity")
async def retry_failed_deliveries_activity(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return await retry_failed_deliveries_activity_impl(
        settings=settings,
        pg_store=pg_store,
        payload=payload,
        coerce_int=_coerce_int,
        claim_due_failed_deliveries=_claim_due_failed_deliveries,
        normalize_email=_normalize_email,
        build_retry_failure_payload=_build_retry_failure_payload,
        mark_delivery_state=_mark_delivery_state,
        fetch_job_digest_record=_fetch_job_digest_record,
        safe_read_text=_safe_read_text,
        build_video_digest_markdown=_build_video_digest_markdown,
        extract_daily_digest_date=_extract_daily_digest_date,
        extract_timezone_name=_extract_timezone_name,
        extract_timezone_offset_minutes=_extract_timezone_offset_minutes,
        resolve_local_digest_date=_resolve_local_digest_date,
        load_daily_digest_jobs=_load_daily_digest_jobs,
        build_daily_digest_markdown=_build_daily_digest_markdown,
        send_with_resend=_send_with_resend,
    )


@activity.defn(name="send_video_digest_activity")
async def send_video_digest_activity(payload: dict[str, Any]) -> dict[str, Any]:
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return await send_video_digest_activity_impl(
        settings=settings,
        pg_store=pg_store,
        payload=payload,
        fetch_job_digest_record=_fetch_job_digest_record,
        get_or_init_notification_config=_get_or_init_notification_config,
        normalize_email=_normalize_email,
        prepare_delivery_skip_reason=_prepare_delivery_skip_reason,
        safe_read_text=_safe_read_text,
        build_video_digest_markdown=_build_video_digest_markdown,
        insert_video_digest_delivery=_insert_video_digest_delivery,
        get_existing_video_digest=_get_existing_video_digest,
        mark_delivery_state=_mark_delivery_state,
        classify_delivery_error=_classify_delivery_error,
        resolve_next_retry_at=_resolve_next_retry_at,
        send_with_resend=_send_with_resend,
    )


@activity.defn(name="send_daily_digest_activity")
async def send_daily_digest_activity(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    return await send_daily_digest_activity_impl(
        settings=settings,
        pg_store=pg_store,
        payload=payload,
        coerce_int=_coerce_int,
        resolve_local_digest_date=_resolve_local_digest_date,
        load_daily_digest_jobs=_load_daily_digest_jobs,
        build_daily_digest_markdown=_build_daily_digest_markdown,
        get_or_init_notification_config=_get_or_init_notification_config,
        normalize_email=_normalize_email,
        prepare_delivery_skip_reason=_prepare_delivery_skip_reason,
        insert_daily_digest_delivery=_insert_daily_digest_delivery,
        get_existing_daily_digest=_get_existing_daily_digest,
        mark_delivery_state=_mark_delivery_state,
        classify_delivery_error=_classify_delivery_error,
        resolve_next_retry_at=_resolve_next_retry_at,
        send_with_resend=_send_with_resend,
    )
