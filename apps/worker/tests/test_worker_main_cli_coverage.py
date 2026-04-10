from __future__ import annotations

import argparse
import asyncio
import json
import sys
import types
from datetime import timedelta
from types import SimpleNamespace

import pytest
from worker import main as worker_main


def _fake_settings() -> SimpleNamespace:
    return SimpleNamespace(
        temporal_target_host="127.0.0.1:7233",
        temporal_namespace="default",
        temporal_task_queue="sourceharbor-worker",
        digest_daily_local_hour=9,
        digest_local_timezone="UTC",
    )


def test_build_parser_supports_all_subcommands() -> None:
    parser = worker_main._build_parser()
    commands = [
        ["run-worker"],
        ["start-poll-workflow", "--platform", "youtube", "--max-new-videos", "12"],
        ["start-process-workflow", "--job-id", "job-1"],
        ["start-daily-workflow", "--run-once", "--local-hour", "8"],
        ["start-notification-retry-workflow", "--interval-minutes", "5"],
        ["start-provider-canary-workflow", "--timeout-seconds", "12"],
        ["start-cleanup-workflow", "--older-than-hours", "6", "--cache-max-size-mb", "256"],
    ]
    for argv in commands:
        ns = parser.parse_args(argv)
        assert ns.command == argv[0]


@pytest.mark.parametrize(
    ("command", "patch_name", "result"),
    [
        ("start-poll-workflow", "start_poll_workflow", {"ok": True, "kind": "poll"}),
        ("start-process-workflow", "start_process_workflow", {"ok": True, "kind": "process"}),
        ("start-daily-workflow", "start_daily_workflow", {"ok": True, "kind": "daily"}),
        (
            "start-notification-retry-workflow",
            "start_notification_retry_workflow",
            {"ok": True, "kind": "retry"},
        ),
        (
            "start-provider-canary-workflow",
            "start_provider_canary_workflow",
            {"ok": True, "kind": "canary"},
        ),
        ("start-cleanup-workflow", "start_cleanup_workflow", {"ok": True, "kind": "cleanup"}),
    ],
)
def test_main_async_dispatches_commands(monkeypatch, capsys, command, patch_name, result) -> None:
    monkeypatch.setattr(worker_main.Settings, "from_env", staticmethod(_fake_settings))

    async def _stub(*_args, **_kwargs):
        return result

    monkeypatch.setattr(worker_main, patch_name, _stub)
    args = argparse.Namespace(
        command=command,
        subscription_id=None,
        platform=None,
        max_new_videos=50,
        continuous=False,
        job_id="job-1",
        run_once=True,
        local_hour=8,
        timezone_name="UTC",
        timezone_offset_minutes=0,
        workflow_id=f"{command}-id",
        interval_minutes=5,
        retry_batch_limit=10,
        interval_hours=1,
        timeout_seconds=8,
        older_than_hours=24,
        workspace_dir=None,
        cache_dir=None,
        cache_older_than_hours=None,
        cache_max_size_mb=None,
    )

    asyncio.run(worker_main._main_async(args))
    printed = capsys.readouterr().out.strip()
    assert json.loads(printed) == result


def test_main_async_run_worker_branch(monkeypatch) -> None:
    monkeypatch.setattr(worker_main.Settings, "from_env", staticmethod(_fake_settings))
    called = {"value": False}

    async def _run_worker(_settings):
        called["value"] = True

    monkeypatch.setattr(worker_main, "run_temporal_worker", _run_worker)
    args = argparse.Namespace(command="run-worker")
    asyncio.run(worker_main._main_async(args))
    assert called["value"] is True


