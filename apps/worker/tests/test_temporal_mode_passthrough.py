from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.temporal import activities, workflows


def _patch_activity_runtime(
    monkeypatch: Any,
    *,
    tmp_path: Path,
    fallback_mode: str,
    fallback_content_type: str = "video",
    captured: dict[str, Any],
    pipeline_result: dict[str, Any] | None = None,
):
    settings = Settings(
        sqlite_path=str((tmp_path / "state.db").resolve()),
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor",
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
    )
    monkeypatch.setattr(activities.Settings, "from_env", classmethod(lambda cls: settings))

    class _FakeSQLiteStore:
        def __init__(self, _sqlite_path: str):
            self.sqlite_path = _sqlite_path

    class _FakePGStore:
        get_job_calls = 0

        def __init__(self, _database_url: str):
            self.database_url = _database_url

        def get_job_with_video(self, *, job_id: str) -> dict[str, Any]:
            type(self).get_job_calls += 1
            return {
                "job_id": job_id,
                "platform": "youtube",
                "video_uid": "video-uid",
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": "Demo",
                "published_at": None,
                "mode": fallback_mode,
                "overrides_json": {"lang": "zh-CN"},
                "content_type": fallback_content_type,
            }

    async def _fake_run_pipeline(
        _settings: Settings,
        _sqlite_store: Any,
        _pg_store: Any,
        *,
        job_id: str,
        attempt: int,
        mode: str = "full",
        overrides: dict[str, Any] | None = None,
        content_type: str = "video",
    ) -> dict[str, Any]:
        captured["job_id"] = job_id
        captured["attempt"] = attempt
        captured["mode"] = mode
        captured["overrides"] = dict(overrides or {})
        captured["content_type"] = content_type
        result = {
            "job_id": job_id,
            "attempt": attempt,
            "mode": mode,
            "final_status": "succeeded",
            "steps": {},
            "artifact_dir": str((tmp_path / "artifacts").resolve()),
            "artifacts": {},
            "llm_required": True,
            "llm_gate_passed": True,
            "hard_fail_reason": None,
        }
        if isinstance(pipeline_result, dict):
            result.update(pipeline_result)
        return result

    monkeypatch.setattr(activities, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities, "PostgresBusinessStore", _FakePGStore)
    monkeypatch.setattr("worker.pipeline.runner.run_pipeline", _fake_run_pipeline)
    return _FakePGStore


def _patch_workflow_execute_activity(monkeypatch: Any) -> dict[str, list[dict[str, Any]]]:
    payloads: dict[str, list[dict[str, Any]]] = {
        "run_pipeline": [],
        "mark_succeeded": [],
        "mark_failed": [],
    }

    async def _execute_activity(activity_fn: Any, payload: Any, **_: Any) -> dict[str, Any]:
        if activity_fn is workflows.mark_running_activity:
            return {"job_id": str(payload), "attempt": 1, "status": "running"}
        if activity_fn is workflows.run_pipeline_activity:
            payloads["run_pipeline"].append(dict(payload))
            return await activities.run_pipeline_activity(payload)
        if activity_fn is workflows.mark_succeeded_activity:
            payloads["mark_succeeded"].append(dict(payload))
            return {"status": "succeeded", "db_status": "succeeded"}
        if activity_fn is workflows.mark_failed_activity:
            payloads["mark_failed"].append(dict(payload))
            return {"status": "failed"}
        if activity_fn is workflows.send_video_digest_activity:
            return {"ok": True, "status": "sent"}
        raise AssertionError(f"unexpected activity: {activity_fn}")

    monkeypatch.setattr(workflows.workflow, "execute_activity", _execute_activity)
    return payloads


