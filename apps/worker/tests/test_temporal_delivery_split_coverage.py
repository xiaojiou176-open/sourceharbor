from __future__ import annotations

import asyncio
import types
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any

import pytest
from worker.temporal import activities_delivery
from worker.temporal.activities_delivery_retry import retry_failed_deliveries_activity_impl
from worker.temporal.activities_delivery_send import (
    send_daily_digest_activity_impl,
    send_video_digest_activity_impl,
)


class _FakeMappingsResult:
    def __init__(
        self,
        *,
        first_row: dict[str, Any] | None = None,
        one_row: dict[str, Any] | None = None,
        all_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self._first_row = first_row
        self._one_row = one_row
        self._all_rows = all_rows or []

    def mappings(self) -> _FakeMappingsResult:
        return self

    def first(self) -> dict[str, Any] | None:
        return self._first_row

    def one(self) -> dict[str, Any]:
        if self._one_row is None:
            raise AssertionError("one() called without row")
        return self._one_row

    def all(self) -> list[dict[str, Any]]:
        return self._all_rows


class _ScriptedConn:
    def __init__(self, results: list[_FakeMappingsResult]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeMappingsResult:
        sql = getattr(statement, "text", str(statement))
        self.calls.append({"sql": " ".join(sql.split()), "params": params or {}})
        if self._results:
            return self._results.pop(0)
        return _FakeMappingsResult()


class _BeginCtx:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def __enter__(self) -> Any:
        return self._conn

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class _FakeEngine:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def begin(self) -> _BeginCtx:
        return _BeginCtx(self._conn)


class _FakeStore:
    def __init__(self, conn: Any) -> None:
        self._engine = _FakeEngine(conn)


class _RetryStore:
    def __init__(self, *, supported: bool, lease: Any) -> None:
        self._engine = _FakeEngine(object())
        self._supported = supported
        self._lease = lease
        self.released: list[Any] = []

    def try_acquire_advisory_lock(self, *, lock_key: str) -> tuple[bool, Any, str | None]:
        return (self._supported, self._lease, None)

    def release_advisory_lock(self, lease: Any) -> None:
        self.released.append(lease)


def _settings() -> Any:
    return types.SimpleNamespace(
        notification_enabled=True,
        resend_api_key="rk_test",
        resend_from_email="digest@example.com",
    )


def test_get_or_init_notification_config_branches() -> None:
    existing_conn = _ScriptedConn(
        [
            _FakeMappingsResult(
                first_row={
                    "enabled": True,
                    "to_email": "notify@example.com",
                    "daily_digest_enabled": False,
                }
            )
        ]
    )
    existing = activities_delivery._get_or_init_notification_config(existing_conn)
    assert existing["enabled"] is True
    assert existing["to_email"] == "notify@example.com"

    created_conn = _ScriptedConn(
        [
            _FakeMappingsResult(first_row=None),
            _FakeMappingsResult(),
            _FakeMappingsResult(
                first_row={"enabled": False, "to_email": None, "daily_digest_enabled": True}
            ),
        ]
    )
    created = activities_delivery._get_or_init_notification_config(created_conn)
    assert created == {"enabled": False, "to_email": None, "daily_digest_enabled": True}

    fallback_conn = _ScriptedConn(
        [
            _FakeMappingsResult(first_row=None),
            _FakeMappingsResult(),
            _FakeMappingsResult(first_row=None),
        ]
    )
    fallback = activities_delivery._get_or_init_notification_config(fallback_conn)
    assert fallback == {"enabled": False, "to_email": None, "daily_digest_enabled": False}


def test_mark_delivery_state_success_conflict_and_missing() -> None:
    success_conn = _ScriptedConn(
        [
            _FakeMappingsResult(
                first_row={
                    "delivery_id": "delivery-1",
                    "status": "sent",
                    "attempt_count": 1,
                }
            )
        ]
    )
    success_store = _FakeStore(success_conn)
    success = activities_delivery._mark_delivery_state(
        success_store,
        delivery_id="delivery-1",
        status="sent",
        record_attempt=True,
    )
    assert success["status"] == "sent"

    conflict_conn = _ScriptedConn(
        [
            _FakeMappingsResult(first_row=None),
            _FakeMappingsResult(first_row={"delivery_id": "delivery-2", "status": "queued"}),
        ]
    )
    conflict_store = _FakeStore(conflict_conn)
    conflict = activities_delivery._mark_delivery_state(
        conflict_store,
        delivery_id="delivery-2",
        status="failed",
        expected_status="queued",
        expected_attempt_count=1,
    )
    assert conflict["conflict"] is True
    assert conflict["expected_status"] == "queued"
    assert conflict["expected_attempt_count"] == 1

    missing_conn = _ScriptedConn(
        [_FakeMappingsResult(first_row=None), _FakeMappingsResult(first_row=None)]
    )
    missing_store = _FakeStore(missing_conn)
    with pytest.raises(ValueError, match="delivery not found"):
        activities_delivery._mark_delivery_state(
            missing_store,
            delivery_id="delivery-missing",
            status="failed",
        )


def test_fetch_job_and_insert_duplicate_helpers() -> None:
    found_conn = _ScriptedConn(
        [_FakeMappingsResult(first_row={"job_id": "job-1", "title": "Demo"})]
    )
    found = activities_delivery._fetch_job_digest_record(found_conn, job_id="job-1")
    assert found["job_id"] == "job-1"

    missing_conn = _ScriptedConn([_FakeMappingsResult(first_row=None)])
    with pytest.raises(ValueError, match="job not found"):
        activities_delivery._fetch_job_digest_record(missing_conn, job_id="job-missing")

    video_conn = _ScriptedConn(
        [
            _FakeMappingsResult(),
            _FakeMappingsResult(first_row={"delivery_id": "delivery-video-1"}),
        ]
    )
    assert (
        activities_delivery._insert_video_digest_delivery(
            video_conn,
            job={"job_id": "00000000-0000-0000-0000-000000000001"},
            recipient_email="notify@example.com",
            subject="video",
            payload_json={"digest_scope": "video"},
        )
        is None
    )

    daily_conn = _ScriptedConn(
        [
            _FakeMappingsResult(),
            _FakeMappingsResult(first_row={"delivery_id": "delivery-daily-1"}),
        ]
    )
    assert (
        activities_delivery._insert_daily_digest_delivery(
            daily_conn,
            digest_date=date(2026, 2, 21),
            recipient_email="notify@example.com",
            subject="daily",
            payload_json={"digest_scope": "daily", "digest_date": "2026-02-21"},
        )
        is None
    )


def test_insert_helpers_create_and_existing_lookup_branches() -> None:
    created_video_conn = _ScriptedConn(
        [
            _FakeMappingsResult(),
            _FakeMappingsResult(first_row=None),
            _FakeMappingsResult(
                one_row={
                    "delivery_id": "delivery-video-created",
                    "status": "queued",
                    "recipient_email": "notify@example.com",
                    "subject": "video",
                    "attempt_count": 0,
                    "last_attempt_at": None,
                    "next_retry_at": None,
                    "last_error_kind": None,
                }
            ),
        ]
    )
    created_video = activities_delivery._insert_video_digest_delivery(
        created_video_conn,
        job={"job_id": "00000000-0000-0000-0000-000000000002"},
        recipient_email="notify@example.com",
        subject="video",
        payload_json={"digest_scope": "video"},
    )
    assert created_video is not None
    assert created_video["delivery_id"] == "delivery-video-created"

    created_daily_conn = _ScriptedConn(
        [
            _FakeMappingsResult(),
            _FakeMappingsResult(first_row=None),
            _FakeMappingsResult(
                one_row={
                    "delivery_id": "delivery-daily-created",
                    "status": "queued",
                    "recipient_email": "notify@example.com",
                    "subject": "daily",
                    "attempt_count": 0,
                    "last_attempt_at": None,
                    "next_retry_at": None,
                    "last_error_kind": None,
                }
            ),
        ]
    )
    created_daily = activities_delivery._insert_daily_digest_delivery(
        created_daily_conn,
        digest_date=date(2026, 2, 22),
        recipient_email="notify@example.com",
        subject="daily",
        payload_json={"digest_scope": "daily", "digest_date": "2026-02-22"},
    )
    assert created_daily is not None
    assert created_daily["delivery_id"] == "delivery-daily-created"

    existing_video_conn = _ScriptedConn(
        [
            _FakeMappingsResult(
                first_row={
                    "delivery_id": "delivery-video-existing",
                    "status": "queued",
                }
            )
        ]
    )
    existing_video = activities_delivery._get_existing_video_digest(
        existing_video_conn,
        job_id="00000000-0000-0000-0000-000000000003",
    )
    assert existing_video is not None
    assert existing_video["delivery_id"] == "delivery-video-existing"

    no_video_conn = _ScriptedConn([_FakeMappingsResult(first_row=None)])
    assert (
        activities_delivery._get_existing_video_digest(
            no_video_conn,
            job_id="00000000-0000-0000-0000-000000000004",
        )
        is None
    )

    existing_daily_conn = _ScriptedConn(
        [
            _FakeMappingsResult(
                first_row={
                    "delivery_id": "delivery-daily-existing",
                    "status": "failed",
                }
            )
        ]
    )
    existing_daily = activities_delivery._get_existing_daily_digest(
        existing_daily_conn,
        digest_date=date(2026, 2, 22),
    )
    assert existing_daily is not None
    assert existing_daily["delivery_id"] == "delivery-daily-existing"

    no_daily_conn = _ScriptedConn([_FakeMappingsResult(first_row=None)])
    assert (
        activities_delivery._get_existing_daily_digest(
            no_daily_conn,
            digest_date=date(2026, 2, 22),
        )
        is None
    )


def test_delivery_wrapper_helpers_cover_passthrough(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        activities_delivery,
        "_claim_due_failed_deliveries",
        lambda conn, *, limit: [{"delivery_id": "delivery-1", "limit": limit}],
    )
    rows = activities_delivery._load_due_failed_deliveries(object(), limit=5)
    assert rows == [{"delivery_id": "delivery-1", "limit": 5}]

    payload = {
        "digest_date": "2026-02-21",
        "timezone_name": "Asia/Shanghai",
        "timezone_offset_minutes": "480",
    }
    assert activities_delivery._extract_daily_digest_date(payload) == date(2026, 2, 21)
    assert activities_delivery._extract_timezone_name(payload) == "Asia/Shanghai"
    assert activities_delivery._extract_timezone_offset_minutes(payload) == 480


async def _run_retry_impl(
    *,
    store: Any,
    due_deliveries: list[dict[str, Any]],
    normalize_email: Any,
    mark_delivery_state: Any,
    send_with_resend: Any,
    kind_handlers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind_handlers = kind_handlers or {}
    return await retry_failed_deliveries_activity_impl(
        settings=_settings(),
        pg_store=store,
        payload={"limit": 10},
        coerce_int=lambda value, fallback=0: int(value or fallback),
        claim_due_failed_deliveries=lambda _conn, *, limit: due_deliveries,
        normalize_email=normalize_email,
        build_retry_failure_payload=lambda **_: (
            "transient",
            datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
        ),
        mark_delivery_state=mark_delivery_state,
        fetch_job_digest_record=kind_handlers.get(
            "fetch_job_digest_record",
            lambda _conn, *, job_id: {"job_id": job_id, "artifact_digest_md": ""},
        ),
        safe_read_text=lambda _path: "digest",
        build_video_digest_markdown=lambda _job, _md: "video-body",
        extract_daily_digest_date=kind_handlers.get(
            "extract_daily_digest_date", lambda _payload: None
        ),
        extract_timezone_name=kind_handlers.get("extract_timezone_name", lambda _payload: "UTC"),
        extract_timezone_offset_minutes=kind_handlers.get(
            "extract_timezone_offset_minutes", lambda _payload: 0
        ),
        resolve_local_digest_date=kind_handlers.get(
            "resolve_local_digest_date", lambda **_: date(2026, 2, 21)
        ),
        load_daily_digest_jobs=kind_handlers.get(
            "load_daily_digest_jobs", lambda *_args, **_kwargs: []
        ),
        build_daily_digest_markdown=kind_handlers.get(
            "build_daily_digest_markdown", lambda **_: "daily-body"
        ),
        send_with_resend=send_with_resend,
    )


def test_retry_impl_branch_missing_recipient_and_missing_job_id() -> None:
    store = _RetryStore(supported=False, lease=None)

    failed_calls: list[dict[str, Any]] = []

    def _mark_state(_store: Any, **kwargs: Any) -> dict[str, Any]:
        failed_calls.append(dict(kwargs))
        return {
            "status": kwargs["status"],
            "error_message": kwargs.get("error_message"),
            "next_retry_at": kwargs.get("next_retry_at"),
            "conflict": False,
        }

    missing_recipient = asyncio.run(
        _run_retry_impl(
            store=store,
            due_deliveries=[
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
            normalize_email=lambda _value: None,
            mark_delivery_state=_mark_state,
            send_with_resend=lambda **_: "provider-msg",
        )
    )
    assert missing_recipient["failed"] == 1
    assert missing_recipient["retry_scheduled"] == 1

    failed_calls.clear()
    missing_job = asyncio.run(
        _run_retry_impl(
            store=store,
            due_deliveries=[
                {
                    "delivery_id": "delivery-2",
                    "kind": "video_digest",
                    "recipient_email": "notify@example.com",
                    "subject": "Digest",
                    "payload_json": {},
                    "job_id": "",
                    "attempt_count": 0,
                }
            ],
            normalize_email=str,
            mark_delivery_state=_mark_state,
            send_with_resend=lambda **_: "provider-msg",
        )
    )
    assert missing_job["failed"] == 1
    assert "missing job_id" in str(failed_calls[0]["error_message"])


def test_retry_impl_daily_digest_and_unsupported_kind() -> None:
    lease = object()
    store = _RetryStore(supported=True, lease=lease)

    state_calls: list[dict[str, Any]] = []

    def _mark_state(_store: Any, **kwargs: Any) -> dict[str, Any]:
        state_calls.append(dict(kwargs))
        return {
            "status": kwargs["status"],
            "conflict": False,
        }

    daily = asyncio.run(
        _run_retry_impl(
            store=store,
            due_deliveries=[
                {
                    "delivery_id": "delivery-daily-1",
                    "kind": "daily_digest",
                    "recipient_email": "notify@example.com",
                    "subject": "Daily",
                    "payload_json": {},
                    "attempt_count": 2,
                }
            ],
            normalize_email=str,
            mark_delivery_state=_mark_state,
            send_with_resend=lambda **_: "provider-msg",
        )
    )
    assert daily["sent"] == 1
    assert store.released == [lease]

    state_calls.clear()
    unsupported = asyncio.run(
        _run_retry_impl(
            store=_RetryStore(supported=False, lease=None),
            due_deliveries=[
                {
                    "delivery_id": "delivery-x",
                    "kind": "unknown_kind",
                    "recipient_email": "notify@example.com",
                    "subject": "Unknown",
                    "payload_json": {},
                    "attempt_count": 0,
                }
            ],
            normalize_email=str,
            mark_delivery_state=_mark_state,
            send_with_resend=lambda **_: "provider-msg",
        )
    )
    assert unsupported["failed"] == 1
    assert "unsupported retry kind" in str(state_calls[0]["error_message"])


def test_send_video_digest_impl_skip_recipient_and_runtime_error() -> None:
    store = _FakeStore(object())

    skipped = asyncio.run(
        send_video_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"job_id": "job-1"},
            fetch_job_digest_record=lambda _conn, *, job_id: {
                "job_id": job_id,
                "title": "Demo",
                "video_uid": "v1",
                "status": "succeeded",
                "pipeline_final_status": "succeeded",
                "artifact_digest_md": "",
            },
            get_or_init_notification_config=lambda _conn: {"to_email": "notify@example.com"},
            normalize_email=str,
            prepare_delivery_skip_reason=lambda **_: "notifications_disabled",
            safe_read_text=lambda _path: "digest",
            build_video_digest_markdown=lambda _job, _md: "body",
            insert_video_digest_delivery=lambda _conn, **_: {
                "delivery_id": "delivery-video-skip",
                "subject": "subject",
                "attempt_count": 0,
            },
            get_existing_video_digest=lambda _conn, *, job_id: None,
            mark_delivery_state=lambda _store, **kwargs: {"status": kwargs["status"]},
            classify_delivery_error=lambda _message: "transient",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: "msg",
        )
    )
    assert skipped["skipped"] is True
    assert skipped["reason"] == "notifications_disabled"

    missing_recipient = asyncio.run(
        send_video_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"job_id": "job-2"},
            fetch_job_digest_record=lambda _conn, *, job_id: {
                "job_id": job_id,
                "title": "Demo",
                "video_uid": "v1",
                "status": "succeeded",
                "pipeline_final_status": "succeeded",
                "artifact_digest_md": "",
            },
            get_or_init_notification_config=lambda _conn: {"to_email": None},
            normalize_email=lambda _value: None,
            prepare_delivery_skip_reason=lambda **_: None,
            safe_read_text=lambda _path: "digest",
            build_video_digest_markdown=lambda _job, _md: "body",
            insert_video_digest_delivery=lambda _conn, **_: {
                "delivery_id": "delivery-video-no-recipient",
                "subject": "subject",
                "attempt_count": 1,
            },
            get_existing_video_digest=lambda _conn, *, job_id: None,
            mark_delivery_state=lambda _store, **kwargs: {
                "status": kwargs["status"],
                "error_message": kwargs["error_message"],
                "last_error_kind": kwargs["last_error_kind"],
                "attempt_count": 2,
                "next_retry_at": kwargs["next_retry_at"],
            },
            classify_delivery_error=lambda _message: "config_error",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: "msg",
        )
    )
    assert missing_recipient["ok"] is False
    assert missing_recipient["last_error_kind"] == "config_error"

    runtime_failed = asyncio.run(
        send_video_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"job_id": "job-3"},
            fetch_job_digest_record=lambda _conn, *, job_id: {
                "job_id": job_id,
                "title": "Demo",
                "video_uid": "v1",
                "status": "succeeded",
                "pipeline_final_status": "succeeded",
                "artifact_digest_md": "",
            },
            get_or_init_notification_config=lambda _conn: {"to_email": "notify@example.com"},
            normalize_email=str,
            prepare_delivery_skip_reason=lambda **_: None,
            safe_read_text=lambda _path: "digest",
            build_video_digest_markdown=lambda _job, _md: "body",
            insert_video_digest_delivery=lambda _conn, **_: {
                "delivery_id": "delivery-video-fail",
                "subject": "subject",
                "attempt_count": 0,
            },
            get_existing_video_digest=lambda _conn, *, job_id: None,
            mark_delivery_state=lambda _store, **kwargs: {
                "status": kwargs["status"],
                "error_message": kwargs["error_message"],
                "last_error_kind": kwargs["last_error_kind"],
                "attempt_count": 1,
                "next_retry_at": kwargs["next_retry_at"],
            },
            classify_delivery_error=lambda _message: "transient",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: (_ for _ in ()).throw(RuntimeError("provider_timeout")),
        )
    )
    assert runtime_failed["ok"] is False
    assert runtime_failed["error"] == "provider_timeout"