def test_main_async_emits_success_log_with_output_correlation(monkeypatch, capsys) -> None:
    monkeypatch.setattr(worker_main.Settings, "from_env", staticmethod(_fake_settings))
    events: list[dict[str, object]] = []

    async def _stub(*_args, **_kwargs):
        return {"ok": True, "run_id": "run-123", "kind": "poll"}

    monkeypatch.setattr(worker_main, "start_poll_workflow", _stub)
    monkeypatch.setattr(
        worker_main, "_emit_worker_command_log", lambda **kwargs: events.append(kwargs)
    )
    args = argparse.Namespace(
        command="start-poll-workflow",
        subscription_id=None,
        platform="youtube",
        max_new_videos=10,
        continuous=False,
        job_id=None,
        run_once=False,
        local_hour=None,
        timezone_name=None,
        timezone_offset_minutes=None,
        workflow_id="poll-id",
        interval_minutes=5,
        retry_batch_limit=10,
        interval_hours=1,
        timeout_seconds=8,
        older_than_hours=24,
        workspace_dir=None,
        cache_dir=None,
        cache_older_than_hours=None,
        cache_max_size_mb=None,
    )

    asyncio.run(worker_main._main_async(args))

    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["run_id"] == "run-123"
    assert [event["event"] for event in events] == [
        "worker_command_started",
        "worker_command_completed",
    ]
    assert events[0]["run_id"] == events[0]["request_id"]
    assert events[1]["run_id"] == "run-123"
    assert events[1]["trace_id"] == "run-123"
    assert events[1]["request_id"]


def test_main_async_emits_failure_log_with_argument_correlation(monkeypatch) -> None:
    monkeypatch.setattr(worker_main.Settings, "from_env", staticmethod(_fake_settings))
    events: list[dict[str, object]] = []

    async def _stub(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_main, "start_process_workflow", _stub)
    monkeypatch.setattr(
        worker_main, "_emit_worker_command_log", lambda **kwargs: events.append(kwargs)
    )
    args = argparse.Namespace(
        command="start-process-workflow",
        subscription_id=None,
        platform=None,
        max_new_videos=50,
        continuous=False,
        job_id="job-123",
        run_once=False,
        local_hour=None,
        timezone_name=None,
        timezone_offset_minutes=None,
        workflow_id="process-id",
        interval_minutes=5,
        retry_batch_limit=10,
        interval_hours=1,
        timeout_seconds=8,
        older_than_hours=24,
        workspace_dir=None,
        cache_dir=None,
        cache_older_than_hours=None,
        cache_max_size_mb=None,
    )

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(worker_main._main_async(args))

    assert [event["event"] for event in events] == [
        "worker_command_started",
        "worker_command_failed",
    ]
    assert events[1]["run_id"] == "job-123"
    assert events[1]["trace_id"] == "job-123"
    assert events[1]["request_id"]


def test_main_async_run_worker_emits_loop_lifecycle_logs(monkeypatch) -> None:
    monkeypatch.setattr(worker_main.Settings, "from_env", staticmethod(_fake_settings))
    events: list[dict[str, object]] = []

    async def _run_worker(_settings):
        return None

    monkeypatch.setattr(worker_main, "run_temporal_worker", _run_worker)
    monkeypatch.setattr(
        worker_main, "_emit_worker_command_log", lambda **kwargs: events.append(kwargs)
    )

    asyncio.run(worker_main._main_async(argparse.Namespace(command="run-worker")))

    assert [event["event"] for event in events] == [
        "worker_command_started",
        "worker_loop_started",
        "worker_loop_exited",
    ]
    assert all(event["run_id"] == events[0]["request_id"] for event in events)


def test_main_async_unsupported_command_raises(monkeypatch) -> None:
    monkeypatch.setattr(worker_main.Settings, "from_env", staticmethod(_fake_settings))
    with pytest.raises(ValueError, match="Unsupported command"):
        asyncio.run(worker_main._main_async(argparse.Namespace(command="unknown")))


