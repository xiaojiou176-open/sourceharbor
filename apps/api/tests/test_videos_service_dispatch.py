from __future__ import annotations

import asyncio
import builtins
import hashlib
import json
import re
import sys
import types
import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from apps.api.app.errors import ApiTimeoutError
from apps.api.app.services import videos as videos_module
from apps.api.app.services.videos import (
    VideosService,
    _build_process_idempotency_key,
    _extract_video_uid,
    _url_hash,
    _validate_video_source_url,
)


@dataclass
class _JobRow:
    id: uuid.UUID
    status: str
    idempotency_key: str
    mode: str


@dataclass
class _VideoRow:
    id: uuid.UUID


class _RepoStub:
    def __init__(self, *, should_dispatch: bool = True) -> None:
        self.should_dispatch = should_dispatch
        self.created_calls: list[dict[str, Any]] = []
        self.mark_failed_calls: list[dict[str, Any]] = []
        self.job = _JobRow(
            id=uuid.uuid4(),
            status="queued",
            idempotency_key="idem-1",
            mode="full",
        )

    def create_or_reuse(self, **kwargs: Any) -> tuple[_JobRow, bool]:
        self.created_calls.append(dict(kwargs))
        self.job.idempotency_key = str(kwargs["idempotency_key"])
        self.job.mode = str(kwargs["mode"])
        return self.job, self.should_dispatch

    def mark_dispatch_failed(
        self, *, job_id: uuid.UUID, error_message: str, reason: str = "dispatch_failed"
    ) -> _JobRow:
        self.mark_failed_calls.append(
            {
                "job_id": job_id,
                "error_message": error_message,
                "reason": reason,
            }
        )
        self.job.status = "failed"
        return self.job


class _VideoRepoStub:
    def __init__(self) -> None:
        self.video = _VideoRow(id=uuid.uuid4())
        self.upsert_calls: list[dict[str, Any]] = []

    def upsert_for_processing(self, **kwargs: Any) -> _VideoRow:
        self.upsert_calls.append(dict(kwargs))
        return self.video


class _FakeClient:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, Any]] = []

    async def start_workflow(
        self, workflow: str, job_id: str, *, id: str, task_queue: str, **kwargs: Any
    ) -> None:
        self.calls.append(
            {
                "workflow": workflow,
                "job_id": job_id,
                "id": id,
                "task_queue": task_queue,
                "kwargs": kwargs,
            }
        )
        if self.should_fail:
            raise RuntimeError("temporal start failed")


def _install_temporal_modules(
    monkeypatch: pytest.MonkeyPatch, *, client: _FakeClient
) -> list[dict[str, str]]:
    temporalio_mod = types.ModuleType("temporalio")
    temporal_client_mod = types.ModuleType("temporalio.client")
    temporal_common_mod = types.ModuleType("temporalio.common")
    connect_calls: list[dict[str, str]] = []

    class _WorkflowIDReusePolicy:
        REJECT_DUPLICATE = "reject_duplicate"

    class _WorkflowIDConflictPolicy:
        USE_EXISTING = "use_existing"

    class _Client:
        @staticmethod
        async def connect(target_host: str, *, namespace: str):
            connect_calls.append({"target_host": target_host, "namespace": namespace})
            return client

    temporal_client_mod.Client = _Client
    temporal_common_mod.WorkflowIDReusePolicy = _WorkflowIDReusePolicy
    temporal_common_mod.WorkflowIDConflictPolicy = _WorkflowIDConflictPolicy

    monkeypatch.setitem(sys.modules, "temporalio", temporalio_mod)
    monkeypatch.setitem(sys.modules, "temporalio.client", temporal_client_mod)
    monkeypatch.setitem(sys.modules, "temporalio.common", temporal_common_mod)
    return connect_calls


