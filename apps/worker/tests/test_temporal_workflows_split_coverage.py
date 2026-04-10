from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from worker.temporal import workflows


def test_poll_feeds_workflow_stays_track_only(monkeypatch: Any) -> None:
    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        assert activity_fn is workflows.poll_feeds_activity
        assert payload == {"platform": "youtube"}
        return {"ok": True, "created_job_ids": ["job-1", "job-2"]}

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(workflows.PollFeedsWorkflow().run({"platform": "youtube"}))

    assert result["dispatched_process_workflows"] == 0
    assert result["process_results"] == []
    assert result["track_interval_minutes"] == 15


def test_poll_feeds_workflow_continuous_mode_uses_interval(monkeypatch: Any) -> None:
    calls = {"activity": 0}
    sleeps: list[timedelta] = []

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        assert activity_fn is workflows.poll_feeds_activity
        assert payload == {"platform": "youtube"}
        calls["activity"] += 1
        return {"ok": True, "created_job_ids": []}

    async def _fake_sleep(duration: timedelta) -> None:
        sleeps.append(duration)
        raise StopAsyncIteration

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(
            workflows.PollFeedsWorkflow().run(
                {"platform": "youtube", "run_once": False, "interval_minutes": 15}
            )
        )

    assert calls["activity"] == 1
    assert int(sleeps[0].total_seconds()) == 15 * 60


def test_consume_batch_workflow_materializes_and_closes(monkeypatch: Any) -> None:
    reader_materialization_payloads: list[dict[str, Any]] = []
    materialized_payloads: list[dict[str, Any]] = []
    closed_payloads: list[dict[str, Any]] = []

    async def _fake_execute_activity(activity_fn: Any, payload: Any, **_: Any) -> dict[str, Any]:
        if activity_fn is workflows.load_consumption_batch_activity:
            return {
                "id": "batch-1",
                "window_id": "2026-04-09@America/Los_Angeles",
                "cutoff_at": "2026-04-09T10:00:00Z",
                "source_item_count": 2,
                "items": [
                    {"job_id": "job-1"},
                    {"job_id": "job-2"},
                ],
            }
        if activity_fn is workflows.mark_consumption_batch_materialized_activity:
            materialized_payloads.append(dict(payload))
            return {"status": "materialized"}
        if activity_fn is workflows.mark_consumption_batch_closed_activity:
            closed_payloads.append(dict(payload))
            return {"status": "closed"}
        if activity_fn is workflows.materialize_reader_batch_activity:
            reader_materialization_payloads.append(dict(payload))
            return {
                "consumption_batch_id": "batch-1",
                "cluster_verdict_manifest_id": "manifest-1",
                "window_id": "2026-04-09@America/Los_Angeles",
                "published_document_count": 2,
                "published_with_gap_count": 1,
                "documents": [
                    {"id": "doc-1"},
                    {"id": "doc-2"},
                ],
                "navigation_brief": {"document_count": 2},
            }
        raise AssertionError(f"unexpected activity {activity_fn}")

    async def _fake_execute_child_workflow(
        _workflow_run: Any,
        job_id: str,
        *,
        id: str,
        task_queue: str,
    ) -> dict[str, Any]:
        assert id.startswith("consume-batch-batch-1-process-job-")
        assert task_queue == "queue-main"
        return {"ok": job_id == "job-1", "job_id": job_id}

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "execute_child_workflow", _fake_execute_child_workflow)
    monkeypatch.setattr(
        workflows.workflow,
        "info",
        lambda: SimpleNamespace(run_id="run-123", task_queue="queue-main"),
    )

    result = asyncio.run(workflows.ConsumeBatchWorkflow().run({"consumption_batch_id": "batch-1"}))

    assert result["status"] == "closed"
    assert result["processed_job_count"] == 2
    assert result["succeeded_job_count"] == 1
    assert result["failed_job_count"] == 1
    assert result["downstream_status"] == "published_reader_documents_materialized"
    assert result["published_document_count"] == 2
    assert result["published_with_gap_count"] == 1
    assert result["materialization"]["cluster_verdict_manifest_id"] == "manifest-1"
    assert reader_materialization_payloads[0]["consumption_batch_id"] == "batch-1"
    assert materialized_payloads[0]["processed_job_count"] == 2
    assert materialized_payloads[0]["process_summary_json"]["published_document_ids"] == [
        "doc-1",
        "doc-2",
    ]
    assert closed_payloads[0]["consumption_batch_id"] == "batch-1"


@pytest.mark.parametrize("job_input", [{"job_id": ""}, "   "])
def test_process_job_workflow_requires_non_empty_job_id(job_input: Any) -> None:
    with pytest.raises(ValueError, match="requires job_id"):
        asyncio.run(workflows.ProcessJobWorkflow().run(job_input))


