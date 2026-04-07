from __future__ import annotations

import asyncio
import types
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from worker.temporal import activities, workflows


class _DummyBegin:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyEngine:
    def begin(self):
        return _DummyBegin()


class _DummyPostgresStore:
    def __init__(self, _database_url: str):
        self._engine = _DummyEngine()
        self.released_leases: list[Any] = []

    def try_acquire_advisory_lock(self, *, lock_key: str) -> tuple[bool, Any, str | None]:
        return (False, None, f"advisory_unsupported:{lock_key}")

    def release_advisory_lock(self, lease: Any) -> None:
        self.released_leases.append(lease)


def test_retry_failed_deliveries_activity_schedules_retry_for_transient(monkeypatch: Any) -> None:
    captured: list[dict[str, Any]] = []
    now_utc = datetime(2026, 2, 22, 12, 0, tzinfo=UTC)

    monkeypatch.setattr(activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                resend_api_key="rk_test",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(
        activities,
        "_claim_due_failed_deliveries",
        lambda _conn, *, limit: [
            {
                "delivery_id": "delivery-1",
                "kind": "video_digest",
                "recipient_email": "notify@example.com",
                "subject": "Digest",
                "payload_json": {},
                "job_id": "00000000-0000-0000-0000-000000000001",
                "attempt_count": 0,
            }
        ],
    )
    monkeypatch.setattr(
        activities,
        "_fetch_job_digest_record",
        lambda _conn, *, job_id: {
            "job_id": job_id,
            "title": "Demo",
            "video_uid": "demo",
            "platform": "youtube",
            "source_url": "https://example.com/video",
            "status": "succeeded",
            "artifact_digest_md": "",
        },
    )
    monkeypatch.setattr(activities, "_safe_read_text", lambda _path: "digest")
    monkeypatch.setattr(
        activities,
        "_send_with_resend",
        lambda **_: (_ for _ in ()).throw(RuntimeError("Resend request failed: timeout")),
    )

    def _fake_mark_delivery_state(
        _pg_store,
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
        **_: Any,
    ) -> dict[str, Any]:
        captured.append(
            {
                "delivery_id": delivery_id,
                "status": status,
                "error_message": error_message,
                "provider_message_id": provider_message_id,
                "record_attempt": record_attempt,
                "last_error_kind": last_error_kind,
                "next_retry_at": next_retry_at or now_utc + timedelta(minutes=2),
                "clear_retry_meta": clear_retry_meta,
            }
        )
        return {
            "delivery_id": delivery_id,
            "status": status,
            "attempt_count": 1,
            "next_retry_at": next_retry_at or now_utc + timedelta(minutes=2),
            "last_error_kind": last_error_kind,
        }

    monkeypatch.setattr(activities, "_mark_delivery_state", _fake_mark_delivery_state)

    payload = asyncio.run(activities.retry_failed_deliveries_activity({"limit": 10}))

    assert payload["checked"] == 1
    assert payload["retried"] == 1
    assert payload["sent"] == 0
    assert payload["failed"] == 1
    assert payload["retry_scheduled"] == 1
    assert captured[0]["status"] == "failed"
    assert captured[0]["last_error_kind"] == "transient"
    assert captured[0]["record_attempt"] is True


def test_retry_backoff_stops_for_config_error() -> None:
    error_kind, next_retry_at = activities._build_retry_failure_payload(
        error_message="RESEND_API_KEY is not configured",
        attempt_count=1,
    )

    assert error_kind == "config_error"
    assert next_retry_at is None


def test_retry_failed_deliveries_activity_marks_sent_on_recovery(monkeypatch: Any) -> None:
    captured: list[dict[str, Any]] = []
    send_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                resend_api_key="rk_test",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(
        activities,
        "_claim_due_failed_deliveries",
        lambda _conn, *, limit: [
            {
                "delivery_id": "delivery-2",
                "kind": "video_digest",
                "recipient_email": "notify@example.com",
                "subject": "Digest",
                "payload_json": {},
                "job_id": "00000000-0000-0000-0000-000000000002",
                "attempt_count": 1,
            }
        ],
    )
    monkeypatch.setattr(
        activities,
        "_fetch_job_digest_record",
        lambda _conn, *, job_id: {
            "job_id": job_id,
            "title": "Demo",
            "video_uid": "demo",
            "platform": "youtube",
            "source_url": "https://example.com/video",
            "status": "succeeded",
            "artifact_digest_md": "",
        },
    )
    monkeypatch.setattr(activities, "_safe_read_text", lambda _path: "digest")

    def _fake_send_with_resend(**kwargs: Any) -> str:
        send_calls.append(dict(kwargs))
        return "provider-msg-1"

    monkeypatch.setattr(activities, "_send_with_resend", _fake_send_with_resend)

    def _fake_mark_delivery_state(
        _pg_store,
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
        **_: Any,
    ) -> dict[str, Any]:
        captured.append(
            {
                "delivery_id": delivery_id,
                "status": status,
                "provider_message_id": provider_message_id,
                "clear_retry_meta": clear_retry_meta,
                "record_attempt": record_attempt,
            }
        )
        return {
            "delivery_id": delivery_id,
            "status": status,
            "attempt_count": 2,
            "next_retry_at": None,
            "last_error_kind": None,
        }

    monkeypatch.setattr(activities, "_mark_delivery_state", _fake_mark_delivery_state)

    payload = asyncio.run(activities.retry_failed_deliveries_activity({"limit": 10}))

    assert payload["checked"] == 1
    assert payload["retried"] == 1
    assert payload["sent"] == 1
    assert payload["failed"] == 0
    assert payload["retry_scheduled"] == 0
    assert captured[0]["delivery_id"] == "delivery-2"
    assert captured[0]["status"] == "sent"
    assert captured[0]["record_attempt"] is True
    assert captured[0]["clear_retry_meta"] is True
    assert send_calls[0]["idempotency_key"] == "delivery-retry:delivery-2:attempt-2"


def test_retry_failed_deliveries_reclaimed_first_attempt_reuses_initial_idempotency(
    monkeypatch: Any,
) -> None:
    send_calls: list[dict[str, Any]] = []
    mark_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                resend_api_key="rk_test",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(
        activities,
        "_claim_due_failed_deliveries",
        lambda _conn, *, limit: [
            {
                "delivery_id": "delivery-3",
                "kind": "video_digest",
                "recipient_email": "notify@example.com",
                "subject": "Digest",
                "payload_json": {},
                "job_id": "00000000-0000-0000-0000-000000000003",
                "attempt_count": 0,
            }
        ],
    )
    monkeypatch.setattr(
        activities,
        "_fetch_job_digest_record",
        lambda _conn, *, job_id: {
            "job_id": job_id,
            "title": "Demo",
            "video_uid": "demo-uid",
            "source_url": "https://example.com",
            "artifact_digest_md": "",
        },
    )
    monkeypatch.setattr(activities, "_safe_read_text", lambda _path: "digest")
    monkeypatch.setattr(
        activities,
        "_send_with_resend",
        lambda **kwargs: send_calls.append(dict(kwargs)) or "provider-msg-3",
    )

    def _fake_mark_delivery_state(_pg_store, **kwargs: Any) -> dict[str, Any]:
        mark_calls.append(dict(kwargs))
        return {
            "delivery_id": kwargs["delivery_id"],
            "status": kwargs["status"],
            "attempt_count": kwargs.get("expected_attempt_count", 0)
            + (1 if kwargs.get("record_attempt") else 0),
            "next_retry_at": kwargs.get("next_retry_at"),
        }

    monkeypatch.setattr(activities, "_mark_delivery_state", _fake_mark_delivery_state)

    payload = asyncio.run(activities.retry_failed_deliveries_activity({"limit": 10}))

    assert payload["checked"] == 1
    assert payload["retried"] == 1
    assert payload["sent"] == 1
    assert payload["failed"] == 0
    assert send_calls[0]["idempotency_key"] == "delivery-initial:delivery-3"
    assert mark_calls[0]["expected_attempt_count"] == 0


def test_retry_failed_deliveries_activity_skips_delivery_when_lock_busy(monkeypatch: Any) -> None:
    class _LockBusyStore(_DummyPostgresStore):
        def try_acquire_advisory_lock(self, *, lock_key: str) -> tuple[bool, Any, str | None]:
            assert lock_key == "notification_delivery_retry:delivery-lock-busy"
            return (True, None, None)

    monkeypatch.setattr(activities, "PostgresBusinessStore", _LockBusyStore)
    monkeypatch.setattr(
        activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                resend_api_key="rk_test",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(
        activities,
        "_claim_due_failed_deliveries",
        lambda _conn, *, limit: [
            {
                "delivery_id": "delivery-lock-busy",
                "kind": "video_digest",
                "recipient_email": "notify@example.com",
                "subject": "Digest",
                "payload_json": {},
                "job_id": "00000000-0000-0000-0000-000000000003",
                "attempt_count": 1,
            }
        ],
    )

    send_calls: list[dict[str, Any]] = []
    mark_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        activities, "_fetch_job_digest_record", lambda _conn, *, job_id: {"job_id": job_id}
    )
    monkeypatch.setattr(activities, "_safe_read_text", lambda _path: "digest")
    monkeypatch.setattr(
        activities,
        "_send_with_resend",
        lambda **kwargs: send_calls.append(dict(kwargs)) or "provider-msg-1",
    )
    monkeypatch.setattr(
        activities,
        "_mark_delivery_state",
        lambda _pg_store, **kwargs: (
            mark_calls.append(dict(kwargs))
            or {"delivery_id": kwargs["delivery_id"], "status": kwargs["status"]}
        ),
    )

    payload = asyncio.run(activities.retry_failed_deliveries_activity({"limit": 10}))

    assert payload["checked"] == 1
    assert payload["retried"] == 0
    assert payload["lock_skipped"] == 1
    assert payload["sent"] == 0
    assert payload["failed"] == 0
    assert send_calls == []
    assert mark_calls == []


def test_send_video_digest_activity_uses_stable_idempotency_key_on_first_send(
    monkeypatch: Any,
) -> None:
    send_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                notification_enabled=True,
                resend_api_key="rk_test",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(
        activities,
        "_fetch_job_digest_record",
        lambda _conn, *, job_id: {
            "job_id": job_id,
            "title": "Demo",
            "video_uid": "demo",
            "platform": "youtube",
            "source_url": "https://example.com/video",
            "status": "succeeded",
            "artifact_digest_md": "",
        },
    )
    monkeypatch.setattr(
        activities,
        "_get_or_init_notification_config",
        lambda _conn: {
            "enabled": True,
            "daily_digest_enabled": True,
            "to_email": "notify@example.com",
        },
    )
    monkeypatch.setattr(activities, "_normalize_email", lambda value: value)
    monkeypatch.setattr(activities, "_prepare_delivery_skip_reason", lambda **_: None)
    monkeypatch.setattr(activities, "_safe_read_text", lambda _path: "digest")
    monkeypatch.setattr(activities, "_build_video_digest_markdown", lambda _job, _md: "digest-body")
    monkeypatch.setattr(
        activities,
        "_insert_video_digest_delivery",
        lambda _conn, **_: {
            "delivery_id": "delivery-video-1",
            "subject": "Digest",
            "attempt_count": 0,
        },
    )
    monkeypatch.setattr(activities, "_get_existing_video_digest", lambda _conn, *, job_id: None)
    monkeypatch.setattr(
        activities,
        "_send_with_resend",
        lambda **kwargs: send_calls.append(dict(kwargs)) or "provider-msg-video-1",
    )
    monkeypatch.setattr(
        activities,
        "_mark_delivery_state",
        lambda _pg_store, **kwargs: {
            "delivery_id": kwargs["delivery_id"],
            "status": kwargs["status"],
            "provider_message_id": kwargs.get("provider_message_id"),
            "sent_at": None,
            "attempt_count": 1,
        },
    )

    payload = asyncio.run(
        activities.send_video_digest_activity({"job_id": "00000000-0000-0000-0000-000000000010"})
    )

    assert payload["ok"] is True
    assert send_calls[0]["idempotency_key"] == "delivery-initial:delivery-video-1"


def test_send_daily_digest_activity_uses_stable_idempotency_key_on_first_send(
    monkeypatch: Any,
) -> None:
    send_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                notification_enabled=True,
                resend_api_key="rk_test",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(activities, "_coerce_int", lambda value, fallback=0: int(value or fallback))
    monkeypatch.setattr(
        activities,
        "_resolve_local_digest_date",
        lambda **_: date(2026, 2, 22),
    )
    monkeypatch.setattr(activities, "_load_daily_digest_jobs", lambda _conn, **_: [])
    monkeypatch.setattr(activities, "_build_daily_digest_markdown", lambda **_: "daily-body")
    monkeypatch.setattr(
        activities,
        "_get_or_init_notification_config",
        lambda _conn: {
            "enabled": True,
            "daily_digest_enabled": True,
            "to_email": "notify@example.com",
        },
    )
    monkeypatch.setattr(activities, "_normalize_email", lambda value: value)
    monkeypatch.setattr(activities, "_prepare_delivery_skip_reason", lambda **_: None)
    monkeypatch.setattr(
        activities,
        "_insert_daily_digest_delivery",
        lambda _conn, **_: {
            "delivery_id": "delivery-daily-1",
            "subject": "Daily Digest",
            "attempt_count": 0,
        },
    )
    monkeypatch.setattr(
        activities, "_get_existing_daily_digest", lambda _conn, *, digest_date: None
    )
    monkeypatch.setattr(
        activities,
        "_send_with_resend",
        lambda **kwargs: send_calls.append(dict(kwargs)) or "provider-msg-daily-1",
    )
    monkeypatch.setattr(
        activities,
        "_mark_delivery_state",
        lambda _pg_store, **kwargs: {
            "delivery_id": kwargs["delivery_id"],
            "status": kwargs["status"],
            "provider_message_id": kwargs.get("provider_message_id"),
            "sent_at": None,
            "attempt_count": 1,
        },
    )

    payload = asyncio.run(
        activities.send_daily_digest_activity(
            {"digest_date": "2026-02-22", "timezone_name": "UTC", "timezone_offset_minutes": 0}
        )
    )

    assert payload["ok"] is True
    assert send_calls[0]["idempotency_key"] == "delivery-initial:delivery-daily-1"


def test_daily_digest_workflow_uses_timezone_name_across_dst(monkeypatch: Any) -> None:
    sleeps: list[timedelta] = []
    activity_payloads: list[dict[str, Any]] = []

    async def _fake_sleep(duration: timedelta) -> None:
        sleeps.append(duration)
        if len(sleeps) >= 2:
            raise StopAsyncIteration

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        if activity_fn is workflows.resolve_daily_digest_timing_activity:
            return {
                "ok": True,
                "digest_date": "2026-03-07",
                "wait_before_run_seconds": 3600,
                "wait_after_run_seconds": 82800,
                "timezone_name": "America/Los_Angeles",
                "timezone_offset_minutes": -480,
            }
        assert activity_fn is workflows.send_daily_digest_activity
        activity_payloads.append(dict(payload))
        return {"ok": True}

    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)
    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(
            workflows.DailyDigestWorkflow().run(
                {
                    "run_once": False,
                    "local_hour": 9,
                    "timezone_name": "America/Los_Angeles",
                    "timezone_offset_minutes": -480,
                }
            )
        )

    assert activity_payloads[0]["timezone_name"] == "America/Los_Angeles"
    assert activity_payloads[0]["digest_date"] == "2026-03-07"
    assert int(sleeps[0].total_seconds()) == 3600
    # Regression guard: IANA timezone data must keep DST jump (23h instead of 24h).
    assert int(sleeps[1].total_seconds()) == 82800, (
        "Expected 23h across DST boundary; if this is 86400, check tzdata/ZoneInfo availability."
    )
