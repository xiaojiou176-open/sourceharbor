from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

import pytest
from worker.config import Settings
from worker.pipeline.types import PipelineContext, StepExecution

from apps.worker.worker.pipeline import step_executor


class _FakeProcess:
    def __init__(self, *, block_on_wait: bool = False) -> None:
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False
        self.waited = False
        self.block_on_wait = block_on_wait
        self.pid = 12345

    async def communicate(self) -> tuple[bytes, bytes]:
        await asyncio.sleep(30)
        self.returncode = 0
        return b"ok", b""

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = -15

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        if self.block_on_wait and not self.killed:
            await asyncio.sleep(30)
        self.waited = True
        return self.returncode or 0


def _build_ctx(tmp_path: Path, *, timeout: int) -> PipelineContext:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        pipeline_subprocess_timeout_seconds=timeout,
    )
    work_dir = tmp_path / "work"
    cache_dir = work_dir / "cache"
    download_dir = work_dir / "downloads"
    frames_dir = work_dir / "frames"
    artifacts_dir = tmp_path / "artifacts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return PipelineContext(
        settings=settings,
        sqlite_store=None,  # type: ignore[arg-type]
        pg_store=None,  # type: ignore[arg-type]
        job_id="job",
        attempt=1,
        job_record={},
        work_dir=work_dir,
        cache_dir=cache_dir,
        download_dir=download_dir,
        frames_dir=frames_dir,
        artifacts_dir=artifacts_dir,
    )


def test_run_command_terminates_subprocess_on_timeout(monkeypatch, tmp_path: Path) -> None:
    fake_process = _FakeProcess()
    captured: dict[str, Any] = {}

    async def _fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    ctx = _build_ctx(tmp_path, timeout=1)

    result = asyncio.run(step_executor.run_command(ctx, ["sleep", "30"]))

    assert result.ok is False
    assert result.reason == "timeout"
    assert fake_process.terminated is True
    assert fake_process.killed is False
    assert fake_process.waited is True
    assert captured["args"] == ("sleep", "30")
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["stdout"] is asyncio.subprocess.PIPE
    assert captured["kwargs"]["stderr"] is asyncio.subprocess.PIPE


def test_run_command_kills_subprocess_when_terminate_times_out(monkeypatch, tmp_path: Path) -> None:
    fake_process = _FakeProcess(block_on_wait=True)
    captured: dict[str, Any] = {}

    async def _fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    ctx = _build_ctx(tmp_path, timeout=1)

    result = asyncio.run(step_executor.run_command(ctx, ["sleep", "30"]))

    assert result.ok is False
    assert result.reason == "timeout"
    assert fake_process.terminated is True
    assert fake_process.killed is True
    assert fake_process.waited is True
    assert captured["args"] == ("sleep", "30")
    assert captured["kwargs"]["start_new_session"] is True


def test_run_command_kills_subprocess_on_cancellation(monkeypatch, tmp_path: Path) -> None:
    fake_process = _FakeProcess()
    captured: dict[str, Any] = {}

    async def _fake_create_subprocess_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    ctx = _build_ctx(tmp_path, timeout=60)

    async def _runner() -> None:
        task = asyncio.create_task(step_executor.run_command(ctx, ["sleep", "30"]))
        await asyncio.sleep(0.01)
        task.cancel()
        await task

    try:
        asyncio.run(_runner())
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("expected asyncio.CancelledError to propagate")

    assert fake_process.killed is True
    assert fake_process.waited is True
    assert captured["args"] == ("sleep", "30")
    assert captured["kwargs"]["start_new_session"] is True


def test_run_command_non_zero_exit_decodes_output(monkeypatch, tmp_path: Path) -> None:
    class _FinishedProcess:
        returncode = 7
        pid = 67890

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"\xffstdout", b"\xfestderr")

    created: dict[str, Any] = {}
    wait_for_timeouts: list[int] = []

    async def _fake_create_subprocess_exec(*args, **kwargs):
        created["args"] = args
        created["kwargs"] = kwargs
        return _FinishedProcess()

    async def _fake_wait_for(awaitable: Any, timeout: int) -> Any:
        wait_for_timeouts.append(timeout)
        return await awaitable

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(step_executor.asyncio, "wait_for", _fake_wait_for)
    ctx = _build_ctx(tmp_path, timeout=5)

    result = asyncio.run(step_executor.run_command(ctx, ["echo", "demo"]))

    assert result.ok is False
    assert result.returncode == 7
    assert result.reason == "non_zero_exit"
    assert result.stdout == "stdout"
    assert result.stderr == "stderr"
    assert created["args"] == ("echo", "demo")
    assert created["kwargs"]["start_new_session"] is True
    assert wait_for_timeouts == [5]