def test_run_temporal_worker_registers_workflows_and_activities(monkeypatch) -> None:
    workflows_mod = types.ModuleType("worker.temporal.workflows")
    activities_mod = types.ModuleType("worker.temporal.activities")
    worker_mod = types.ModuleType("temporalio.worker")

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Worker:
        def __init__(self, client, *, task_queue, workflows, activities):
            self.client = client
            self.task_queue = task_queue
            self.workflows = workflows
            self.activities = activities

        async def run(self):
            return None

    workflows_mod.PollFeedsWorkflow = _Workflow
    workflows_mod.ProcessJobWorkflow = _Workflow
    workflows_mod.ConsumeBatchWorkflow = _Workflow
    workflows_mod.ConsumePendingWorkflow = _Workflow
    workflows_mod.DailyDigestWorkflow = _Workflow
    workflows_mod.CleanupWorkspaceWorkflow = _Workflow
    workflows_mod.NotificationRetryWorkflow = _Workflow
    workflows_mod.ProviderCanaryWorkflow = _Workflow
    for name in [
        "cleanup_workspace_activity",
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
        "send_daily_digest_activity",
        "send_video_digest_activity",
    ]:
        setattr(activities_mod, name, lambda *args, **kwargs: {"ok": True})
    worker_mod.Worker = _Worker

    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.activities", activities_mod)
    monkeypatch.setitem(sys.modules, "temporalio.worker", worker_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=object())
    )

    asyncio.run(worker_main.run_temporal_worker(_fake_settings()))