def test_process_job_workflow_handles_notification_exception(monkeypatch: Any) -> None:
    async def _fake_execute_activity(activity_fn: Any, payload: Any, **_: Any) -> dict[str, Any]:
        if activity_fn is workflows.mark_running_activity:
            return {"attempt": 1}
        if activity_fn is workflows.run_pipeline_activity:
            return {"final_status": "succeeded", "artifacts": {}}
        if activity_fn is workflows.mark_succeeded_activity:
            return {"status": "succeeded", "db_status": "succeeded"}
        if activity_fn is workflows.send_video_digest_activity:
            raise RuntimeError("notification_down")
        raise AssertionError(f"unexpected activity {activity_fn}")

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(workflows.ProcessJobWorkflow().run("job-1"))

    assert result["ok"] is True
    assert result["video_digest"]["ok"] is False
    assert result["video_digest"]["status"] == "failed"
    assert result["video_digest"]["error"] == "notification_down"


def test_process_job_workflow_handles_pipeline_exception(monkeypatch: Any) -> None:
    async def _fake_execute_activity(activity_fn: Any, payload: Any, **_: Any) -> dict[str, Any]:
        if activity_fn is workflows.mark_running_activity:
            return {"attempt": 3}
        if activity_fn is workflows.run_pipeline_activity:
            raise RuntimeError("pipeline_crashed")
        if activity_fn is workflows.mark_failed_activity:
            assert payload["hard_fail_reason"] == "workflow_exception"
            return {"status": "failed"}
        raise AssertionError(f"unexpected activity {activity_fn}")

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(workflows.ProcessJobWorkflow().run("job-2"))

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["error"] == "pipeline_crashed"


def test_process_job_workflow_dict_input_failed_pipeline_branch(monkeypatch: Any) -> None:
    captured_pipeline_payload: dict[str, Any] = {}

    async def _fake_execute_activity(activity_fn: Any, payload: Any, **_: Any) -> dict[str, Any]:
        if activity_fn is workflows.mark_running_activity:
            return {"attempt": "2"}
        if activity_fn is workflows.run_pipeline_activity:
            captured_pipeline_payload.update(dict(payload))
            return {
                "final_status": "failed",
                "fatal_error": "llm_gate_blocked",
                "degradations": ["subtitles_missing"],
                "llm_required": True,
                "llm_gate_passed": False,
                "hard_fail_reason": "llm_gate",
            }
        if activity_fn is workflows.mark_failed_activity:
            assert payload["mode"] == "safe"
            assert payload["overrides"] == {"force_summary": True}
            assert payload["error"] == "llm_gate_blocked"
            assert payload["pipeline_final_status"] == "failed"
            return {"status": "failed"}
        raise AssertionError(f"unexpected activity {activity_fn}")

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(
        workflows.ProcessJobWorkflow().run(
            {
                "job_id": "job-3",
                "mode": " safe ",
                "overrides": {"force_summary": True},
            }
        )
    )

    assert captured_pipeline_payload["job_id"] == "job-3"
    assert captured_pipeline_payload["attempt"] == 2
    assert captured_pipeline_payload["mode"] == "safe"
    assert captured_pipeline_payload["overrides"] == {"force_summary": True}
    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["error"] == "llm_gate_blocked"


def test_consume_pending_workflow_prepares_and_dispatches_batch(monkeypatch: Any) -> None:
    sleep_calls: list[timedelta] = []

    async def _fake_execute_activity(activity_fn: Any, payload: Any, **_: Any) -> dict[str, Any]:
        if activity_fn is workflows.prepare_consumption_batch_activity:
            assert payload["trigger_mode"] == "auto"
            return {
                "ok": True,
                "status": "frozen",
                "consumption_batch_id": "batch-2",
                "window_id": "2026-04-09@America/Los_Angeles",
                "cutoff_at": "2026-04-09T18:00:00Z",
            }
        raise AssertionError(f"unexpected activity {activity_fn}")

    async def _fake_execute_child_workflow(
        workflow_run: Any,
        payload: dict[str, Any],
        *,
        id: str,
        task_queue: str,
    ) -> dict[str, Any]:
        assert workflow_run is workflows.ConsumeBatchWorkflow.run
        assert payload == {"consumption_batch_id": "batch-2"}
        assert id.startswith("consume-pending-batch-2-")
        assert task_queue == "queue-main"
        return {"ok": True, "status": "closed", "processed_job_count": 1}

    async def _fake_sleep(duration: timedelta) -> None:
        sleep_calls.append(duration)
        raise StopAsyncIteration

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "execute_child_workflow", _fake_execute_child_workflow)
    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)
    monkeypatch.setattr(
        workflows.workflow,
        "info",
        lambda: SimpleNamespace(run_id="run-789", task_queue="queue-main"),
    )

    result = asyncio.run(
        workflows.ConsumePendingWorkflow().run(
            {"run_once": True, "trigger_mode": "auto", "interval_minutes": 120}
        )
    )

    assert result["consumption_batch_id"] == "batch-2"
    assert result["status"] == "closed"
    assert result["auto_cooldown_minutes"] == 120
    assert sleep_calls == []