class _WaitForSequence:
    def __init__(self, steps: list[str]) -> None:
        self._steps = iter(steps)
        self.timeouts: list[float] = []

    async def __call__(self, awaitable: Any, timeout: float) -> Any:
        self.timeouts.append(timeout)
        step = next(self._steps, "await")
        if step == "timeout":
            close = getattr(awaitable, "close", None)
            if callable(close):
                close()
            raise TimeoutError
        return await awaitable


async def _run_process(service: VideosService) -> dict[str, Any]:
    return await service.process_video(
        platform="youtube",
        url="https://www.youtube.com/watch?v=abc123",
        video_id=None,
        mode="full",
        overrides={},
        force=False,
    )


class _ListRepoStub:
    def __init__(self, *, result: object) -> None:
        self.result = result
        self.calls: list[dict[str, object | None]] = []

    def list(
        self, *, platform: str | None = None, status: str | None = None, limit: int = 50
    ) -> object:
        self.calls.append({"platform": platform, "status": status, "limit": limit})
        return self.result


def test_list_videos_delegates_default_filters_to_repo() -> None:
    expected_result = [{"id": "v-1"}]
    repo = _ListRepoStub(result=expected_result)
    service = VideosService(db=object())
    service.video_repo = repo  # type: ignore[assignment]

    result = service.list_videos()

    assert result is expected_result
    assert repo.calls == [{"platform": None, "status": None, "limit": 50}]


def test_list_videos_delegates_explicit_filters_to_repo() -> None:
    expected_result = [{"id": "v-2"}]
    repo = _ListRepoStub(result=expected_result)
    service = VideosService(db=object())
    service.video_repo = repo  # type: ignore[assignment]

    result = service.list_videos(platform="youtube", status="ready", limit=7)

    assert result is expected_result
    assert repo.calls == [{"platform": "youtube", "status": "ready", "limit": 7}]


def test_process_video_marks_dispatch_failed_when_temporal_start_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    fake_client = _FakeClient(should_fail=True)
    _install_temporal_modules(monkeypatch, client=fake_client)

    with pytest.raises(RuntimeError, match="failed to start ProcessJobWorkflow"):
        asyncio.run(_run_process(service))

    assert len(repo.mark_failed_calls) == 1
    assert repo.mark_failed_calls[0]["job_id"] == repo.job.id
    assert "temporal start failed" in repo.mark_failed_calls[0]["error_message"]


def test_process_video_uses_deterministic_workflow_id_and_conflict_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    video_repo = _VideoRepoStub()
    service.video_repo = video_repo  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    fake_client = _FakeClient(should_fail=False)
    connect_calls = _install_temporal_modules(monkeypatch, client=fake_client)

    result = asyncio.run(_run_process(service))

    assert set(result.keys()) == {
        "job_id",
        "video_db_id",
        "video_uid",
        "status",
        "idempotency_key",
        "mode",
        "overrides",
        "force",
        "reused",
        "workflow_id",
    }
    assert result["job_id"] == repo.job.id
    assert result["video_db_id"] == video_repo.video.id
    assert result["video_uid"] == "abc123"
    assert result["status"] == "queued"
    assert result["idempotency_key"] == repo.job.idempotency_key
    assert result["mode"] == "full"
    assert result["overrides"] == {}
    assert result["force"] is False
    assert result["workflow_id"] == f"process-job-{repo.job.id}"
    assert result["reused"] is False

    assert len(connect_calls) == 1
    assert connect_calls[0] == {
        "target_host": videos_module.settings.temporal_target_host,
        "namespace": videos_module.settings.temporal_namespace,
    }
    call = fake_client.calls[0]
    assert call["workflow"] == "ProcessJobWorkflow"
    assert call["id"] == f"process-job-{repo.job.id}"
    assert call["task_queue"] == videos_module.settings.temporal_task_queue
    assert call["kwargs"]["id_reuse_policy"] == "reject_duplicate"
    assert call["kwargs"]["id_conflict_policy"] == "use_existing"


