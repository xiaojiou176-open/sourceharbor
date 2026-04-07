from __future__ import annotations

import os
import sys
import types
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from worker import main as worker_main
from worker.temporal import activities as temporal_activities
from worker.temporal.activities import _build_daily_digest_markdown, cleanup_workspace_media_files


def _ensure_required_worker_env(
    monkeypatch,
    *,
    tmp_path_factory,
) -> Path:
    env_root = tmp_path_factory.mktemp("worker-temporal-tests")
    monkeypatch.setenv("SQLITE_PATH", str((env_root / "state.db").resolve()))
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor",
    )
    monkeypatch.setenv("TEMPORAL_TARGET_HOST", "localhost:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "default")
    monkeypatch.setenv("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
    monkeypatch.setenv("PIPELINE_WORKSPACE_DIR", str((env_root / "workspace").resolve()))
    monkeypatch.setenv("PIPELINE_ARTIFACT_ROOT", str((env_root / "artifacts").resolve()))
    return env_root


def _set_mtime(path: Path, dt: datetime) -> None:
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


def test_cleanup_workspace_media_files_removes_old_media_and_keeps_digest(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    downloads = base / "job-1" / "downloads"
    frames = base / "job-1" / "frames"
    artifacts = base / "job-1" / "artifacts"
    downloads.mkdir(parents=True)
    frames.mkdir(parents=True)
    artifacts.mkdir(parents=True)

    media_file = downloads / "media.mp4"
    frame_file = frames / "frame_001.jpg"
    digest_file = artifacts / "digest.md"
    media_file.write_text("video", encoding="utf-8")
    frame_file.write_text("image", encoding="utf-8")
    digest_file.write_text("keep", encoding="utf-8")

    now_utc = datetime(2026, 2, 21, 12, 0, tzinfo=UTC)
    old_utc = now_utc - timedelta(days=2)
    _set_mtime(media_file, old_utc)
    _set_mtime(frame_file, old_utc)
    _set_mtime(digest_file, old_utc)

    result = cleanup_workspace_media_files(
        workspace_dir=str(base),
        older_than_hours=24,
        now_utc=now_utc,
    )

    assert result["ok"] is True
    assert result["deleted_files"] == 2
    assert not media_file.exists()
    assert not frame_file.exists()
    assert digest_file.exists()


def test_build_daily_digest_markdown_contains_counts_and_rows() -> None:
    rows = [
        {
            "job_id": "job-1",
            "status": "succeeded",
            "pipeline_final_status": "succeeded",
            "updated_at": datetime(2026, 2, 21, 8, 0, tzinfo=UTC),
            "platform": "youtube",
            "title": "Video A",
        },
        {
            "job_id": "job-2",
            "status": "succeeded",
            "pipeline_final_status": "degraded",
            "updated_at": datetime(2026, 2, 21, 9, 0, tzinfo=UTC),
            "platform": "bilibili",
            "title": "Video B",
        },
    ]

    markdown = _build_daily_digest_markdown(
        digest_day=date(2026, 2, 21),
        offset_minutes=480,
        jobs=rows,
    )

    assert "# Daily Digest 2026-02-21" in markdown
    assert "- Succeeded: 1" in markdown
    assert "- Degraded: 1" in markdown
    assert "| job-1 | succeeded | youtube | Video A |" in markdown
    assert "| job-2 | succeeded | bilibili | Video B |" in markdown


def test_to_html_renders_markdown_elements() -> None:
    html = temporal_activities._to_html("# 标题\n\n- 一\n- 二\n\n[链接](https://example.com)")
    assert "<h1>标题</h1>" in html
    assert "<li>一</li>" in html
    assert '<a href="https://example.com">链接</a>' in html


class _FakeMappingsResult:
    def __init__(self, *, first_row: dict | None = None, one_row: dict | None = None):
        self._first_row = first_row
        self._one_row = one_row

    def mappings(self) -> _FakeMappingsResult:
        return self

    def first(self):
        return self._first_row

    def one(self):
        if self._one_row is None:
            raise AssertionError("one() called without a row")
        return self._one_row


class _CaptureNotificationConn:
    def __init__(self, *, existing_row: dict | None = None):
        self._existing_row = existing_row
        self.executed_sql: list[str] = []

    def execute(self, statement, params=None):
        sql = getattr(statement, "text", str(statement))
        normalized = " ".join(sql.split())
        self.executed_sql.append(normalized)
        if "SELECT pg_advisory_xact_lock" in normalized:
            return _FakeMappingsResult()
        if "INSERT INTO notification_deliveries" in normalized:
            return _FakeMappingsResult(
                one_row={
                    "delivery_id": "delivery-1",
                    "status": "queued",
                    "recipient_email": "notify@example.com",
                    "subject": "[SourceHarbor] Video digest Demo",
                }
            )
        if "FROM notification_deliveries" in normalized:
            return _FakeMappingsResult(first_row=self._existing_row)
        return _FakeMappingsResult()


def test_video_digest_delivery_sql_uses_video_digest_kind() -> None:
    conn = _CaptureNotificationConn(existing_row=None)

    created = temporal_activities._insert_video_digest_delivery(
        conn,
        job={"job_id": "00000000-0000-0000-0000-000000000001"},
        recipient_email="notify@example.com",
        subject="[SourceHarbor] Video digest Demo",
        payload_json={"digest_scope": "video"},
    )

    assert created is not None
    assert created["delivery_id"] == "delivery-1"

    notification_sql = [item for item in conn.executed_sql if "notification_deliveries" in item]
    assert any("WHERE kind = 'video_digest'" in item for item in notification_sql)
    assert any("status IN ('queued', 'sent', 'skipped')" in item for item in notification_sql)
    assert any(
        "status = 'failed' AND next_retry_at IS NOT NULL" in item for item in notification_sql
    )
    assert not any("kind = 'daily_digest'" in item for item in notification_sql)
    assert any(
        "INSERT INTO notification_deliveries" in item and "'video_digest'" in item
        for item in notification_sql
    )


def test_get_existing_video_digest_sql_excludes_non_retryable_failed() -> None:
    existing_row = {
        "delivery_id": "delivery-1",
        "status": "queued",
        "recipient_email": "notify@example.com",
        "subject": "[SourceHarbor] Video digest Demo",
    }
    conn = _CaptureNotificationConn(existing_row=existing_row)

    existing = temporal_activities._get_existing_video_digest(
        conn,
        job_id="00000000-0000-0000-0000-000000000001",
    )

    assert existing is not None
    assert existing["delivery_id"] == "delivery-1"
    assert any("status IN ('queued', 'sent', 'skipped')" in item for item in conn.executed_sql)
    assert any(
        "status = 'failed' AND next_retry_at IS NOT NULL" in item for item in conn.executed_sql
    )


def test_daily_digest_delivery_sql_reuses_retryable_failed_rows() -> None:
    conn = _CaptureNotificationConn(existing_row=None)

    created = temporal_activities._insert_daily_digest_delivery(
        conn,
        digest_date=date(2026, 2, 21),
        recipient_email="notify@example.com",
        subject="[SourceHarbor] Daily digest 2026-02-21",
        payload_json={"digest_scope": "daily", "digest_date": "2026-02-21"},
    )

    assert created is not None
    notification_sql = [item for item in conn.executed_sql if "notification_deliveries" in item]
    assert any("WHERE kind = 'daily_digest'" in item for item in notification_sql)
    assert any("status IN ('queued', 'sent', 'skipped')" in item for item in notification_sql)
    assert any(
        "status = 'failed' AND next_retry_at IS NOT NULL" in item for item in notification_sql
    )


def test_get_existing_daily_digest_sql_excludes_non_retryable_failed() -> None:
    existing_row = {
        "delivery_id": "delivery-daily-1",
        "status": "queued",
        "recipient_email": "notify@example.com",
        "subject": "[SourceHarbor] Daily digest 2026-02-21",
    }
    conn = _CaptureNotificationConn(existing_row=existing_row)

    existing = temporal_activities._get_existing_daily_digest(
        conn,
        digest_date=date(2026, 2, 21),
    )

    assert existing is not None
    assert existing["delivery_id"] == "delivery-daily-1"
    assert any("status IN ('queued', 'sent', 'skipped')" in item for item in conn.executed_sql)
    assert any(
        "status = 'failed' AND next_retry_at IS NOT NULL" in item for item in conn.executed_sql
    )


def test_send_video_digest_activity_duplicate_job_skips_second_send(monkeypatch) -> None:
    import asyncio

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

    state = {"insert_calls": 0, "send_calls": 0}
    job_id = "00000000-0000-0000-0000-000000000001"

    monkeypatch.setattr(temporal_activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        temporal_activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                notification_enabled=True,
                resend_api_key=None,
                resend_from_email=None,
            )
        ),
    )
    monkeypatch.setattr(
        temporal_activities,
        "_fetch_job_digest_record",
        lambda _conn, *, job_id: {
            "job_id": job_id,
            "title": "Demo",
            "video_uid": "demo-uid",
            "status": "succeeded",
            "pipeline_final_status": "succeeded",
            "artifact_digest_md": "",
            "platform": "youtube",
            "source_url": "https://example.com/video",
        },
    )
    monkeypatch.setattr(
        temporal_activities,
        "_get_or_init_notification_config",
        lambda _conn: {
            "enabled": True,
            "daily_digest_enabled": True,
            "to_email": "notify@example.com",
        },
    )
    monkeypatch.setattr(temporal_activities, "_safe_read_text", lambda _path: "digest content")

    def _fake_insert(_conn, *, job, recipient_email, subject, payload_json):
        state["insert_calls"] += 1
        if state["insert_calls"] == 1:
            return {
                "delivery_id": "delivery-1",
                "status": "queued",
                "recipient_email": recipient_email,
                "subject": subject,
            }
        return None

    monkeypatch.setattr(temporal_activities, "_insert_video_digest_delivery", _fake_insert)
    monkeypatch.setattr(
        temporal_activities,
        "_get_existing_video_digest",
        lambda _conn, *, job_id: {"delivery_id": "delivery-1", "status": "sent"},
    )

    def _fake_send_with_resend(
        *,
        to_email: str,
        subject: str,
        text_body: str,
        resend_api_key: str | None,
        resend_from_email: str | None,
        idempotency_key: str | None = None,
    ) -> str:
        assert resend_api_key is None
        assert resend_from_email is None
        assert idempotency_key == "delivery-initial:delivery-1"
        state["send_calls"] += 1
        return f"msg-{state['send_calls']}"

    monkeypatch.setattr(temporal_activities, "_send_with_resend", _fake_send_with_resend)

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
    ) -> dict:
        return {
            "delivery_id": delivery_id,
            "status": status,
            "provider_message_id": provider_message_id,
            "error_message": error_message,
            "sent_at": datetime(2026, 2, 21, 12, 0, tzinfo=UTC) if sent else None,
            "attempt_count": 1 if record_attempt else 0,
            "last_error_kind": last_error_kind,
            "next_retry_at": next_retry_at,
        }

    monkeypatch.setattr(temporal_activities, "_mark_delivery_state", _fake_mark_delivery_state)

    first = asyncio.run(temporal_activities.send_video_digest_activity({"job_id": job_id}))
    second = asyncio.run(temporal_activities.send_video_digest_activity({"job_id": job_id}))

    assert first["ok"] is True
    assert first["status"] == "sent"
    assert second["ok"] is True
    assert second["skipped"] is True
    assert second["reason"] == "duplicate_delivery"
    assert state["send_calls"] == 1