def test_run_command_binary_missing_sets_ok_false(monkeypatch, tmp_path: Path) -> None:
    async def _raise_missing(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _raise_missing)
    ctx = _build_ctx(tmp_path, timeout=5)

    result = asyncio.run(step_executor.run_command(ctx, ["missing-binary"]))

    assert result.ok is False
    assert result.reason == "binary_not_found"


def test_run_command_enforces_minimum_timeout_of_one_second(monkeypatch, tmp_path: Path) -> None:
    class _FastProcess:
        returncode = 0
        pid = 22222

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"ok", b"")

    timeouts: list[int] = []

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _FastProcess()

    async def _fake_wait_for(awaitable: Any, timeout: int) -> Any:
        timeouts.append(timeout)
        return await awaitable

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    monkeypatch.setattr(step_executor.asyncio, "wait_for", _fake_wait_for)
    ctx = _build_ctx(tmp_path, timeout=0)

    result = asyncio.run(step_executor.run_command(ctx, ["echo", "ok"]))

    assert result.ok is True
    assert result.reason is None
    assert timeouts == [1]


def test_run_command_treats_returncode_one_as_non_zero_exit(monkeypatch, tmp_path: Path) -> None:
    class _ReturnCodeOneProcess:
        returncode = 1
        pid = 33333

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"one", b"")

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _ReturnCodeOneProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    ctx = _build_ctx(tmp_path, timeout=3)

    result = asyncio.run(step_executor.run_command(ctx, ["echo", "one"]))

    assert result.returncode == 1
    assert result.ok is False
    assert result.reason == "non_zero_exit"
    assert result.stdout == "one"
    assert result.stderr == ""


def test_run_command_empty_streams_stay_empty_strings(monkeypatch, tmp_path: Path) -> None:
    class _EmptyOutputProcess:
        returncode = 0
        pid = 44444

        async def communicate(self) -> tuple[bytes, bytes]:
            return (b"", b"")

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _EmptyOutputProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)
    ctx = _build_ctx(tmp_path, timeout=2)

    result = asyncio.run(step_executor.run_command(ctx, ["echo", ""]))

    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    assert result.reason is None


class _FakeSQLiteStore:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: list[dict[str, Any]] = []

    def mark_step_running(self, **payload: Any) -> None:
        self.started.append(dict(payload))

    def mark_step_finished(self, **payload: Any) -> None:
        self.finished.append(dict(payload))

    def update_checkpoint(self, **_payload: Any) -> None:
        return None

    def get_latest_step_run(self, **_payload: Any) -> dict[str, Any] | None:
        return None


def test_execute_step_marks_failed_when_cancelled(monkeypatch, tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _build_ctx(tmp_path, timeout=30)
    ctx = PipelineContext(
        settings=ctx.settings,
        sqlite_store=sqlite_store,  # type: ignore[arg-type]
        pg_store=ctx.pg_store,  # type: ignore[arg-type]
        job_id=ctx.job_id,
        attempt=ctx.attempt,
        job_record=ctx.job_record,
        work_dir=ctx.work_dir,
        cache_dir=ctx.cache_dir,
        download_dir=ctx.download_dir,
        frames_dir=ctx.frames_dir,
        artifacts_dir=ctx.artifacts_dir,
    )
    state: dict[str, Any] = {"degradations": [], "steps": {}}
    expected_cache_key = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")[
        "cache_key"
    ]
    signature = inspect.signature(step_executor.execute_step)
    assert signature.parameters["critical"].default is step_executor._DEFAULT_ARG_UNSET

    async def _cancelled_step(_ctx: PipelineContext, _state: dict[str, Any]) -> StepExecution:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            step_executor.execute_step(
                ctx,
                state,
                step_name="fetch_metadata",
                step_func=_cancelled_step,
                critical=False,
            )
        )

    assert len(sqlite_store.started) == 1
    assert len(sqlite_store.finished) == 1
    assert sqlite_store.finished[0]["job_id"] == ctx.job_id
    assert sqlite_store.finished[0]["step_name"] == "fetch_metadata"
    assert sqlite_store.finished[0]["attempt"] == ctx.attempt
    assert sqlite_store.finished[0]["status"] == "failed"
    assert sqlite_store.finished[0]["error_payload"]["reason"] == "cancelled"
    assert sqlite_store.finished[0]["error_payload"]["error"] == "step_cancelled"
    assert sqlite_store.finished[0]["error_payload"]["error_kind"] == "fatal"
    assert sqlite_store.finished[0]["error_payload"]["retry_meta"]["strategy"] == "cancelled"
    assert sqlite_store.finished[0]["error_kind"] == "fatal"
    assert sqlite_store.finished[0]["result_payload"]["status"] == "failed"
    assert sqlite_store.finished[0]["result_payload"]["reason"] == "cancelled"
    assert sqlite_store.finished[0]["result_payload"]["error"] == "step_cancelled"
    assert sqlite_store.finished[0]["result_payload"]["error_kind"] == "fatal"
    assert sqlite_store.finished[0]["result_payload"]["degraded"] is True
    assert sqlite_store.finished[0]["cache_key"] == expected_cache_key
    retry_meta = sqlite_store.finished[0]["retry_meta"]
    assert retry_meta["strategy"] == "cancelled"
    assert retry_meta["classification"] == "fatal"
    assert retry_meta["attempts"] == 1
    assert retry_meta["retries_used"] == 0
    assert retry_meta["retries_configured"] == 0
    assert retry_meta["history"] == ["fatal"]
    assert retry_meta["delays_seconds"] == []
    assert retry_meta["resume_hint"] is False
    assert state["steps"]["fetch_metadata"]["status"] == "failed"
    assert state["steps"]["fetch_metadata"]["reason"] == "cancelled"
    assert state["steps"]["fetch_metadata"]["retry_meta"]["strategy"] == "cancelled"
    assert state["steps"]["fetch_metadata"]["retry_meta"]["delays_seconds"] == []
    assert state["steps"]["fetch_metadata"]["retry_meta"]["resume_hint"] is False
    assert len(state["degradations"]) == 1
    degradation = state["degradations"][0]
    assert degradation["step"] == "fetch_metadata"
    assert degradation["status"] == "failed"
    assert degradation["reason"] == "cancelled"
    assert degradation["error"] == "step_cancelled"
    assert degradation["error_kind"] == "fatal"
    assert degradation["retry_meta"]["delays_seconds"] == []
    assert degradation["retry_meta"]["resume_hint"] is False
    assert degradation["cache_meta"] == {}