def test_process_video_reuses_existing_job_without_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=False)
    service = VideosService(db=object())
    video_repo = _VideoRepoStub()
    service.video_repo = video_repo  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    fake_client = _FakeClient(should_fail=False)
    _install_temporal_modules(monkeypatch, client=fake_client)

    result = asyncio.run(_run_process(service))

    assert result["job_id"] == repo.job.id
    assert result["video_db_id"] == video_repo.video.id
    assert result["status"] == "queued"
    assert result["idempotency_key"] == repo.job.idempotency_key
    assert result["mode"] == "full"
    assert result["overrides"] == {}
    assert result["force"] is False
    assert result["workflow_id"] is None
    assert result["reused"] is True
    assert fake_client.calls == []


def test_process_video_logs_default_trace_and_user_on_reuse(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _RepoStub(should_dispatch=False)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]
    _install_temporal_modules(monkeypatch, client=_FakeClient())

    caplog.set_level("INFO", logger=videos_module.logger.name)
    result = asyncio.run(_run_process(service))

    assert result["reused"] is True
    reused_log = next(
        record for record in caplog.records if record.msg == "video_process_reused_existing_job"
    )
    assert reused_log.trace_id == "missing_trace"
    assert reused_log.user == "system"
    assert reused_log.platform == "youtube"
    assert reused_log.video_uid == "abc123"
    assert reused_log.job_id == str(repo.job.id)