def test_send_video_digest_ignores_daily_digest_switch(monkeypatch) -> None:
    import asyncio

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

    monkeypatch.setattr(temporal_activities, "PostgresBusinessStore", _DummyPostgresStore)
    monkeypatch.setattr(
        temporal_activities.Settings,
        "from_env",
        staticmethod(
            lambda: types.SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                notification_enabled=True,
                resend_api_key=None,
                resend_from_email=None,
            )
        ),
    )
    monkeypatch.setattr(
        temporal_activities,
        "_fetch_job_digest_record",
        lambda _conn, *, job_id: {
            "job_id": job_id,
            "title": "Demo",
            "video_uid": "demo-uid",
            "status": "succeeded",
            "pipeline_final_status": "succeeded",
            "artifact_digest_md": "",
            "platform": "youtube",
            "source_url": "https://example.com/video",
        },
    )
    monkeypatch.setattr(
        temporal_activities,
        "_get_or_init_notification_config",
        lambda _conn: {
            "enabled": True,
            "daily_digest_enabled": False,
            "to_email": "notify@example.com",
        },
    )
    monkeypatch.setattr(
        temporal_activities,
        "_insert_video_digest_delivery",
        lambda _conn, *, job, recipient_email, subject, payload_json: {
            "delivery_id": "delivery-1",
            "status": "queued",
            "recipient_email": recipient_email,
            "subject": subject,
        },
    )
    monkeypatch.setattr(
        temporal_activities,
        "_safe_read_text",
        lambda _path: "digest content",
    )
    monkeypatch.setattr(
        temporal_activities,
        "_send_with_resend",
        lambda **_: "msg-1",
    )
    monkeypatch.setattr(
        temporal_activities,
        "_mark_delivery_state",
        lambda _pg_store, **kwargs: {
            "delivery_id": kwargs["delivery_id"],
            "status": kwargs["status"],
            "provider_message_id": kwargs.get("provider_message_id"),
            "error_message": kwargs.get("error_message"),
            "sent_at": datetime(2026, 2, 21, 12, 0, tzinfo=UTC),
            "attempt_count": 1,
        },
    )

    result = asyncio.run(
        temporal_activities.send_video_digest_activity(
            {"job_id": "00000000-0000-0000-0000-000000000001"}
        )
    )

    assert result["ok"] is True
    assert result["status"] == "sent"