def test_daily_digest_workflow_run_once_returns_result(monkeypatch: Any) -> None:
    calls = {"timing": 0, "send": 0}

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        if activity_fn is workflows.resolve_daily_digest_timing_activity:
            calls["timing"] += 1
            return {
                "digest_date": "2026-03-08",
                "wait_before_run_seconds": 0,
                "wait_after_run_seconds": 120,
                "timezone_name": "UTC",
                "timezone_offset_minutes": 0,
            }
        assert activity_fn is workflows.send_daily_digest_activity
        calls["send"] += 1
        return {"ok": True, "status": "sent"}

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(workflows.DailyDigestWorkflow().run({"run_once": True}))

    assert result["ok"] is True
    assert result["runs"] == 1
    assert calls == {"timing": 1, "send": 1}


def test_daily_digest_workflow_floors_non_positive_wait_after(monkeypatch: Any) -> None:
    sleeps: list[timedelta] = []

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        if activity_fn is workflows.resolve_daily_digest_timing_activity:
            return {
                "digest_date": "2026-03-08",
                "wait_before_run_seconds": 0,
                "wait_after_run_seconds": 0,
                "timezone_name": "UTC",
                "timezone_offset_minutes": 0,
            }
        return {"ok": True}

    async def _fake_sleep(duration: timedelta) -> None:
        sleeps.append(duration)
        raise StopAsyncIteration

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(workflows.DailyDigestWorkflow().run({"run_once": False}))

    assert int(sleeps[0].total_seconds()) == 60


def test_notification_retry_workflow_non_run_once_sleeps(monkeypatch: Any) -> None:
    sleeps: list[timedelta] = []

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        if activity_fn is workflows.reconcile_stale_queued_jobs_activity:
            return {"ok": True, "recovered": 1}
        assert activity_fn is workflows.retry_failed_deliveries_activity
        return {"ok": True, "checked": 2, "retried": 1}

    async def _fake_sleep(duration: timedelta) -> None:
        sleeps.append(duration)
        raise StopAsyncIteration

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)
    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(
            workflows.NotificationRetryWorkflow().run(
                {"run_once": False, "interval_minutes": 7, "retry_batch_limit": 5}
            )
        )

    assert int(sleeps[0].total_seconds()) == 7 * 60


def test_notification_retry_workflow_run_once_returns_latest(monkeypatch: Any) -> None:
    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        if activity_fn is workflows.reconcile_stale_queued_jobs_activity:
            assert payload["timeout_minutes"] == 15
            assert payload["limit"] == 200
            return {"ok": True, "recovered": 3}
        assert activity_fn is workflows.retry_failed_deliveries_activity
        assert payload["limit"] == 50
        return {"ok": True, "checked": 4, "retried": 2, "sent": 1}

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(workflows.NotificationRetryWorkflow().run({"run_once": True}))

    assert result["ok"] is True
    assert result["runs"] == 1
    assert result["stale_queued_recovery"]["recovered"] == 3
    assert result["checked"] == 4


def test_provider_canary_workflow_run_once_and_loop(monkeypatch: Any) -> None:
    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        assert activity_fn is workflows.provider_canary_activity
        assert payload["timeout_seconds"] >= 3
        return {"ok": True, "provider": "resend"}

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    run_once = asyncio.run(
        workflows.ProviderCanaryWorkflow().run(
            {"run_once": True, "interval_hours": 0, "timeout_seconds": 1}
        )
    )
    assert run_once["ok"] is True
    assert run_once["runs"] == 1

    sleeps: list[timedelta] = []

    async def _fake_sleep(duration: timedelta) -> None:
        sleeps.append(duration)
        raise StopAsyncIteration

    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(
            workflows.ProviderCanaryWorkflow().run({"run_once": False, "interval_hours": 0})
        )

    assert int(sleeps[0].total_seconds()) == 3600


def test_cleanup_workspace_workflow_filters_payload_and_loops(monkeypatch: Any) -> None:
    activity_payloads: list[dict[str, Any]] = []

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        assert activity_fn is workflows.cleanup_workspace_activity
        activity_payloads.append(dict(payload))
        return {"ok": True, "deleted_files": 2}

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    run_once = asyncio.run(
        workflows.CleanupWorkspaceWorkflow().run(
            {
                "run_once": True,
                "interval_hours": 0,
                "workspace_dir": "/tmp/workspace",
                "older_than_hours": 24,
                "cache_max_size_mb": 128,
                "unexpected": "ignored",
            }
        )
    )
    assert run_once["ok"] is True
    assert run_once["runs"] == 1
    assert "unexpected" not in activity_payloads[0]

    sleeps: list[timedelta] = []

    async def _fake_sleep(duration: timedelta) -> None:
        sleeps.append(duration)
        raise StopAsyncIteration

    monkeypatch.setattr(workflows.workflow, "sleep", _fake_sleep)

    with pytest.raises(StopAsyncIteration):
        asyncio.run(
            workflows.CleanupWorkspaceWorkflow().run({"run_once": False, "interval_hours": 0})
        )

    assert int(sleeps[0].total_seconds()) == 3600