def test_process_job_workflow_explicit_mode_reaches_runner(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}
    fake_pg = _patch_activity_runtime(
        monkeypatch,
        tmp_path=tmp_path,
        fallback_mode="full",
        captured=captured,
    )
    payloads = _patch_workflow_execute_activity(monkeypatch)

    result = asyncio.run(
        workflows.ProcessJobWorkflow().run(
            {
                "job_id": "job-explicit-mode",
                "mode": "text_only",
                "overrides": {"lang": "zh-CN"},
            }
        )
    )

    assert payloads["run_pipeline"][0]["mode"] == "text_only"
    assert payloads["run_pipeline"][0]["overrides"] == {"lang": "zh-CN"}
    assert captured["mode"] == "text_only"
    assert captured["overrides"] == {"lang": "zh-CN"}
    assert captured["content_type"] == "video"
    assert result["pipeline"]["mode"] == "text_only"
    assert fake_pg.get_job_calls == 1


def test_process_job_workflow_db_mode_reaches_runner_when_mode_missing(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    fake_pg = _patch_activity_runtime(
        monkeypatch,
        tmp_path=tmp_path,
        fallback_mode="refresh_llm",
        captured=captured,
    )
    payloads = _patch_workflow_execute_activity(monkeypatch)

    result = asyncio.run(workflows.ProcessJobWorkflow().run("job-db-mode"))

    assert "mode" not in payloads["run_pipeline"][0]
    assert captured["mode"] == "refresh_llm"
    assert captured["overrides"] == {"lang": "zh-CN"}
    assert captured["content_type"] == "video"
    assert result["pipeline"]["mode"] == "refresh_llm"
    assert fake_pg.get_job_calls == 1


def test_process_job_workflow_db_content_type_reaches_runner_when_article(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    _patch_activity_runtime(
        monkeypatch,
        tmp_path=tmp_path,
        fallback_mode="full",
        fallback_content_type="article",
        captured=captured,
    )
    _patch_workflow_execute_activity(monkeypatch)

    result = asyncio.run(workflows.ProcessJobWorkflow().run("job-db-article"))

    assert captured["mode"] == "full"
    assert captured["overrides"] == {"lang": "zh-CN"}
    assert captured["content_type"] == "article"
    assert result["pipeline"]["mode"] == "full"


def test_process_job_workflow_forwards_llm_gate_fields_on_success(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    _patch_activity_runtime(
        monkeypatch,
        tmp_path=tmp_path,
        fallback_mode="full",
        captured=captured,
        pipeline_result={
            "final_status": "succeeded",
            "llm_required": True,
            "llm_gate_passed": True,
            "hard_fail_reason": None,
        },
    )
    payloads = _patch_workflow_execute_activity(monkeypatch)

    result = asyncio.run(workflows.ProcessJobWorkflow().run("job-llm-pass"))

    mark_payload = payloads["mark_succeeded"][0]
    assert mark_payload["llm_required"] is True
    assert mark_payload["llm_gate_passed"] is True
    assert mark_payload["hard_fail_reason"] is None
    assert result["pipeline"]["llm_required"] is True
    assert result["pipeline"]["llm_gate_passed"] is True
    assert result["pipeline"]["hard_fail_reason"] is None


def test_process_job_workflow_forwards_llm_gate_fields_on_failure(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    _patch_activity_runtime(
        monkeypatch,
        tmp_path=tmp_path,
        fallback_mode="full",
        captured=captured,
        pipeline_result={
            "final_status": "failed",
            "fatal_error": "llm_outline:llm_provider_unavailable",
            "llm_required": True,
            "llm_gate_passed": False,
            "hard_fail_reason": "llm_provider_unavailable",
        },
    )
    payloads = _patch_workflow_execute_activity(monkeypatch)

    result = asyncio.run(workflows.ProcessJobWorkflow().run("job-llm-failed"))

    mark_payload = payloads["mark_failed"][0]
    assert mark_payload["llm_required"] is True
    assert mark_payload["llm_gate_passed"] is False
    assert mark_payload["hard_fail_reason"] == "llm_provider_unavailable"
    assert result["ok"] is False
    assert result["pipeline"]["llm_gate_passed"] is False