def test_execute_step_cancelled_initializes_steps_bucket_when_missing(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    base_ctx = _build_ctx(tmp_path, timeout=30)
    ctx = PipelineContext(
        settings=base_ctx.settings,
        sqlite_store=sqlite_store,  # type: ignore[arg-type]
        pg_store=base_ctx.pg_store,  # type: ignore[arg-type]
        job_id=base_ctx.job_id,
        attempt=base_ctx.attempt,
        job_record=base_ctx.job_record,
        work_dir=base_ctx.work_dir,
        cache_dir=base_ctx.cache_dir,
        download_dir=base_ctx.download_dir,
        frames_dir=base_ctx.frames_dir,
        artifacts_dir=base_ctx.artifacts_dir,
    )
    state: dict[str, Any] = {"degradations": []}

    async def _cancelled_step(_ctx: PipelineContext, _state: dict[str, Any]) -> StepExecution:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            step_executor.execute_step(
                ctx,
                state,
                step_name="fetch_metadata",
                step_func=_cancelled_step,
                critical=False,
            )
        )

    assert "steps" in state
    assert state["steps"]["fetch_metadata"]["status"] == "failed"
    assert state["steps"]["fetch_metadata"]["reason"] == "cancelled"
    assert len(state["degradations"]) == 1
    assert state["degradations"][0]["status"] == "failed"


def test_execute_step_cancelled_passes_cache_meta_to_append_degradation(
    monkeypatch, tmp_path: Path
) -> None:
    sqlite_store = _FakeSQLiteStore()
    base_ctx = _build_ctx(tmp_path, timeout=30)
    ctx = PipelineContext(
        settings=base_ctx.settings,
        sqlite_store=sqlite_store,  # type: ignore[arg-type]
        pg_store=base_ctx.pg_store,  # type: ignore[arg-type]
        job_id=base_ctx.job_id,
        attempt=base_ctx.attempt,
        job_record=base_ctx.job_record,
        work_dir=base_ctx.work_dir,
        cache_dir=base_ctx.cache_dir,
        download_dir=base_ctx.download_dir,
        frames_dir=base_ctx.frames_dir,
        artifacts_dir=base_ctx.artifacts_dir,
    )
    state: dict[str, Any] = {"degradations": [], "steps": {}}
    captured: dict[str, Any] = {}
    original_append_degradation = step_executor.append_degradation

    def _capture_append_degradation(*args: Any, **kwargs: Any) -> Any:
        captured["cache_meta"] = kwargs.get("cache_meta", "<missing>")
        return original_append_degradation(*args, **kwargs)

    monkeypatch.setattr(step_executor, "append_degradation", _capture_append_degradation)

    async def _cancelled_step(_ctx: PipelineContext, _state: dict[str, Any]) -> StepExecution:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            step_executor.execute_step(
                ctx,
                state,
                step_name="fetch_metadata",
                step_func=_cancelled_step,
                critical=False,
            )
        )

    assert captured["cache_meta"] == {}