class _FakeHandle:
    def __init__(self, *, workflow_id: str, run_id: str, result_payload: dict):
        self.id = workflow_id
        self.run_id = run_id
        self.first_execution_run_id = run_id
        self._payload = result_payload

    async def result(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, *, handle: _FakeHandle):
        self._handle = handle
        self.calls: list[dict] = []

    async def start_workflow(self, workflow_run, payload, *, id: str, task_queue: str, **kwargs):
        self.calls.append(
            {
                "workflow_run": workflow_run,
                "payload": payload,
                "id": id,
                "task_queue": task_queue,
                "kwargs": kwargs,
            }
        )
        self._handle.id = id
        return self._handle


def _install_temporal_stubs(monkeypatch) -> type[Exception]:
    temporalio_mod = types.ModuleType("temporalio")
    exceptions_mod = types.ModuleType("temporalio.exceptions")

    class WorkflowAlreadyStartedError(Exception):
        pass

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    temporalio_mod.exceptions = exceptions_mod

    monkeypatch.setitem(sys.modules, "temporalio", temporalio_mod)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)

    workflows_mod = types.ModuleType("worker.temporal.workflows")

    class DailyDigestWorkflow:
        async def run(self, payload: dict | None = None):
            return payload or {}

    class CleanupWorkspaceWorkflow:
        async def run(self, payload: dict | None = None):
            return payload or {}

    workflows_mod.DailyDigestWorkflow = DailyDigestWorkflow
    workflows_mod.CleanupWorkspaceWorkflow = CleanupWorkspaceWorkflow
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)

    return WorkflowAlreadyStartedError


