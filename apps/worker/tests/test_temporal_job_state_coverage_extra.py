from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from worker.config import Settings
from worker.temporal import activities_job_state


def _patch_settings(monkeypatch, *, tmp_path: Path) -> None:
    settings = Settings(
        sqlite_path=str((tmp_path / "state.db").resolve()),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor",
    )
    monkeypatch.setattr(
        activities_job_state.Settings,
        "from_env",
        classmethod(lambda cls: settings),
    )


def test_helper_normalization_branches() -> None:
    assert (
        activities_job_state._to_pipeline_final_status(" succeeded ", fallback=None) == "succeeded"
    )
    assert activities_job_state._to_pipeline_final_status("bad", fallback="DEGRADED") == "degraded"
    assert activities_job_state._to_pipeline_final_status("bad", fallback="invalid") is None

    assert activities_job_state._coerce_non_negative_int(True) is None
    assert activities_job_state._coerce_non_negative_int(-1) == 0
    assert activities_job_state._coerce_non_negative_int(" 12 ") == 12
    assert activities_job_state._coerce_non_negative_int("x12") is None

    assert activities_job_state._resolve_degradation_count({"degradation_count": "3"}) == 3
    assert activities_job_state._resolve_degradation_count({"degradations": [{}, {}]}) == 2
    assert activities_job_state._resolve_degradation_count({}) == 0

    assert (
        activities_job_state._resolve_last_error_code(
            {
                "degradations": [
                    "skip-non-dict",
                    {"reason": "  timeout:error-detail  "},
                ]
            }
        )
        == "timeout:error-detail"
    )
    assert (
        activities_job_state._resolve_last_error_code({"fatal_error": "provider: 429"})
        == "provider"
    )
    assert activities_job_state._resolve_last_error_code({"error": "plain_error"}) == "plain_error"


def test_mark_running_activity_success_path(monkeypatch, tmp_path: Path) -> None:
    _patch_settings(monkeypatch, tmp_path=tmp_path)
    observed: dict[str, Any] = {}

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            return None

        def next_attempt(self, **_: Any) -> int:
            return 3

        def mark_step_running(self, **kwargs: Any) -> None:
            observed["running"] = kwargs

        def mark_step_finished(self, **kwargs: Any) -> None:
            observed["finished"] = kwargs

        def update_checkpoint(self, **kwargs: Any) -> None:
            observed["checkpoint"] = kwargs

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def mark_job_running(self, *, job_id: str) -> dict[str, Any]:
            return {"id": job_id, "status": "running", "transitioned": True}

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)

    result = asyncio.run(activities_job_state.mark_running_activity("job-1"))
    assert result == {"job_id": "job-1", "attempt": 3, "status": "running"}
    assert observed["finished"]["status"] == "succeeded"
    assert observed["checkpoint"]["last_completed_step"] == "mark_running"


def test_reconcile_stale_queued_jobs_activity_defaults_and_floor(
    monkeypatch, tmp_path: Path
) -> None:
    _patch_settings(monkeypatch, tmp_path=tmp_path)
    observed: dict[str, Any] = {}

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def fail_stale_queued_jobs(
            self, *, timeout_seconds: int, limit: int
        ) -> list[dict[str, Any]]:
            observed["timeout_seconds"] = timeout_seconds
            observed["limit"] = limit
            return [{"id": "job-a"}, {"id": "job-b"}]

    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)

    result = asyncio.run(
        activities_job_state.reconcile_stale_queued_jobs_activity(
            {"timeout_minutes": "0", "limit": "0"}
        )
    )

    assert observed == {"timeout_seconds": 60, "limit": 200}
    assert result["recovered"] == 2
    assert result["job_ids"] == ["job-a", "job-b"]


def test_run_pipeline_activity_uses_record_defaults_and_sanitizes_content_type(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path=tmp_path)
    observed: dict[str, Any] = {}

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            return None

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def get_job_with_video(self, *, job_id: str) -> dict[str, Any]:
            assert job_id == "job-1"
            return {
                "mode": " text_only ",
                "overrides_json": {"from_db": True},
                "content_type": "unknown",
            }

    async def _fake_run_pipeline(
        _settings: Settings,
        _sqlite_store: Any,
        _pg_store: Any,
        *,
        job_id: str,
        attempt: int,
        mode: str,
        overrides: dict[str, Any] | None,
        content_type: str,
    ) -> dict[str, Any]:
        observed["job_id"] = job_id
        observed["attempt"] = attempt
        observed["mode"] = mode
        observed["overrides"] = overrides
        observed["content_type"] = content_type
        return {"ok": True}

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)
    fake_runner_module = types.SimpleNamespace(run_pipeline=_fake_run_pipeline)
    monkeypatch.setitem(sys.modules, "worker.pipeline.runner", fake_runner_module)

    result = asyncio.run(
        activities_job_state.run_pipeline_activity(
            {
                "job_id": "job-1",
                "attempt": "4",
            }
        )
    )

    assert result == {"ok": True}
    assert observed == {
        "job_id": "job-1",
        "attempt": 4,
        "mode": "text_only",
        "overrides": {"from_db": True},
        "content_type": "video",
    }