def test_process_video_logs_start_failure_with_context(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    _install_temporal_modules(monkeypatch, client=_FakeClient(should_fail=True))

    caplog.set_level("ERROR", logger=videos_module.logger.name)
    with pytest.raises(RuntimeError, match="failed to start ProcessJobWorkflow"):
        asyncio.run(_run_process(service))

    start_failed_log = next(
        record for record in caplog.records if record.msg == "video_process_temporal_start_failed"
    )
    assert start_failed_log.trace_id == "missing_trace"
    assert start_failed_log.user == "system"
    assert start_failed_log.job_id == str(repo.job.id)
    assert start_failed_log.workflow_id == f"process-job-{repo.job.id}"
    assert "temporal start failed" in start_failed_log.error


def test_process_video_maps_temporal_import_failure_with_context(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    for module_name in ("temporalio", "temporalio.client", "temporalio.common"):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    original_import = builtins.__import__

    def _failing_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in {"temporalio.client", "temporalio.common"}:
            raise ImportError("missing temporal dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _failing_import)

    caplog.set_level("ERROR", logger=videos_module.logger.name)
    with pytest.raises(
        RuntimeError, match="^temporal client not available: missing temporal dependency$"
    ):
        asyncio.run(_run_process(service))

    import_failed_log = next(
        record
        for record in caplog.records
        if record.msg == "video_process_temporal_client_import_failed"
    )
    assert import_failed_log.trace_id == "missing_trace"
    assert import_failed_log.user == "system"
    assert import_failed_log.error == "missing temporal dependency"


def test_process_video_wait_for_uses_configured_temporal_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]
    _install_temporal_modules(monkeypatch, client=_FakeClient())
    wait_for = _WaitForSequence(["await", "await"])
    monkeypatch.setattr("apps.api.app.services.videos.asyncio.wait_for", wait_for)

    result = asyncio.run(_run_process(service))

    assert result["workflow_id"] == f"process-job-{repo.job.id}"
    assert wait_for.timeouts == [
        videos_module.settings.api_temporal_connect_timeout_seconds,
        videos_module.settings.api_temporal_start_timeout_seconds,
    ]


def test_process_video_maps_connect_timeout_to_api_timeout(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]
    _install_temporal_modules(monkeypatch, client=_FakeClient())
    monkeypatch.setattr(
        "apps.api.app.services.videos.asyncio.wait_for", _WaitForSequence(["timeout"])
    )

    caplog.set_level("ERROR", logger=videos_module.logger.name)
    with pytest.raises(ApiTimeoutError) as exc_info:
        asyncio.run(_run_process(service))

    assert exc_info.value.error_code == "TEMPORAL_CONNECT_TIMEOUT"
    assert "temporal connect timed out after" in exc_info.value.detail
    timeout_log = next(
        record
        for record in caplog.records
        if record.msg == "video_process_temporal_connect_timeout"
    )
    assert timeout_log.trace_id == "missing_trace"
    assert timeout_log.user == "system"
    assert timeout_log.job_id == str(repo.job.id)
    assert (
        timeout_log.timeout_seconds == videos_module.settings.api_temporal_connect_timeout_seconds
    )
    assert timeout_log.error == ""
    assert repo.mark_failed_calls == []


def test_process_video_maps_start_timeout_and_marks_dispatch_timeout_reason(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]
    _install_temporal_modules(monkeypatch, client=_FakeClient())
    monkeypatch.setattr(
        "apps.api.app.services.videos.asyncio.wait_for", _WaitForSequence(["await", "timeout"])
    )

    caplog.set_level("ERROR", logger=videos_module.logger.name)
    with pytest.raises(ApiTimeoutError) as exc_info:
        asyncio.run(_run_process(service))

    assert exc_info.value.error_code == "TEMPORAL_WORKFLOW_START_TIMEOUT"
    assert "temporal workflow start timed out after" in exc_info.value.detail
    assert len(repo.mark_failed_calls) == 1
    assert repo.mark_failed_calls[0]["job_id"] == repo.job.id
    assert repo.mark_failed_calls[0]["reason"] == "dispatch_timeout"
    assert "timed out after" in repo.mark_failed_calls[0]["error_message"]
    timeout_log = next(
        record for record in caplog.records if record.msg == "video_process_temporal_start_timeout"
    )
    assert timeout_log.trace_id == "missing_trace"
    assert timeout_log.user == "system"
    assert timeout_log.job_id == str(repo.job.id)
    assert timeout_log.workflow_id == f"process-job-{repo.job.id}"
    assert timeout_log.timeout_seconds == videos_module.settings.api_temporal_start_timeout_seconds
    assert timeout_log.error == ""


def test_process_video_logs_dispatch_started_with_trace_and_actor(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]
    _install_temporal_modules(monkeypatch, client=_FakeClient())

    caplog.set_level("INFO", logger=videos_module.logger.name)
    result = asyncio.run(
        service.process_video(
            platform="youtube",
            url="https://www.youtube.com/watch?v=abc123",
            video_id=None,
            mode="full",
            overrides={},
            force=False,
            trace_id="trace-123",
            user="bob",
        )
    )

    assert result["reused"] is False
    dispatch_log = next(
        record for record in caplog.records if record.msg == "video_process_dispatch_started"
    )
    assert dispatch_log.trace_id == "trace-123"
    assert dispatch_log.user == "bob"
    assert dispatch_log.platform == "youtube"
    assert dispatch_log.video_uid == "abc123"
    assert dispatch_log.job_id == str(repo.job.id)


@pytest.mark.parametrize(
    ("platform", "url", "expected"),
    [
        ("youtube", "https://www.youtube.com/watch?v=abc123", "abc123"),
        ("youtube", "https://youtu.be/short123/extra", "short123"),
        ("youtube", "https://youtu.be/XcoreX", "XcoreX"),
        ("youtube", "https://youtu.be", hashlib.sha256(b"https://youtu.be").hexdigest()),
        (
            "youtube",
            "https://www.youtube.com/watch?list=abc",
            hashlib.sha256(b"https://www.youtube.com/watch?list=abc").hexdigest(),
        ),
        ("bilibili", "https://www.bilibili.com/video/BV1xx411c7mD", "BV1xx411c7mD"),
        (
            "bilibili",
            "https://www.bilibili.com/video/av123456",
            hashlib.sha256(b"https://www.bilibili.com/video/av123456").hexdigest(),
        ),
        (
            "youtube",
            "https://www.bilibili.com/video/BV1xx411c7mD",
            _url_hash("https://www.bilibili.com/video/BV1xx411c7mD"),
        ),
        (
            "bilibili",
            "https://youtu.be/mismatch123",
            hashlib.sha256(b"https://youtu.be/mismatch123").hexdigest(),
        ),
        (
            "other",
            "https://www.youtube.com/watch?v=abc",
            hashlib.sha256(b"https://www.youtube.com/watch?v=abc").hexdigest(),
        ),
        (
            "other",
            "https://example.com/watch?v=abc",
            hashlib.sha256(b"https://example.com/watch?v=abc").hexdigest(),
        ),
    ],
)
def test_extract_video_uid_branch_coverage(platform: str, url: str, expected: str) -> None:
    assert _extract_video_uid(platform=platform, url=url) == expected


def test_url_hash_normalizes_case_and_whitespace() -> None:
    raw = " HTTPS://YOUTU.BE/AbC123 "
    expected = hashlib.sha256(b"https://youtu.be/abc123").hexdigest()
    assert _url_hash(raw) == expected


def test_process_video_passes_expected_repo_params_with_explicit_video_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=False)
    video_repo = _VideoRepoStub()
    service = VideosService(db=object())
    service.video_repo = video_repo  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    _install_temporal_modules(monkeypatch, client=_FakeClient())
    result = asyncio.run(
        service.process_video(
            platform="youtube",
            url=" https://www.youtube.com/watch?v=from-url ",
            video_id=" manual-video-id ",
            mode="text-only",
            overrides={"lang": "en", "limit": 5},
            force=False,
        )
    )

    assert result["video_uid"] == "manual-video-id"
    assert result["mode"] == "text_only"
    assert len(video_repo.upsert_calls) == 1
    assert video_repo.upsert_calls[0] == {
        "platform": "youtube",
        "video_uid": "manual-video-id",
        "source_url": "https://www.youtube.com/watch?v=from-url",
    }

    assert len(repo.created_calls) == 1
    created = repo.created_calls[0]
    expected_idempotency = _build_process_idempotency_key(
        platform="youtube",
        video_uid="manual-video-id",
        mode="text_only",
        overrides={"lang": "en", "limit": 5},
    )
    assert created["video_id"] == video_repo.video.id
    assert created["kind"] == "video_digest_v1"
    assert created["mode"] == "text_only"
    assert created["overrides_json"] == {"lang": "en", "limit": 5}
    assert created["idempotency_key"] == expected_idempotency
    assert created["force"] is False


def test_process_video_builds_force_idempotency_key_with_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=False)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    _install_temporal_modules(monkeypatch, client=_FakeClient())

    result = asyncio.run(
        service.process_video(
            platform="youtube",
            url="https://youtu.be/force-video",
            video_id=None,
            mode="full",
            overrides={"x": 1},
            force=True,
        )
    )

    expected_base_key = _build_process_idempotency_key(
        platform="youtube",
        video_uid="force-video",
        mode="full",
        overrides={"x": 1},
    )
    created = repo.created_calls[0]
    assert created["idempotency_key"].startswith(f"{expected_base_key}:force:")
    assert re.fullmatch(
        rf"{re.escape(expected_base_key)}:force:[0-9a-f]{{32}}",
        created["idempotency_key"],
    )
    assert created["force"] is True
    assert result["idempotency_key"] == created["idempotency_key"]


