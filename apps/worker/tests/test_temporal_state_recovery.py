from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from worker.config import Settings
from worker.temporal import activities_job_state, workflows


def test_mark_running_activity_reports_conflict_for_already_running(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        sqlite_path=str((tmp_path / "state.db").resolve()),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor",
    )
    monkeypatch.setattr(
        activities_job_state.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            self.finished_payload: dict[str, Any] | None = None

        def next_attempt(self, **_: Any) -> int:
            return 1

        def mark_step_running(self, **_: Any) -> None:
            return None

        def mark_step_finished(self, **kwargs: Any) -> None:
            self.finished_payload = dict(kwargs)

        def update_checkpoint(self, **_: Any) -> None:
            return None

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def mark_job_running(self, *, job_id: str) -> dict[str, Any]:
            return {
                "id": job_id,
                "status": "running",
                "transitioned": False,
                "conflict": "already_running",
            }

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)

    with pytest.raises(ValueError, match="reason=already_running"):
        asyncio.run(activities_job_state.mark_running_activity("job-1"))


def test_notification_retry_workflow_runs_stale_queue_reconcile(monkeypatch: Any) -> None:
    calls: list[str] = []

    async def _fake_execute_activity(
        activity_fn: Any, payload: dict[str, Any], **_: Any
    ) -> dict[str, Any]:
        if activity_fn is workflows.reconcile_stale_queued_jobs_activity:
            calls.append("reconcile")
            assert payload["timeout_minutes"] == 20
            assert payload["limit"] == 120
            return {"ok": True, "recovered": 2, "job_ids": ["j1", "j2"]}
        if activity_fn is workflows.retry_failed_deliveries_activity:
            calls.append("retry")
            assert payload["limit"] == 15
            return {"ok": True, "checked": 0, "retried": 0}
        raise AssertionError(f"unexpected activity {activity_fn}")

    monkeypatch.setattr(workflows.workflow, "execute_activity", _fake_execute_activity)

    result = asyncio.run(
        workflows.NotificationRetryWorkflow().run(
            {
                "run_once": True,
                "interval_minutes": 10,
                "retry_batch_limit": 15,
                "queued_timeout_minutes": 20,
                "queued_reclaim_limit": 120,
            }
        )
    )

    assert calls == ["reconcile", "retry"]
    assert result["stale_queued_recovery"]["recovered"] == 2
    assert result["runs"] == 1


def test_mark_succeeded_activity_rejects_terminal_overwrite(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        sqlite_path=str((tmp_path / "state.db").resolve()),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor",
    )
    monkeypatch.setattr(
        activities_job_state.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            self.finished_payload: dict[str, Any] | None = None

        def mark_step_running(self, **_: Any) -> None:
            return None

        def mark_step_finished(self, **kwargs: Any) -> None:
            self.finished_payload = dict(kwargs)

        def update_checkpoint(self, **_: Any) -> None:
            return None

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def mark_job_succeeded(self, **_: Any) -> dict[str, Any]:
            return {
                "id": "job-1",
                "status": "failed",
                "transitioned": False,
                "conflict": "terminal_status",
            }

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)

    with pytest.raises(ValueError, match="terminal update blocked, reason=terminal_status"):
        asyncio.run(
            activities_job_state.mark_succeeded_activity(
                {
                    "job_id": "job-1",
                    "attempt": 1,
                    "final_status": "succeeded",
                }
            )
        )