def test_mark_succeeded_activity_default_field_coercion(monkeypatch, tmp_path: Path) -> None:
    _patch_settings(monkeypatch, tmp_path=tmp_path)
    observed: dict[str, Any] = {}

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            return None

        def mark_step_running(self, **_: Any) -> None:
            return None

        def mark_step_finished(self, **kwargs: Any) -> None:
            observed["finished"] = kwargs

        def update_checkpoint(self, **_: Any) -> None:
            return None

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def mark_job_succeeded(self, **kwargs: Any) -> dict[str, Any]:
            observed["stored"] = kwargs
            return {
                "status": "succeeded",
                "pipeline_final_status": kwargs.get("pipeline_final_status"),
                "degradation_count": kwargs.get("degradation_count"),
                "last_error_code": kwargs.get("last_error_code"),
                "llm_required": kwargs.get("llm_required"),
                "llm_gate_passed": kwargs.get("llm_gate_passed"),
                "hard_fail_reason": kwargs.get("hard_fail_reason"),
            }

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)

    result = asyncio.run(
        activities_job_state.mark_succeeded_activity(
            {
                "job_id": "job-s",
                "attempt": 2,
                "final_status": "DEGRADED",
                "pipeline_final_status": "invalid",
                "degradations": [{"error_code": "provider_timeout:retry"}],
                "llm_required": "yes",
                "llm_gate_passed": 1,
                "hard_fail_reason": "   ",
            }
        )
    )

    stored = observed["stored"]
    assert stored["pipeline_final_status"] == "degraded"
    assert stored["degradation_count"] == 1
    assert stored["last_error_code"] == "provider_timeout:retry"
    assert stored["llm_required"] is None
    assert stored["llm_gate_passed"] is None
    assert stored["hard_fail_reason"] is None
    assert observed["finished"]["status"] == "succeeded"
    assert result["status"] == "DEGRADED"


def test_mark_failed_activity_default_derivation_and_conflict_branch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _patch_settings(monkeypatch, tmp_path=tmp_path)
    observed: dict[str, Any] = {}
    conflict_mode = {"enabled": False}

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            return None

        def mark_step_running(self, **_: Any) -> None:
            return None

        def mark_step_finished(self, **kwargs: Any) -> None:
            observed["finished"] = kwargs

        def update_checkpoint(self, **_: Any) -> None:
            observed["checkpoint"] = True

    class _FakePGStore:
        def __init__(self, _database_url: str):
            return None

        def mark_job_failed(self, **kwargs: Any) -> dict[str, Any]:
            observed["stored"] = kwargs
            if conflict_mode["enabled"]:
                return {"status": "succeeded", "transitioned": False}
            return {
                "status": "failed",
                "last_error_code": kwargs.get("last_error_code"),
                "llm_required": kwargs.get("llm_required"),
                "llm_gate_passed": kwargs.get("llm_gate_passed"),
                "hard_fail_reason": kwargs.get("hard_fail_reason"),
                "transitioned": True,
            }

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)

    success = asyncio.run(
        activities_job_state.mark_failed_activity(
            {
                "job_id": "job-f",
                "attempt": 5,
                "error": "provider_timeout:429",
                "llm_required": "invalid",
                "llm_gate_passed": "invalid",
                "hard_fail_reason": "",
            }
        )
    )
    assert observed["stored"]["llm_required"] is True
    assert observed["stored"]["llm_gate_passed"] is False
    assert observed["stored"]["hard_fail_reason"] == "provider_timeout"
    assert success["status"] == "failed"

    conflict_mode["enabled"] = True
    with pytest.raises(
        ValueError, match="terminal update blocked, reason=invalid_status:succeeded"
    ):
        asyncio.run(
            activities_job_state.mark_failed_activity(
                {
                    "job_id": "job-conflict",
                    "attempt": 6,
                    "error": "boom",
                }
            )
        )
    assert observed["finished"]["error_payload"]["reason"] == "invalid_status:succeeded"