def test_poll_and_process_workflow_start_paths(monkeypatch) -> None:
    workflows_mod = types.ModuleType("worker.temporal.workflows")
    common_mod = types.ModuleType("temporalio.common")
    captured: list[dict[str, object]] = []

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        async def result(self):
            return {"ok": True}

    class _Client:
        async def start_workflow(self, *args, **kwargs):
            captured.append({"args": args, "kwargs": kwargs})
            return _Handle()

    class _Reuse:
        REJECT_DUPLICATE = "reject"

    class _Conflict:
        USE_EXISTING = "existing"

    workflows_mod.PollFeedsWorkflow = _Workflow
    workflows_mod.ProcessJobWorkflow = _Workflow
    common_mod.WorkflowIDReusePolicy = _Reuse
    common_mod.WorkflowIDConflictPolicy = _Conflict
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setitem(sys.modules, "temporalio.common", common_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    poll = asyncio.run(worker_main.start_poll_workflow(_fake_settings(), platform="youtube"))
    process = asyncio.run(worker_main.start_process_workflow(_fake_settings(), "job-1"))
    assert poll["ok"] is True
    assert process["ok"] is True
    assert captured[0]["kwargs"]["task_queue"] == "sourceharbor-worker"
    assert captured[1]["kwargs"]["id_reuse_policy"] == _Reuse.REJECT_DUPLICATE
    assert captured[1]["kwargs"]["id_conflict_policy"] == _Conflict.USE_EXISTING


def test_retry_and_canary_workflow_already_started_paths(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Client:
        async def start_workflow(self, *_args, **_kwargs):
            raise WorkflowAlreadyStartedError

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.NotificationRetryWorkflow = _Workflow
    workflows_mod.ProviderCanaryWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    retry = asyncio.run(
        worker_main.start_notification_retry_workflow(_fake_settings(), run_once=False)
    )
    canary = asyncio.run(
        worker_main.start_provider_canary_workflow(_fake_settings(), run_once=False)
    )
    assert retry["status"] == "already_running"
    assert canary["status"] == "already_running"


def test_connect_temporal_uses_settings_target_host_and_namespace(monkeypatch) -> None:
    client_mod = types.ModuleType("temporalio.client")
    captured: dict[str, object] = {}

    class _Client:
        @staticmethod
        async def connect(target_host, *, namespace):
            captured["target_host"] = target_host
            captured["namespace"] = namespace
            return {"ok": True}

    client_mod.Client = _Client
    monkeypatch.setitem(sys.modules, "temporalio.client", client_mod)

    result = asyncio.run(worker_main._connect_temporal(_fake_settings()))

    assert result == {"ok": True}
    assert captured == {"target_host": "127.0.0.1:7233", "namespace": "default"}


def test_local_utc_offset_minutes_returns_zero_when_timezone_has_no_offset(monkeypatch) -> None:
    class _FakeAwareDatetime:
        def utcoffset(self):
            return None

    class _FakeNow:
        def astimezone(self):
            return _FakeAwareDatetime()

    class _FakeDatetime:
        @staticmethod
        def now():
            return _FakeNow()

    monkeypatch.setattr(worker_main, "datetime", _FakeDatetime)

    assert worker_main._local_utc_offset_minutes() == 0


def test_local_utc_offset_minutes_returns_positive_minutes(monkeypatch) -> None:
    class _FakeAwareDatetime:
        def utcoffset(self):
            return timedelta(hours=5, minutes=30)

    class _FakeNow:
        def astimezone(self):
            return _FakeAwareDatetime()

    class _FakeDatetime:
        @staticmethod
        def now():
            return _FakeNow()

    monkeypatch.setattr(worker_main, "datetime", _FakeDatetime)

    assert worker_main._local_utc_offset_minutes() == 330


def test_start_daily_workflow_returns_run_once_result(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        async def result(self):
            return {"ok": True, "status": "completed"}

    class _Client:
        async def start_workflow(self, *_args, **_kwargs):
            return _Handle()

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.DailyDigestWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_daily_workflow(
            _fake_settings(),
            run_once=True,
            local_hour=8,
            timezone_name="Asia/Tokyo",
            timezone_offset_minutes=540,
            workflow_id="daily-run-once",
        )
    )

    assert result == {"ok": True, "status": "completed"}


def test_start_notification_retry_workflow_run_once_returns_result(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        async def result(self):
            return {"ok": True, "status": "sent"}

    class _Client:
        async def start_workflow(self, *_args, **_kwargs):
            return _Handle()

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.NotificationRetryWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_notification_retry_workflow(
            _fake_settings(),
            run_once=True,
            interval_minutes=0,
            retry_batch_limit=0,
            workflow_id="retry-run-once",
        )
    )

    assert result == {"ok": True, "status": "sent"}


def test_start_notification_retry_workflow_started_payload_clamps_values(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")
    captured: dict[str, object] = {}

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        id = "retry-workflow"
        run_id = "retry-run-id"
        first_execution_run_id = "retry-first-run-id"

    class _Client:
        async def start_workflow(self, workflow, payload, **kwargs):
            captured["workflow"] = workflow
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            return _Handle()

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.NotificationRetryWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_notification_retry_workflow(
            _fake_settings(),
            run_once=False,
            interval_minutes=0,
            retry_batch_limit=0,
            workflow_id="retry-stable",
        )
    )

    assert captured["payload"] == {
        "run_once": False,
        "interval_minutes": 1,
        "retry_batch_limit": 1,
    }
    assert captured["kwargs"]["id"] == "retry-stable"
    assert result["status"] == "started"
    assert result["interval_minutes"] == 1
    assert result["retry_batch_limit"] == 1
    assert result["run_id"] == "retry-first-run-id"


def test_start_provider_canary_workflow_run_once_returns_result(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        async def result(self):
            return {"ok": True, "status": "healthy"}

    class _Client:
        async def start_workflow(self, *_args, **_kwargs):
            return _Handle()

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.ProviderCanaryWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_provider_canary_workflow(
            _fake_settings(),
            run_once=True,
            interval_hours=0,
            timeout_seconds=1,
            workflow_id="canary-run-once",
        )
    )

    assert result == {"ok": True, "status": "healthy"}


def test_start_provider_canary_workflow_started_payload_clamps_values(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")
    captured: dict[str, object] = {}

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        id = "provider-canary-workflow"
        run_id = "provider-canary-run"

    class _Client:
        async def start_workflow(self, workflow, payload, **kwargs):
            captured["workflow"] = workflow
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            return _Handle()

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.ProviderCanaryWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_provider_canary_workflow(
            _fake_settings(),
            run_once=False,
            interval_hours=0,
            timeout_seconds=2,
            workflow_id="provider-canary-stable",
        )
    )

    assert captured["payload"] == {
        "run_once": False,
        "interval_hours": 1,
        "timeout_seconds": 3,
    }
    assert captured["kwargs"]["id"] == "provider-canary-stable"
    assert result["status"] == "started"
    assert result["interval_hours"] == 1
    assert result["timeout_seconds"] == 3
    assert result["run_id"] == "provider-canary-run"


def test_start_cleanup_workflow_already_running(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Client:
        async def start_workflow(self, *_args, **_kwargs):
            raise WorkflowAlreadyStartedError

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.CleanupWorkspaceWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_cleanup_workflow(
            _fake_settings(),
            run_once=False,
            workflow_id="cleanup-workflow",
        )
    )

    assert result == {
        "ok": True,
        "workflow_id": "cleanup-workflow",
        "status": "already_running",
        "run_once": False,
    }


def test_start_cleanup_workflow_started_payload_includes_cache_controls(monkeypatch) -> None:
    exceptions_mod = types.ModuleType("temporalio.exceptions")
    workflows_mod = types.ModuleType("worker.temporal.workflows")
    captured: dict[str, object] = {}

    class WorkflowAlreadyStartedError(Exception):
        pass

    class _Workflow:
        @staticmethod
        async def run(*_args, **_kwargs):
            return {}

    class _Handle:
        id = "cleanup-workflow"
        first_execution_run_id = "cleanup-run-id"

    class _Client:
        async def start_workflow(self, workflow, payload, **kwargs):
            captured["workflow"] = workflow
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            return _Handle()

    exceptions_mod.WorkflowAlreadyStartedError = WorkflowAlreadyStartedError
    workflows_mod.CleanupWorkspaceWorkflow = _Workflow
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", exceptions_mod)
    monkeypatch.setitem(sys.modules, "worker.temporal.workflows", workflows_mod)
    monkeypatch.setattr(
        worker_main, "_connect_temporal", lambda _settings: asyncio.sleep(0, result=_Client())
    )

    result = asyncio.run(
        worker_main.start_cleanup_workflow(
            _fake_settings(),
            run_once=False,
            interval_hours=0,
            older_than_hours=0,
            workspace_dir="/tmp/workspace",
            cache_dir="/tmp/cache",
            cache_older_than_hours=0,
            cache_max_size_mb=0,
            workflow_id="cleanup-stable",
        )
    )

    assert captured["payload"] == {
        "run_once": False,
        "interval_hours": 1,
        "older_than_hours": 1,
        "workspace_dir": "/tmp/workspace",
        "cache_dir": "/tmp/cache",
        "cache_older_than_hours": 1,
        "cache_max_size_mb": 1,
    }
    assert captured["kwargs"]["id"] == "cleanup-stable"
    assert result["status"] == "started"
    assert result["interval_hours"] == 1
    assert result["older_than_hours"] == 1
    assert result["cache_older_than_hours"] == 1
    assert result["cache_max_size_mb"] == 1
    assert result["run_id"] == "cleanup-run-id"


def test_main_invokes_parser_and_asyncio_run(monkeypatch) -> None:
    captured: dict[str, object] = {}
    parsed_args = argparse.Namespace(command="run-worker")

    def _parse_args():
        captured["args"] = parsed_args
        return parsed_args

    parser = SimpleNamespace(parse_args=_parse_args)

    monkeypatch.setattr(worker_main, "_build_parser", lambda: parser)

    async def _fake_main_async(args):
        captured["args"] = args

    monkeypatch.setattr(worker_main, "_main_async", _fake_main_async)

    def _fake_asyncio_run(coro):
        captured["coro_type"] = type(coro).__name__
        coro.close()

    monkeypatch.setattr(worker_main.asyncio, "run", _fake_asyncio_run)

    worker_main.main()

    assert captured["args"].command == "run-worker"
    assert captured["coro_type"] == "coroutine"