def test_process_video_normalizes_analysis_mode_aliases_into_llm_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=False)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    _install_temporal_modules(monkeypatch, client=_FakeClient())

    result = asyncio.run(
        service.process_video(
            platform="youtube",
            url="https://youtu.be/advanced-video",
            video_id=None,
            mode="full",
            overrides={"analysis_mode": "ECONOMY", "raw_stage": {"mode": "advanced"}},
            force=False,
        )
    )

    assert result["overrides"] == {
        "llm": {"analysis_mode": "advanced"},
        "raw_stage": {"mode": "advanced"},
    }
    assert repo.created_calls[0]["overrides_json"] == result["overrides"]


def test_build_process_idempotency_key_is_stable_with_unicode_and_key_order() -> None:
    overrides = {"b": "中文", "a": 1}
    expected_overrides_json = json.dumps({"a": 1, "b": "中文"}, ensure_ascii=False, sort_keys=True)
    expected_key = hashlib.sha256(
        f"youtube:vid-1:full:{expected_overrides_json}".encode()
    ).hexdigest()

    key_a = _build_process_idempotency_key(
        platform="youtube",
        video_uid="vid-1",
        mode="full",
        overrides=overrides,
    )
    key_b = _build_process_idempotency_key(
        platform="youtube",
        video_uid="vid-1",
        mode="full",
        overrides={"a": 1, "b": "中文"},
    )

    assert key_a == expected_key
    assert key_b == expected_key