async def _run_start_daily_for_test(
    *, run_once: bool, monkeypatch, tmp_path_factory
) -> tuple[dict, _FakeClient]:
    _install_temporal_stubs(monkeypatch)
    _ensure_required_worker_env(monkeypatch, tmp_path_factory=tmp_path_factory)
    handle = _FakeHandle(
        workflow_id="daily-id",
        run_id="daily-run",
        result_payload={"ok": True, "status": "sent"},
    )
    client = _FakeClient(handle=handle)

    async def _fake_connect(_settings):
        return client

    monkeypatch.setattr(worker_main, "_connect_temporal", _fake_connect)
    settings = worker_main.Settings.from_env()
    result = await worker_main.start_daily_workflow(
        settings,
        run_once=run_once,
        local_hour=9,
        timezone_offset_minutes=480,
        workflow_id="daily-digest-workflow",
    )
    return result, client


def test_start_daily_workflow_scheduler_mode_returns_started(monkeypatch, tmp_path_factory):
    import asyncio

    result, client = asyncio.run(
        _run_start_daily_for_test(
            run_once=False,
            monkeypatch=monkeypatch,
            tmp_path_factory=tmp_path_factory,
        )
    )

    assert result["ok"] is True
    assert result["status"] == "started"
    assert result["run_once"] is False
    assert client.calls[0]["payload"]["local_hour"] == 9
    assert client.calls[0]["payload"]["timezone_offset_minutes"] == 480


def test_start_daily_workflow_run_once_waits_result(monkeypatch, tmp_path_factory):
    import asyncio

    result, _client = asyncio.run(
        _run_start_daily_for_test(
            run_once=True,
            monkeypatch=monkeypatch,
            tmp_path_factory=tmp_path_factory,
        )
    )

    assert result == {"ok": True, "status": "sent"}


def test_start_cleanup_workflow_waits_result(monkeypatch, tmp_path_factory, tmp_path: Path):
    import asyncio

    _install_temporal_stubs(monkeypatch)
    _ensure_required_worker_env(monkeypatch, tmp_path_factory=tmp_path_factory)
    handle = _FakeHandle(
        workflow_id="cleanup-id",
        run_id="cleanup-run",
        result_payload={"ok": True, "deleted_files": 3},
    )
    client = _FakeClient(handle=handle)

    async def _fake_connect(_settings):
        return client

    monkeypatch.setattr(worker_main, "_connect_temporal", _fake_connect)
    settings = worker_main.Settings.from_env()
    workspace_dir = str((tmp_path / "demo").resolve())
    result = asyncio.run(
        worker_main.start_cleanup_workflow(
            settings,
            older_than_hours=24,
            workspace_dir=workspace_dir,
        )
    )

    assert result == {"ok": True, "deleted_files": 3}
    assert client.calls[0]["payload"]["older_than_hours"] == 24
    assert client.calls[0]["payload"]["workspace_dir"] == workspace_dir