def test_send_video_digest_impl_duplicate_branch_without_existing_record() -> None:
    result = asyncio.run(
        send_video_digest_activity_impl(
            settings=_settings(),
            pg_store=_FakeStore(object()),
            payload={"job_id": "job-duplicate"},
            fetch_job_digest_record=lambda _conn, *, job_id: {
                "job_id": job_id,
                "title": "Demo",
                "video_uid": "v1",
                "status": "succeeded",
                "pipeline_final_status": "succeeded",
                "artifact_digest_md": "",
            },
            get_or_init_notification_config=lambda _conn: {"to_email": "notify@example.com"},
            normalize_email=str,
            prepare_delivery_skip_reason=lambda **_: None,
            safe_read_text=lambda _path: "digest",
            build_video_digest_markdown=lambda _job, _md: "body",
            insert_video_digest_delivery=lambda _conn, **_: None,
            get_existing_video_digest=lambda _conn, *, job_id: None,
            mark_delivery_state=lambda _store, **kwargs: {"status": kwargs["status"]},
            classify_delivery_error=lambda _message: "transient",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: "provider-msg",
        )
    )
    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "duplicate_delivery"
    assert result["delivery_id"] is None
    assert result["status"] is None


def test_send_daily_digest_impl_duplicate_skip_recipient_and_runtime_error() -> None:
    store = _FakeStore(object())

    duplicate = asyncio.run(
        send_daily_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"digest_date": "2026-02-21"},
            coerce_int=lambda value, fallback=0: int(value or fallback),
            resolve_local_digest_date=lambda **_: date(2026, 2, 21),
            load_daily_digest_jobs=lambda *_args, **_kwargs: [{"job_id": "job-1"}],
            build_daily_digest_markdown=lambda **_: "daily",
            get_or_init_notification_config=lambda _conn: {"to_email": "notify@example.com"},
            normalize_email=str,
            prepare_delivery_skip_reason=lambda **_: None,
            insert_daily_digest_delivery=lambda _conn, **_: None,
            get_existing_daily_digest=lambda _conn, *, digest_date: {
                "delivery_id": "delivery-daily-dup",
                "status": "queued",
            },
            mark_delivery_state=lambda _store, **kwargs: {"status": kwargs["status"]},
            classify_delivery_error=lambda _message: "transient",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: "msg",
        )
    )
    assert duplicate["skipped"] is True
    assert duplicate["reason"] == "duplicate_delivery"

    skipped = asyncio.run(
        send_daily_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"digest_date": "2026-02-21"},
            coerce_int=lambda value, fallback=0: int(value or fallback),
            resolve_local_digest_date=lambda **_: date(2026, 2, 21),
            load_daily_digest_jobs=lambda *_args, **_kwargs: [],
            build_daily_digest_markdown=lambda **_: "daily",
            get_or_init_notification_config=lambda _conn: {"to_email": "notify@example.com"},
            normalize_email=str,
            prepare_delivery_skip_reason=lambda **_: "daily_digest_disabled",
            insert_daily_digest_delivery=lambda _conn, **_: {
                "delivery_id": "delivery-daily-skip",
                "subject": "subject",
                "attempt_count": 0,
            },
            get_existing_daily_digest=lambda _conn, *, digest_date: None,
            mark_delivery_state=lambda _store, **kwargs: {"status": kwargs["status"]},
            classify_delivery_error=lambda _message: "transient",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: "msg",
        )
    )
    assert skipped["skipped"] is True
    assert skipped["reason"] == "daily_digest_disabled"

    missing_recipient = asyncio.run(
        send_daily_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"digest_date": "2026-02-21"},
            coerce_int=lambda value, fallback=0: int(value or fallback),
            resolve_local_digest_date=lambda **_: date(2026, 2, 21),
            load_daily_digest_jobs=lambda *_args, **_kwargs: [{"job_id": "job-1"}],
            build_daily_digest_markdown=lambda **_: "daily",
            get_or_init_notification_config=lambda _conn: {"to_email": None},
            normalize_email=lambda _value: None,
            prepare_delivery_skip_reason=lambda **_: None,
            insert_daily_digest_delivery=lambda _conn, **_: {
                "delivery_id": "delivery-daily-no-recipient",
                "subject": "subject",
                "attempt_count": 1,
            },
            get_existing_daily_digest=lambda _conn, *, digest_date: None,
            mark_delivery_state=lambda _store, **kwargs: {
                "status": kwargs["status"],
                "error_message": kwargs["error_message"],
                "last_error_kind": kwargs["last_error_kind"],
                "attempt_count": 2,
                "next_retry_at": kwargs["next_retry_at"],
            },
            classify_delivery_error=lambda _message: "config_error",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: "msg",
        )
    )
    assert missing_recipient["ok"] is False
    assert missing_recipient["last_error_kind"] == "config_error"

    runtime_failed = asyncio.run(
        send_daily_digest_activity_impl(
            settings=_settings(),
            pg_store=store,
            payload={"digest_date": "2026-02-21"},
            coerce_int=lambda value, fallback=0: int(value or fallback),
            resolve_local_digest_date=lambda **_: date(2026, 2, 21),
            load_daily_digest_jobs=lambda *_args, **_kwargs: [{"job_id": "job-1"}],
            build_daily_digest_markdown=lambda **_: "daily",
            get_or_init_notification_config=lambda _conn: {"to_email": "notify@example.com"},
            normalize_email=str,
            prepare_delivery_skip_reason=lambda **_: None,
            insert_daily_digest_delivery=lambda _conn, **_: {
                "delivery_id": "delivery-daily-fail",
                "subject": "subject",
                "attempt_count": 0,
            },
            get_existing_daily_digest=lambda _conn, *, digest_date: None,
            mark_delivery_state=lambda _store, **kwargs: {
                "status": kwargs["status"],
                "error_message": kwargs["error_message"],
                "last_error_kind": kwargs["last_error_kind"],
                "attempt_count": 1,
                "next_retry_at": kwargs["next_retry_at"],
            },
            classify_delivery_error=lambda _message: "transient",
            resolve_next_retry_at=lambda **_: datetime(2026, 2, 21, 10, 0, tzinfo=UTC),
            send_with_resend=lambda **_: (_ for _ in ()).throw(RuntimeError("provider_timeout")),
        )
    )
    assert runtime_failed["ok"] is False
    assert runtime_failed["error"] == "provider_timeout"