def test_build_process_idempotency_key_rejects_non_json_serializable_overrides() -> None:
    with pytest.raises(ValueError, match=r"^overrides must be JSON-serializable$"):
        _build_process_idempotency_key(
            platform="youtube",
            video_uid="vid-1",
            mode="full",
            overrides={"set": {1, 2}},
        )


def test_process_video_falls_back_to_normalized_mode_when_repo_job_mode_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _BlankModeRepo(_RepoStub):
        def create_or_reuse(self, **kwargs: Any) -> tuple[_JobRow, bool]:
            job, should_dispatch = super().create_or_reuse(**kwargs)
            job.mode = ""
            return job, should_dispatch

    repo = _BlankModeRepo(should_dispatch=False)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]
    _install_temporal_modules(monkeypatch, client=_FakeClient())

    result = asyncio.run(
        service.process_video(
            platform="youtube",
            url="https://www.youtube.com/watch?v=abc123",
            video_id=None,
            mode="refresh-comments",
            overrides={},
            force=False,
        )
    )

    assert result["mode"] == "refresh_comments"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123", "https://www.youtube.com/watch?v=abc123"),
        ("http://m.youtube.com/watch?v=abc123", "http://m.youtube.com/watch?v=abc123"),
        ("https://youtu.be/abc123", "https://youtu.be/abc123"),
        ("https://music.youtube.com/watch?v=abc123", "https://music.youtube.com/watch?v=abc123"),
        (
            "https://www.bilibili.com/video/BV1xx411c7mD",
            "https://www.bilibili.com/video/BV1xx411c7mD",
        ),
        ("https://m.bilibili.com/video/BV1xx411c7mD", "https://m.bilibili.com/video/BV1xx411c7mD"),
        ("https://b23.tv/abc123", "https://b23.tv/abc123"),
        (" https://www.youtube.com/watch?v=trimmed ", "https://www.youtube.com/watch?v=trimmed"),
    ],
)
def test_validate_video_source_url_accepts_whitelisted_hosts(url: str, expected: str) -> None:
    assert _validate_video_source_url(url) == expected


@pytest.mark.parametrize(
    ("url", "error_code"),
    [
        ("", "video_url_empty"),
        ("ftp://www.youtube.com/watch?v=abc123", "video_url_invalid_scheme"),
        ("https:///watch?v=abc123", "video_url_host_required"),
        ("https://localhost/watch?v=abc123", "video_url_blocked_internal_host"),
        ("https://api.internal/watch?v=abc123", "video_url_blocked_internal_host"),
        ("https://127.0.0.1/watch?v=abc123", "video_url_ip_literal_blocked"),
        ("https://[::1]/watch?v=abc123", "video_url_ip_literal_blocked"),
        ("https://10.0.0.8/watch?v=abc123", "video_url_ip_literal_blocked"),
        ("https://example.com/watch?v=abc123", "video_url_domain_not_allowed"),
        ("https://youtube.com.evil.com/watch?v=abc123", "video_url_domain_not_allowed"),
    ],
)
def test_validate_video_source_url_rejects_disallowed_hosts(url: str, error_code: str) -> None:
    with pytest.raises(ValueError, match=rf"^{re.escape(error_code)}$"):
        _validate_video_source_url(url)
