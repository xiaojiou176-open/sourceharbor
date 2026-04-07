from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any


async def send_video_digest_activity_impl(
    *,
    settings: Any,
    pg_store: Any,
    payload: dict[str, Any],
    fetch_job_digest_record: Callable[..., dict[str, Any]],
    get_or_init_notification_config: Callable[[Any], dict[str, Any]],
    normalize_email: Callable[[Any], str | None],
    prepare_delivery_skip_reason: Callable[..., str | None],
    safe_read_text: Callable[[str | None], str | None],
    build_video_digest_markdown: Callable[[dict[str, Any], str | None], str],
    insert_video_digest_delivery: Callable[..., dict[str, Any] | None],
    get_existing_video_digest: Callable[..., dict[str, Any] | None],
    mark_delivery_state: Callable[..., dict[str, Any]],
    classify_delivery_error: Callable[[str], str],
    resolve_next_retry_at: Callable[..., datetime | None],
    send_with_resend: Callable[..., str],
) -> dict[str, Any]:
    job_id = str(payload["job_id"])

    with pg_store._engine.begin() as conn:  # type: ignore[attr-defined]
        job = fetch_job_digest_record(conn, job_id=job_id)
        config = get_or_init_notification_config(conn)
        recipient_email = normalize_email(config.get("to_email"))
        skip_reason = prepare_delivery_skip_reason(
            config=config,
            recipient_email=recipient_email,
            notification_enabled=settings.notification_enabled,
            require_daily_digest=False,
        )
        subject_title = str(job.get("title") or job.get("video_uid") or job_id)
        subject = f"[SourceHarbor] Video digest {subject_title}"
        digest_markdown = safe_read_text(str(job.get("artifact_digest_md") or ""))
        body_markdown = build_video_digest_markdown(job, digest_markdown)
        insert_payload = {
            "digest_scope": "video",
            "job_id": job_id,
            "job_status": str(job.get("status") or ""),
            "pipeline_final_status": str(job.get("pipeline_final_status") or ""),
        }
        created = insert_video_digest_delivery(
            conn,
            job=job,
            recipient_email=recipient_email or "unknown@example.invalid",
            subject=subject,
            payload_json=insert_payload,
        )
        if created is None:
            existing = get_existing_video_digest(conn, job_id=job_id) or {}
            return {
                "ok": True,
                "job_id": job_id,
                "skipped": True,
                "reason": "duplicate_delivery",
                "delivery_id": existing.get("delivery_id"),
                "status": existing.get("status"),
            }
        delivery = created

    delivery_id = str(delivery["delivery_id"])
    if skip_reason is not None:
        skipped = mark_delivery_state(
            pg_store,
            delivery_id=delivery_id,
            status="skipped",
            error_message=skip_reason,
            sent=False,
            clear_retry_meta=True,
        )
        return {
            "ok": True,
            "job_id": job_id,
            "delivery_id": delivery_id,
            "status": skipped["status"],
            "skipped": True,
            "reason": skip_reason,
        }

    if recipient_email is None:
        error_message = "notification recipient email is not configured"
        error_kind = classify_delivery_error(error_message)
        next_attempt = int(delivery.get("attempt_count") or 0) + 1
        failed = mark_delivery_state(
            pg_store,
            delivery_id=delivery_id,
            status="failed",
            error_message=error_message,
            sent=False,
            record_attempt=True,
            last_error_kind=error_kind,
            next_retry_at=resolve_next_retry_at(
                attempt_count=next_attempt,
                error_kind=error_kind,
            ),
        )
        return {
            "ok": False,
            "job_id": job_id,
            "delivery_id": delivery_id,
            "status": failed["status"],
            "error": failed["error_message"],
            "last_error_kind": failed.get("last_error_kind"),
            "attempt_count": failed.get("attempt_count"),
            "next_retry_at": (
                failed.get("next_retry_at").isoformat()
                if isinstance(failed.get("next_retry_at"), datetime)
                else None
            ),
        }

    try:
        provider_message_id = send_with_resend(
            to_email=recipient_email,
            subject=str(delivery["subject"]),
            text_body=body_markdown,
            resend_api_key=settings.resend_api_key,
            resend_from_email=settings.resend_from_email,
            idempotency_key=f"delivery-initial:{delivery_id}",
        )
    except RuntimeError as exc:
        error_message = str(exc)
        error_kind = classify_delivery_error(error_message)
        next_attempt = int(delivery.get("attempt_count") or 0) + 1
        failed = mark_delivery_state(
            pg_store,
            delivery_id=delivery_id,
            status="failed",
            error_message=error_message,
            sent=False,
            record_attempt=True,
            last_error_kind=error_kind,
            next_retry_at=resolve_next_retry_at(
                attempt_count=next_attempt,
                error_kind=error_kind,
            ),
        )
        return {
            "ok": False,
            "job_id": job_id,
            "delivery_id": delivery_id,
            "status": failed["status"],
            "error": failed["error_message"],
            "last_error_kind": failed.get("last_error_kind"),
            "attempt_count": failed.get("attempt_count"),
            "next_retry_at": (
                failed.get("next_retry_at").isoformat()
                if isinstance(failed.get("next_retry_at"), datetime)
                else None
            ),
        }

    sent = mark_delivery_state(
        pg_store,
        delivery_id=delivery_id,
        status="sent",
        provider_message_id=provider_message_id,
        error_message=None,
        sent=True,
        record_attempt=True,
        clear_retry_meta=True,
    )
    return {
        "ok": True,
        "job_id": job_id,
        "delivery_id": delivery_id,
        "status": sent["status"],
        "provider_message_id": sent.get("provider_message_id"),
        "sent_at": sent.get("sent_at").isoformat() if sent.get("sent_at") else None,
        "attempt_count": sent.get("attempt_count"),
    }


