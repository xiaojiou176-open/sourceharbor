from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.temporal import activities_job_state


def _patch_runtime(
    monkeypatch: Any,
    *,
    tmp_path: Path,
    captured: dict[str, Any],
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
            self.sqlite_path = _sqlite_path

        def mark_step_running(self, **_: Any) -> None:
            return None

        def mark_step_finished(self, **_: Any) -> None:
            return None

        def update_checkpoint(self, **_: Any) -> None:
            return None

    class _FakePGStore:
        def __init__(self, _database_url: str):
            self.database_url = _database_url

        def mark_job_succeeded(self, **kwargs: Any) -> dict[str, Any]:
            captured["mark_job_succeeded"] = dict(kwargs)
            return {
                "status": "succeeded",
                "pipeline_final_status": kwargs.get("pipeline_final_status"),
                "degradation_count": kwargs.get("degradation_count"),
                "last_error_code": kwargs.get("last_error_code"),
                "llm_required": kwargs.get("llm_required"),
                "llm_gate_passed": kwargs.get("llm_gate_passed"),
                "hard_fail_reason": kwargs.get("hard_fail_reason"),
            }

        def mark_job_failed(self, **kwargs: Any) -> dict[str, Any]:
            captured["mark_job_failed"] = dict(kwargs)
            return {
                "status": "failed",
                "last_error_code": kwargs.get("last_error_code"),
                "llm_required": kwargs.get("llm_required"),
                "llm_gate_passed": kwargs.get("llm_gate_passed"),
                "hard_fail_reason": kwargs.get("hard_fail_reason"),
            }

    monkeypatch.setattr(activities_job_state, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_job_state, "PostgresBusinessStore", _FakePGStore)


def test_mark_succeeded_activity_persists_llm_gate_fields(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    _patch_runtime(monkeypatch, tmp_path=tmp_path, captured=captured)

    result = asyncio.run(
        activities_job_state.mark_succeeded_activity(
            {
                "job_id": "job-1",
                "attempt": 2,
                "final_status": "degraded",
                "pipeline_final_status": "degraded",
                "llm_required": True,
                "llm_gate_passed": False,
                "hard_fail_reason": "llm_provider_unavailable",
            }
        )
    )

    stored = captured["mark_job_succeeded"]
    assert stored["llm_required"] is True
    assert stored["llm_gate_passed"] is False
    assert stored["hard_fail_reason"] == "llm_provider_unavailable"
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is False
    assert result["hard_fail_reason"] == "llm_provider_unavailable"


def test_mark_failed_activity_persists_llm_gate_fields(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    _patch_runtime(monkeypatch, tmp_path=tmp_path, captured=captured)

    result = asyncio.run(
        activities_job_state.mark_failed_activity(
            {
                "job_id": "job-2",
                "attempt": 3,
                "error": "llm_provider_unavailable",
                "pipeline_final_status": "failed",
                "llm_required": True,
                "llm_gate_passed": False,
                "hard_fail_reason": "llm_provider_unavailable",
            }
        )
    )

    stored = captured["mark_job_failed"]
    assert stored["llm_required"] is True
    assert stored["llm_gate_passed"] is False
    assert stored["hard_fail_reason"] == "llm_provider_unavailable"
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is False
    assert result["hard_fail_reason"] == "llm_provider_unavailable"
