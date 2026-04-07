from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline import runner, step_executor
from worker.pipeline.steps import llm_steps


class _FakeSQLiteStore:
    def get_checkpoint(self, _: str) -> dict[str, Any] | None:
        return None

    def mark_step_running(self, **_: Any) -> None:
        return None

    def mark_step_finished(self, **_: Any) -> None:
        return None

    def update_checkpoint(self, **_: Any) -> None:
        return None

    def get_latest_step_run(self, **_: Any) -> dict[str, Any] | None:
        return None


class _FakePGStore:
    def get_job_with_video(self, *, job_id: str) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "job_status": "running",
            "job_kind": "phase2_ingest_stub",
            "idempotency_key": "idem",
            "video_id": "video-id",
            "platform": "youtube",
            "video_uid": "video-uid",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Demo",
            "published_at": None,
        }


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        pipeline_llm_input_mode="auto",
        gemini_api_key=None,
    )


def _build_ctx(tmp_path: Path, *, settings: Settings | None = None) -> runner.PipelineContext:
    current_settings = settings or _make_settings(tmp_path)
    work_dir = tmp_path / "work"
    cache_dir = work_dir / "cache"
    download_dir = work_dir / "downloads"
    frames_dir = work_dir / "frames"
    artifacts_dir = tmp_path / "artifacts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return runner.PipelineContext(
        settings=current_settings,
        sqlite_store=_FakeSQLiteStore(),  # type: ignore[arg-type]
        pg_store=_FakePGStore(),  # type: ignore[arg-type]
        job_id="job",
        attempt=1,
        job_record={},
        work_dir=work_dir,
        cache_dir=cache_dir,
        download_dir=download_dir,
        frames_dir=frames_dir,
        artifacts_dir=artifacts_dir,
    )