async def send_daily_digest_activity_impl(
    *,
    settings: Any,
    pg_store: Any,
    payload: dict[str, Any] | None,
    coerce_int: Callable[[Any, int], int],
    resolve_local_digest_date: Callable[..., Any],
    load_daily_digest_jobs: Callable[..., list[dict[str, Any]]],
    build_daily_digest_markdown: Callable[..., str],
    get_or_init_notification_config: Callable[[Any], dict[str, Any]],
    normalize_email: Callable[[Any], str | None],
    prepare_delivery_skip_reason: Callable[..., str | None],
    insert_daily_digest_delivery: Callable[..., dict[str, Any] | None],
    get_existing_daily_digest: Callable[..., dict[str, Any] | None],
    mark_delivery_state: Callable[..., dict[str, Any]],
    classify_delivery_error: Callable[[str], str],
    resolve_next_retry_at: Callable[..., datetime | None],
    send_with_resend: Callable[..., str],
) -> dict[str, Any]:
    payload = payload or {}
    timezone_name = str(payload.get("timezone_name") or "").strip() or None
    offset_minutes = coerce_int(payload.get("timezone_offset_minutes"), fallback=0)
    digest_day = resolve_local_digest_date(
        digest_date=str(payload.get("digest_date") or "") or None,
        timezone_name=timezone_name,
        offset_minutes=offset_minutes,
    )

    with pg_store._engine.begin() as conn:  # type: ignore[attr-defined]
        job_rows = load_daily_digest_jobs(
            conn,
            digest_day=digest_day,
            timezone_name=timezone_name,
            offset_minutes=offset_minutes,
        )
        digest_markdown = build_daily_digest_markdown(
            digest_day=digest_day,
            timezone_name=timezone_name,
            offset_minutes=offset_minutes,
            jobs=job_rows,
        )

        config = get_or_init_notification_config(conn)
        recipient_email = normalize_email(config.get("to_email"))
        skip_reason = prepare_delivery_skip_reason(
            config=config,
            recipient_email=recipient_email,
            notification_enabled=settings.notification_enabled,
            require_daily_digest=True,
        )
        subject = f"[SourceHarbor] Daily digest {digest_day.isoformat()}"
        insert_payload = {
            "digest_scope": "daily",
            "digest_date": digest_day.isoformat(),
            "timezone_name": timezone_name,
            "timezone_offset_minutes": offset_minutes,
            "job_count": len(job_rows),
        }
        created = insert_daily_digest_delivery(
            conn,
            digest_date=digest_day,
            recipient_email=recipient_email or "unknown@example.invalid",
            subject=subject,
            payload_json=insert_payload,
        )
        if created is None:
            existing = get_existing_daily_digest(conn, digest_date=digest_day) or {}
            return {
                "ok": True,
                "digest_date": digest_day.isoformat(),
                "skipped": True,
                "reason": "duplicate_delivery",
                "delivery_id": existing.get("delivery_id"),
                "status": existing.get("status"),
                "jobs": len(job_rows),
            }
        delivery = created

    delivery_id = str(delivery["delivery_id"])
    if skip_reason is not None:
        skipped = mark_delivery_state(
            pg_store,
            delivery_id=delivery_id,
            status="skipped",
            error_message=skip_reason,
            sent=False,
            clear_retry_meta=True,
        )
        return {
            "ok": True,
            "digest_date": digest_day.isoformat(),
            "delivery_id": delivery_id,
            "status": skipped["status"],
            "skipped": True,
            "reason": skip_reason,
            "jobs": len(job_rows),
        }

    if recipient_email is None:
        error_message = "notification recipient email is not configured"
        error_kind = classify_delivery_error(error_message)
        next_attempt = int(delivery.get("attempt_count") or 0) + 1
        failed = mark_delivery_state(
            pg_store,
            delivery_id=delivery_id,
            status="failed",
            error_message=error_message,
            sent=False,
            record_attempt=True,
            last_error_kind=error_kind,
            next_retry_at=resolve_next_retry_at(
                attempt_count=next_attempt,
                error_kind=error_kind,
            ),
        )
        return {
            "ok": False,
            "digest_date": digest_day.isoformat(),
            "delivery_id": delivery_id,
            "status": failed["status"],
            "error": failed["error_message"],
            "jobs": len(job_rows),
            "last_error_kind": failed.get("last_error_kind"),
            "attempt_count": failed.get("attempt_count"),
            "next_retry_at": (
                failed.get("next_retry_at").isoformat()
                if isinstance(failed.get("next_retry_at"), datetime)
                else None
            ),
        }

    try:
        provider_message_id = send_with_resend(
            to_email=recipient_email,
            subject=str(delivery["subject"]),
            text_body=digest_markdown,
            resend_api_key=settings.resend_api_key,
            resend_from_email=settings.resend_from_email,
            idempotency_key=f"delivery-initial:{delivery_id}",
        )
    except RuntimeError as exc:
        error_message = str(exc)
        error_kind = classify_delivery_error(error_message)
        next_attempt = int(delivery.get("attempt_count") or 0) + 1
        failed = mark_delivery_state(
            pg_store,
            delivery_id=delivery_id,
            status="failed",
            error_message=error_message,
            sent=False,
            record_attempt=True,
            last_error_kind=error_kind,
            next_retry_at=resolve_next_retry_at(
                attempt_count=next_attempt,
                error_kind=error_kind,
            ),
        )
        return {
            "ok": False,
            "digest_date": digest_day.isoformat(),
            "delivery_id": delivery_id,
            "status": failed["status"],
            "error": failed["error_message"],
            "jobs": len(job_rows),
            "last_error_kind": failed.get("last_error_kind"),
            "attempt_count": failed.get("attempt_count"),
            "next_retry_at": (
                failed.get("next_retry_at").isoformat()
                if isinstance(failed.get("next_retry_at"), datetime)
                else None
            ),
        }

    sent = mark_delivery_state(
        pg_store,
        delivery_id=delivery_id,
        status="sent",
        provider_message_id=provider_message_id,
        error_message=None,
        sent=True,
        record_attempt=True,
        clear_retry_meta=True,
    )
    return {
        "ok": True,
        "digest_date": digest_day.isoformat(),
        "delivery_id": delivery_id,
        "status": sent["status"],
        "provider_message_id": sent.get("provider_message_id"),
        "jobs": len(job_rows),
        "sent_at": sent.get("sent_at").isoformat() if sent.get("sent_at") else None,
        "attempt_count": sent.get("attempt_count"),
    }