def test_step_llm_outline_fails_when_provider_unavailable_by_default(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "failed"
    assert execution.reason == "gemini_api_key_missing"


def test_apply_state_updates_preserves_exact_values() -> None:
    state = {"existing": "value"}
    updates = {
        "flag": True,
        "count": 3,
        "nested": {"status": "ok"},
        "items": ["a", "b"],
        "nothing": None,
    }

    step_executor.apply_state_updates(state, updates)

    assert state == {
        "existing": "value",
        "flag": True,
        "count": 3,
        "nested": {"status": "ok"},
        "items": ["a", "b"],
        "nothing": None,
    }


def test_run_command_once_success_sets_fields_and_subprocess_options(
    monkeypatch: Any,
) -> None:
    called: dict[str, Any] = {}

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        called["args"] = args
        called["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=["echo", "ok"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

    monkeypatch.setattr(step_executor.subprocess, "run", _fake_run)
    result = step_executor.run_command_once(["echo", "ok"], timeout_seconds=7)

    assert called["args"] == (["echo", "ok"],)
    assert called["kwargs"] == {
        "capture_output": True,
        "text": True,
        "timeout": 7,
        "check": False,
    }
    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert result.stderr == ""
    assert result.reason is None


def test_run_command_once_non_zero_exit_returns_failure_with_reason(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        step_executor.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["cmd"],
            returncode=3,
            stdout="partial-output",
            stderr="boom",
        ),
    )

    result = step_executor.run_command_once(["cmd"], timeout_seconds=3)

    assert result.ok is False
    assert result.returncode == 3
    assert result.stdout == "partial-output"
    assert result.stderr == "boom"
    assert result.reason == "non_zero_exit"


def test_run_command_once_binary_missing_returns_binary_not_found(monkeypatch: Any) -> None:
    def _raise_file_not_found(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError

    monkeypatch.setattr(step_executor.subprocess, "run", _raise_file_not_found)

    result = step_executor.run_command_once(["missing-binary"], timeout_seconds=1)

    assert result.ok is False
    assert result.returncode is None
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.reason == "binary_not_found"


def test_run_command_once_timeout_returns_timeout_reason(monkeypatch: Any) -> None:
    def _raise_timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["sleep", "5"], timeout=1)

    monkeypatch.setattr(step_executor.subprocess, "run", _raise_timeout)

    result = step_executor.run_command_once(["sleep", "5"], timeout_seconds=1)

    assert result.ok is False
    assert result.returncode is None
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.reason == "timeout"


def test_step_llm_outline_still_fails_when_flags_disable_provider_soft_fail(
    tmp_path: Path,
) -> None:
    ctx = _build_ctx(
        tmp_path,
        settings=Settings(
            pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
            pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
            pipeline_llm_hard_required=False,
            pipeline_llm_fail_on_provider_error=False,
        ),
    )
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "failed"
    assert execution.degraded is False
    assert execution.output["provider"] == "gemini"
    assert execution.output["llm_required"] is False
    assert execution.output["llm_gate_passed"] is False
    assert execution.output["hard_fail_reason"] is None


def test_step_llm_outline_soft_mode_success_keeps_step_gate_consistent(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def _fake_gemini_generate(*_: Any, **__: Any) -> tuple[str | None, str]:
        return (
            '{"title":"演示视频深度拆解","tldr":["总结关键问题与修复路径。"],"highlights":["我们定位了队列拥塞、重试放大和超时雪崩之间的因果链条。"],"recommended_actions":["先降低重试上限并按依赖分层隔离超时策略。"],"risk_or_pitfalls":["若只提高超时阈值会掩盖真实瓶颈并放大资源占用。"],"chapters":[{"chapter_no":1,"title":"根因定位","anchor":"chapter-01","start_s":0,"end_s":90,"summary":"通过关联日志与追踪数据，确认瓶颈发生在上游服务限流与重试叠加阶段。","bullets":["先按链路拆分超时预算，再逐层收敛重试策略。"],"key_terms":["重试风暴"],"code_snippets":[]}],"timestamp_references":[]}',
            "text",
        )

    monkeypatch.setattr(runner, "_gemini_generate", _fake_gemini_generate)
    ctx = _build_ctx(
        tmp_path,
        settings=Settings(
            pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
            pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
            pipeline_llm_hard_required=False,
        ),
    )
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {"hard_required": False},
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "succeeded"
    assert execution.output["provider"] == "gemini"
    assert execution.output["llm_required"] is False
    assert execution.output["llm_gate_passed"] is True
    assert execution.output["hard_fail_reason"] is None


def test_run_pipeline_marks_degraded_when_non_llm_step_degraded(
    monkeypatch: Any, tmp_path: Path
) -> None:
    async def _ok(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    async def _degraded(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            reason="subtitle_unavailable",
            degraded=True,
            state_updates={"transcript": ""},
        )

    async def _write(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            state_updates={"artifact_dir": str((tmp_path / "artifacts").resolve())},
        )

    async def _embedding(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    monkeypatch.setattr(runner, "_step_fetch_metadata", _ok)
    monkeypatch.setattr(runner, "_step_download_media", _ok)
    monkeypatch.setattr(runner, "_step_collect_subtitles", _degraded)
    monkeypatch.setattr(runner, "_step_collect_comments", _ok)
    monkeypatch.setattr(runner, "_step_extract_frames", _ok)
    monkeypatch.setattr(runner, "_step_llm_outline", _ok)
    monkeypatch.setattr(runner, "_step_llm_digest", _ok)
    monkeypatch.setattr(runner, "_step_build_embeddings", _embedding)
    monkeypatch.setattr(runner, "_step_write_artifacts", _write)

    result = asyncio.run(
        runner.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-degraded",
            attempt=1,
            mode="full",
        )
    )

    assert result["final_status"] == "degraded"
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is True
    assert result["hard_fail_reason"] is None


def test_run_pipeline_marks_failed_when_llm_step_failed(monkeypatch: Any, tmp_path: Path) -> None:
    async def _ok(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    async def _llm_failed(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="failed",
            reason="llm_provider_unavailable",
            error="llm_provider_unavailable",
            degraded=False,
            output={
                "provider": "gemini",
                "llm_required": True,
                "llm_gate_passed": False,
                "hard_fail_reason": "llm_provider_unavailable",
            },
        )

    async def _write(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            state_updates={"artifact_dir": str((tmp_path / "artifacts").resolve())},
        )

    async def _embedding(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    monkeypatch.setattr(runner, "_step_fetch_metadata", _ok)
    monkeypatch.setattr(runner, "_step_download_media", _ok)
    monkeypatch.setattr(runner, "_step_collect_subtitles", _ok)
    monkeypatch.setattr(runner, "_step_collect_comments", _ok)
    monkeypatch.setattr(runner, "_step_extract_frames", _ok)
    monkeypatch.setattr(runner, "_step_llm_outline", _llm_failed)
    monkeypatch.setattr(runner, "_step_llm_digest", _ok)
    monkeypatch.setattr(runner, "_step_build_embeddings", _embedding)
    monkeypatch.setattr(runner, "_step_write_artifacts", _write)

    result = asyncio.run(
        runner.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-failed",
            attempt=1,
            mode="refresh_llm",
        )
    )

    assert result["final_status"] == "failed"
    assert result["steps"]["llm_outline"]["status"] == "failed"
    assert result["steps"]["llm_outline"]["degraded"] is False
    assert "llm_digest" not in result["steps"]
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is False
    assert result["hard_fail_reason"] == "llm_provider_unavailable"


def test_run_pipeline_continues_after_llm_failure_when_not_hard_required(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        pipeline_llm_hard_required=False,
    )
    calls = {"llm_digest": 0, "build_embeddings": 0, "write_artifacts": 0}

    async def _ok(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    async def _llm_failed(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="failed",
            reason="llm_provider_unavailable",
            error="llm_provider_unavailable",
        )

    async def _llm_digest(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["llm_digest"] += 1
        return runner.StepExecution(status="succeeded")

    async def _embedding(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["build_embeddings"] += 1
        return runner.StepExecution(status="succeeded")

    async def _write(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["write_artifacts"] += 1
        return runner.StepExecution(
            status="succeeded",
            state_updates={"artifact_dir": str((tmp_path / "artifacts").resolve())},
        )

    monkeypatch.setattr(runner, "_step_fetch_metadata", _ok)
    monkeypatch.setattr(runner, "_step_download_media", _ok)
    monkeypatch.setattr(runner, "_step_collect_subtitles", _ok)
    monkeypatch.setattr(runner, "_step_collect_comments", _ok)
    monkeypatch.setattr(runner, "_step_extract_frames", _ok)
    monkeypatch.setattr(runner, "_step_llm_outline", _llm_failed)
    monkeypatch.setattr(runner, "_step_llm_digest", _llm_digest)
    monkeypatch.setattr(runner, "_step_build_embeddings", _embedding)
    monkeypatch.setattr(runner, "_step_write_artifacts", _write)

    result = asyncio.run(
        runner.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-soft-fail",
            attempt=1,
            mode="full",
        )
    )

    assert result["steps"]["llm_outline"]["status"] == "failed"
    assert result["steps"]["llm_digest"]["status"] == "succeeded"
    assert result["steps"]["build_embeddings"]["status"] == "succeeded"
    assert result["steps"]["write_artifacts"]["status"] == "succeeded"
    assert result["final_status"] == "degraded"
    assert result["llm_required"] is False
    assert result["llm_gate_passed"] is True
    assert result["hard_fail_reason"] is None
    assert any(item.get("step") == "llm_outline" for item in result["degradations"])
    assert calls["llm_digest"] == 1
    assert calls["build_embeddings"] == 1
    assert calls["write_artifacts"] == 1


def test_run_pipeline_respects_llm_hard_required_override(monkeypatch: Any, tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        pipeline_llm_hard_required=True,
    )
    calls = {"llm_digest": 0, "build_embeddings": 0, "write_artifacts": 0}

    async def _ok(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    async def _llm_failed(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="failed",
            reason="llm_provider_unavailable",
            error="llm_provider_unavailable",
        )

    async def _llm_digest(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["llm_digest"] += 1
        return runner.StepExecution(status="succeeded")

    async def _embedding(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["build_embeddings"] += 1
        return runner.StepExecution(status="succeeded")

    async def _write(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["write_artifacts"] += 1
        return runner.StepExecution(
            status="succeeded",
            state_updates={"artifact_dir": str((tmp_path / "artifacts").resolve())},
        )

    monkeypatch.setattr(runner, "_step_fetch_metadata", _ok)
    monkeypatch.setattr(runner, "_step_download_media", _ok)
    monkeypatch.setattr(runner, "_step_collect_subtitles", _ok)
    monkeypatch.setattr(runner, "_step_collect_comments", _ok)
    monkeypatch.setattr(runner, "_step_extract_frames", _ok)
    monkeypatch.setattr(runner, "_step_llm_outline", _llm_failed)
    monkeypatch.setattr(runner, "_step_llm_digest", _llm_digest)
    monkeypatch.setattr(runner, "_step_build_embeddings", _embedding)
    monkeypatch.setattr(runner, "_step_write_artifacts", _write)

    result = asyncio.run(
        runner.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-override-soft-fail",
            attempt=1,
            mode="full",
            overrides={"llm": {"hard_required": False}},
        )
    )

    assert result["steps"]["llm_outline"]["status"] == "failed"
    assert result["steps"]["llm_digest"]["status"] == "succeeded"
    assert result["steps"]["build_embeddings"]["status"] == "succeeded"
    assert result["steps"]["write_artifacts"]["status"] == "succeeded"
    assert result["final_status"] == "degraded"
    assert result["llm_required"] is False
    assert result["llm_gate_passed"] is True
    assert result["hard_fail_reason"] is None
    assert calls["llm_digest"] == 1
    assert calls["build_embeddings"] == 1
    assert calls["write_artifacts"] == 1


def test_run_pipeline_embedding_degraded_does_not_fail_llm_gate(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    async def _ok(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(status="succeeded")

    async def _embedding_degraded(
        _: runner.PipelineContext, __: dict[str, Any]
    ) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            degraded=True,
            reason="embedding_provider_unavailable",
            error="embedding_provider_unavailable",
            state_updates={
                "embeddings": {
                    "provider": "gemini",
                    "stored_count": 0,
                    "retrievable": False,
                }
            },
        )

    async def _write(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            state_updates={"artifact_dir": str((tmp_path / "artifacts").resolve())},
        )

    monkeypatch.setattr(runner, "_step_fetch_metadata", _ok)
    monkeypatch.setattr(runner, "_step_download_media", _ok)
    monkeypatch.setattr(runner, "_step_collect_subtitles", _ok)
    monkeypatch.setattr(runner, "_step_collect_comments", _ok)
    monkeypatch.setattr(runner, "_step_extract_frames", _ok)
    monkeypatch.setattr(runner, "_step_llm_outline", _ok)
    monkeypatch.setattr(runner, "_step_llm_digest", _ok)
    monkeypatch.setattr(runner, "_step_build_embeddings", _embedding_degraded)
    monkeypatch.setattr(runner, "_step_write_artifacts", _write)

    result = asyncio.run(
        runner.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-embedding-degraded",
            attempt=1,
            mode="full",
        )
    )

    assert result["final_status"] == "degraded"
    assert result["steps"]["build_embeddings"]["status"] == "succeeded"
    assert result["steps"]["build_embeddings"]["degraded"] is True
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is True
    assert result["hard_fail_reason"] is None


def test_execute_step_uses_pipeline_llm_max_retries(tmp_path: Path) -> None:
    ctx = _build_ctx(
        tmp_path,
        settings=Settings(
            pipeline_retry_attempts=5,
            pipeline_llm_max_retries=1,
        ),
    )

    calls = {"count": 0}

    async def _flaky(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        calls["count"] += 1
        if calls["count"] == 1:
            return runner.StepExecution(
                status="failed",
                reason="timeout",
                error="timeout",
                degraded=True,
            )
        return runner.StepExecution(status="succeeded")

    state: dict[str, Any] = {
        "llm_policy": {},
        "steps": {},
        "degradations": [],
        "llm_media_input": {"video_available": False, "frame_count": 0},
    }

    step_record = asyncio.run(
        runner._execute_step(
            ctx,
            state,
            step_name="llm_outline",
            step_func=_flaky,
            critical=False,
            resume_hint=False,
            force_run=True,
        )
    )

    assert calls["count"] == 2
    assert step_record["status"] == "succeeded"
    assert step_record["retry_meta"]["attempts"] == 2
    assert step_record["retry_meta"]["retries_configured"] == 1


def test_step_llm_outline_fails_when_quality_is_insufficient(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def _fake_gemini_generate(*_: Any, **__: Any) -> tuple[str | None, str]:
        return (
            '{"title":"演示视频","tldr":["短"],"highlights":["短"],"recommended_actions":[],"risk_or_pitfalls":[],"chapters":[{"chapter_no":1,"title":"第一章","anchor":"chapter-01","start_s":0,"end_s":60,"summary":"短","bullets":["短"],"key_terms":[],"code_snippets":[]}],"timestamp_references":[]}',
            "text",
        )

    monkeypatch.setattr(runner, "_gemini_generate", _fake_gemini_generate)
    ctx = _build_ctx(tmp_path)
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "failed"
    assert execution.reason == "llm_quality_insufficient"
    assert execution.output["provider"] == "gemini"
    assert execution.output["llm_gate_passed"] is False


def test_step_llm_digest_fails_when_quality_is_insufficient(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def _fake_gemini_generate(*_: Any, **__: Any) -> tuple[str | None, str]:
        return (
            '{"title":"演示视频","summary":"太短","tldr":["短"],"highlights":["短"],"action_items":[],"code_blocks":[],"timestamp_references":[],"fallback_notes":[]}',
            "text",
        )

    monkeypatch.setattr(runner, "_gemini_generate", _fake_gemini_generate)
    ctx = _build_ctx(tmp_path)
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
        "outline": {
            "title": "演示视频",
            "highlights": ["定位耗时根因并给出修复方案。"],
            "chapters": [
                {
                    "chapter_no": 1,
                    "title": "背景",
                    "anchor": "chapter-01",
                    "start_s": 0,
                    "end_s": 60,
                    "summary": "介绍问题背景与观测信号。",
                    "bullets": ["先确认告警范围，再定位慢点。"],
                }
            ],
        },
    }

    execution = asyncio.run(runner._step_llm_digest(ctx, state))

    assert execution.status == "failed"
    assert execution.reason == "llm_quality_insufficient"
    assert execution.output["provider"] == "gemini"
    assert execution.output["llm_gate_passed"] is False


def test_step_llm_outline_fails_when_translation_fails(monkeypatch: Any, tmp_path: Path) -> None:
    def _fake_gemini_generate(*_: Any, **__: Any) -> tuple[str | None, str]:
        return (
            '{"title":"Demo video","tldr":["This section explains timeout and retry interactions."],"highlights":["The request waterfall exposes upstream saturation and queue buildup."],"recommended_actions":[],"risk_or_pitfalls":[],"chapters":[{"chapter_no":1,"title":"Root cause","anchor":"chapter-01","start_s":0,"end_s":60,"summary":"We identify root cause by correlating traces with queue latency spikes.","bullets":["Measure queue depth and retry amplification first."],"key_terms":[],"code_snippets":[]}],"timestamp_references":[]}',
            "text",
        )

    monkeypatch.setattr(runner, "_gemini_generate", _fake_gemini_generate)
    monkeypatch.setattr(llm_steps, "_translate_payload_to_chinese", lambda *args, **kwargs: None)
    ctx = _build_ctx(tmp_path)
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "failed"
    assert execution.reason == "llm_translation_failed"
    assert execution.output["provider"] == "gemini"
    assert execution.output["llm_gate_passed"] is False


def test_step_llm_outline_fails_when_schema_contains_extra_fields(
    monkeypatch: Any, tmp_path: Path
) -> None:
    def _fake_gemini_generate(*_: Any, **__: Any) -> tuple[str | None, str]:
        return (
            '{"title":"演示视频","tldr":["梳理关键问题。"],"highlights":["明确了错误放大的触发条件与影响路径。"],"recommended_actions":[],"risk_or_pitfalls":[],"chapters":[{"chapter_no":1,"title":"第一章","anchor":"chapter-01","start_s":0,"end_s":60,"summary":"介绍关键链路与异常扩散机制。","bullets":["优先确认上游超时门限与重试策略。"],"key_terms":[],"code_snippets":[]}],"timestamp_references":[],"unexpected":"nope"}',
            "text",
        )

    monkeypatch.setattr(runner, "_gemini_generate", _fake_gemini_generate)
    ctx = _build_ctx(tmp_path)
    state = {
        "metadata": {"title": "Demo"},
        "title": "Demo",
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "media_path": "",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_policy": {},
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "failed"
    assert execution.reason == "llm_output_invalid_json"
