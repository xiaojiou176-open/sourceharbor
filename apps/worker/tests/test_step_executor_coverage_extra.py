from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline.types import PipelineContext, StepExecution

from apps.worker.worker.pipeline import step_executor


class _FakeSQLiteStore:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: list[dict[str, Any]] = []
        self.checkpoints: list[dict[str, Any]] = []
        self.latest_step_run: dict[str, Any] | None = None
        self.latest_step_queries: list[dict[str, Any]] = []

    def mark_step_running(self, **payload: Any) -> None:
        self.started.append(dict(payload))

    def mark_step_finished(self, **payload: Any) -> None:
        self.finished.append(dict(payload))

    def update_checkpoint(self, **payload: Any) -> None:
        self.checkpoints.append(dict(payload))

    def get_latest_step_run(self, **payload: Any) -> dict[str, Any] | None:
        self.latest_step_queries.append(dict(payload))
        return self.latest_step_run


class _FakePGStore:
    def upsert_video_embeddings(self, **_: Any) -> int:
        return 0


def _make_ctx(tmp_path: Path, *, sqlite_store: _FakeSQLiteStore | None = None) -> PipelineContext:
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
        settings=Settings(
            pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
            pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
            pipeline_subprocess_timeout_seconds=1,
        ),
        sqlite_store=(sqlite_store or _FakeSQLiteStore()),  # type: ignore[arg-type]
        pg_store=_FakePGStore(),  # type: ignore[arg-type]
        job_id="job-step-executor-extra",
        attempt=1,
        job_record={"video_id": "vid-1"},
        work_dir=work_dir,
        cache_dir=cache_dir,
        download_dir=download_dir,
        frames_dir=frames_dir,
        artifacts_dir=artifacts_dir,
    )


@dataclass
class _ModelDumpObj:
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return self.payload


@dataclass
class _DictObj:
    payload: dict[str, Any]

    def dict(self) -> dict[str, Any]:
        return self.payload


class _BrokenIsoObj:
    def isoformat(self) -> str:
        raise RuntimeError("broken")

    def __str__(self) -> str:
        return "broken-iso"


class _IsoObj:
    def isoformat(self) -> str:
        return "preferred-iso"

    def __str__(self) -> str:
        return "fallback-string"


def test_jsonable_and_write_json_helpers(tmp_path: Path) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    payload = {
        "tuple": (1, 2),
        "set": {3, 4},
        "path": tmp_path / "demo.txt",
        "dt": now,
        "model": _ModelDumpObj(payload={"a": 1}),
        "dict_obj": _DictObj(payload={"b": 2}),
        "iso_broken": _BrokenIsoObj(),
        "iso_ok": _IsoObj(),
        "non_ascii": "中文内容",
    }
    json_ready = step_executor.jsonable(payload)
    assert json_ready["tuple"] == [1, 2]
    assert sorted(json_ready["set"]) == [3, 4]
    assert json_ready["dt"] == now.isoformat()
    assert json_ready["model"] == {"a": 1}
    assert json_ready["dict_obj"] == {"b": 2}
    assert json_ready["iso_broken"] == "broken-iso"
    assert json_ready["iso_ok"] == "preferred-iso"

    output_path = tmp_path / "payload.json"
    step_executor.write_json(output_path, payload)
    loaded = json.loads(step_executor.read_text_file(output_path))
    written = output_path.read_text(encoding="utf-8")
    assert written.startswith("{\n")
    assert "中文内容" in written
    assert "\\u4e2d\\u6587\\u5185\\u5bb9" not in written
    assert loaded["model"] == {"a": 1}
    assert loaded["iso_ok"] == "preferred-iso"


def test_write_json_uses_utf8_encoding_explicitly(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def _fake_write_text(self: Path, text: str, encoding: str | None = None, **_: Any) -> int:
        captured["path"] = self
        captured["text"] = text
        captured["encoding"] = encoding
        return len(text)

    monkeypatch.setattr(Path, "write_text", _fake_write_text)

    output_path = tmp_path / "payload.json"
    step_executor.write_json(output_path, {"message": "你好"})

    assert captured["path"] == output_path
    assert captured["encoding"] == "utf-8"
    assert json.loads(captured["text"]) == {"message": "你好"}


def test_read_text_file_uses_utf8_ignore_flags(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    def _fake_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        captured["path"] = self
        captured["args"] = args
        captured["kwargs"] = dict(kwargs)
        return "content"

    monkeypatch.setattr(Path, "read_text", _fake_read_text)
    target = tmp_path / "file.txt"
    assert step_executor.read_text_file(target) == "content"
    assert captured["path"] == target
    assert captured["args"] == ()
    assert captured["kwargs"] == {"encoding": "utf-8", "errors": "ignore"}


def test_truncate_text_ignores_invalid_surrogate_codepoints() -> None:
    value = "\udcff" * 300
    truncated = step_executor._truncate_text(value)

    assert step_executor._truncate_text.__kwdefaults__ == {"keep": None}
    assert truncated.startswith("<<sha256:")
    assert "|len:300>>" in truncated
    assert step_executor._truncate_text("x" * 241) != "x" * 241


def test_signature_and_state_update_helpers_cover_small_branches(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state = {
        "source_url": "https://example.com/watch?v=demo",
        "title": "Demo title",
        "platform": "youtube",
        "video_uid": "demo-id",
        "published_at": None,
    }

    truncated = step_executor._truncate_text("x" * 300)
    normalized = step_executor._normalize_for_signature(
        {"path": Path("/tmp/demo"), "items": ("a", {"nested": "b"}), "value": "ok"}
    )
    subset = step_executor._settings_subset(ctx.settings, ("pipeline_max_frames", "missing_key"))
    payload = step_executor._step_input_payload(ctx, state, "fetch_metadata")
    target_state = {"degradations": []}
    step_executor.apply_state_updates(target_state, {"done": True})
    step_executor.append_degradation(
        target_state,
        "fetch_metadata",
        status="skipped",
        reason="cache_hit",
        error="none",
    )

    assert truncated.startswith("<<sha256:")
    assert "|len:300>>" in truncated
    assert step_executor._truncate_text("x" * 240) == "x" * 240
    assert normalized["path"] == str(Path("/tmp/demo").resolve())
    assert normalized["items"] == ["a", {"nested": "b"}]
    assert subset["missing_key"] is None
    assert payload["state"]["source_url"] == "https://example.com/watch?v=demo"
    assert payload["settings"] == {
        "pipeline_subprocess_timeout_seconds": 1,
        "bilibili_cookie": None,
    }
    assert target_state["done"] is True
    degradation = target_state["degradations"][0]
    assert degradation["step"] == "fetch_metadata"
    assert degradation["status"] == "skipped"
    assert degradation["reason"] == "cache_hit"
    assert degradation["error"] == "none"
    assert degradation["error_kind"] is None
    assert degradation["retry_meta"] == {}
    assert degradation["cache_meta"] == {}
    assert isinstance(degradation["at"], str)


def test_cache_helpers_and_skip_builder(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state = {"source_url": "https://www.youtube.com/watch?v=demo"}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    assert cache_info["step"] == "fetch_metadata"
    assert "STEP" not in cache_info
    execution = StepExecution(status="succeeded", output={"ok": True}, state_updates={"x": 1})
    step_executor._write_step_cache(cache_info, execution)

    loaded, reason = step_executor._load_step_execution_from_cache(cache_info)
    assert loaded is not None
    assert reason == "cache_hit"
    cache_payload = json.loads(cache_info["cache_path"].read_text(encoding="utf-8"))
    legacy_payload = json.loads(cache_info["legacy_path"].read_text(encoding="utf-8"))
    assert cache_payload == legacy_payload
    assert cache_info["cache_path"].read_text(encoding="utf-8") == cache_info[
        "legacy_path"
    ].read_text(encoding="utf-8")
    assert cache_payload["cache_meta"]["cache_key"] == cache_info["cache_key"]
    assert cache_payload["cache_meta"]["signature"] == cache_info["signature"]
    assert cache_payload["cache_meta"]["version"] == cache_info["version"]
    assert isinstance(cache_payload["cache_meta"]["cached_at"], str)

    cache_info["cache_path"].unlink()
    loaded_legacy, legacy_reason = step_executor._load_step_execution_from_cache(cache_info)
    assert loaded_legacy is None
    assert legacy_reason is None

    cache_info_v2 = dict(cache_info)
    cache_info_v2["version"] = "v2"
    none_loaded, none_reason = step_executor._load_step_execution_from_cache(cache_info_v2)
    assert none_loaded is None
    assert none_reason is None

    same_cache = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    changed_cache = step_executor.build_step_cache_info(
        ctx,
        {**state, "source_url": "https://www.youtube.com/watch?v=other"},
        "fetch_metadata",
    )
    assert same_cache["signature"] == cache_info["signature"]
    assert changed_cache["signature"] != cache_info["signature"]

    skip_fn = step_executor.build_mode_skip_step("collect_subtitles", "text_only")
    skip_execution = asyncio.run(skip_fn(ctx, state))
    assert skip_execution.status == "skipped"
    assert skip_execution.reason == "mode_matrix_skip"
    assert skip_execution.output == {"skipped_by_mode": "text_only", "step": "collect_subtitles"}
    assert skip_execution.state_updates == {"transcript": "", "subtitle_files": []}

    failed_payload = step_executor._build_error_payload(
        StepExecution(status="failed", reason="boom", error="err")
    )
    skipped_payload = step_executor._build_error_payload(
        StepExecution(status="skipped", reason="manual_skip")
    )
    assert failed_payload == {
        "reason": "boom",
        "error": "err",
        "error_kind": None,
        "retry_meta": {},
    }
    assert skipped_payload == {"reason": "manual_skip", "error_kind": None, "retry_meta": {}}
    assert step_executor._build_error_payload(StepExecution(status="succeeded")) is None


def test_build_step_cache_info_keeps_contract_inputs_only(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state = {
        "source_url": "https://www.youtube.com/watch?v=demo",
        "title": "Demo",
        "platform": "youtube",
        "video_uid": "video-uid",
        "published_at": None,
    }
    baseline = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    with_untracked = step_executor.build_step_cache_info(
        ctx,
        {**state, "non_contract_field": "ignored"},
        "fetch_metadata",
    )
    changed_source = step_executor.build_step_cache_info(
        ctx,
        {**state, "source_url": "https://www.youtube.com/watch?v=changed"},
        "fetch_metadata",
    )

    assert baseline["signature"] == with_untracked["signature"]
    assert baseline["signature"] != changed_source["signature"]
    assert baseline["cache_key"] == f"fetch_metadata:{baseline['version']}:{baseline['signature']}"
    assert baseline["cache_path"].name == f"{baseline['version']}_{baseline['signature']}.json"
    assert baseline["cache_path"].parent.name == "fetch_metadata"
    assert baseline["legacy_path"].name == "fetch_metadata.json"


def test_build_step_cache_info_unknown_step_uses_v1_fallback(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    info = step_executor.build_step_cache_info(ctx, {"non_contract_field": "x"}, "unknown_step")

    assert info["version"] == "v1"
    assert info["cache_key"].startswith("unknown_step:v1:")
    assert info["cache_path"].name.startswith("v1_")
    assert info["legacy_path"].name == "unknown_step.json"


def test_build_step_cache_info_signature_contract_for_non_default_version(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state = {
        "title": "Demo",
        "metadata": {"k": "v"},
        "outline": {"a": 1},
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "source_url": "https://www.youtube.com/watch?v=demo",
        "llm_input_mode": "text",
        "llm_media_input": {"video_available": False, "frame_count": 0},
        "llm_policy": {"hard_required": False},
    }
    info = step_executor.build_step_cache_info(ctx, state, "llm_digest")
    inputs = step_executor._step_input_payload(ctx, state, "llm_digest")
    expected_payload = {"step": "llm_digest", "version": "v7", "inputs": inputs}
    expected_signature = hashlib.sha256(
        json.dumps(
            expected_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:24]

    assert info["version"] == "v7"
    assert info["signature"] == expected_signature
    assert info["cache_key"] == f"llm_digest:v7:{expected_signature}"


def test_write_step_cache_preserves_existing_cache_meta_fields(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state = {"source_url": "https://www.youtube.com/watch?v=demo"}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    execution = StepExecution(
        status="succeeded",
        output={"ok": True},
        state_updates={"done": True},
        cache_meta={"existing": "keep-me"},
    )

    step_executor._write_step_cache(cache_info, execution)
    payload = json.loads(cache_info["cache_path"].read_text(encoding="utf-8"))

    assert payload["output"] == {"ok": True}
    assert payload["state_updates"] == {"done": True}
    assert payload["cache_meta"]["existing"] == "keep-me"
    assert payload["cache_meta"]["cache_key"] == cache_info["cache_key"]
    assert payload["cache_meta"]["signature"] == cache_info["signature"]
    assert payload["cache_meta"]["version"] == cache_info["version"]
    assert isinstance(payload["cache_meta"]["cached_at"], str)
    assert json.loads(cache_info["legacy_path"].read_text(encoding="utf-8")) == payload


def test_write_step_cache_calls_json_dumps_with_explicit_non_ascii_settings(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    ctx = _make_ctx(tmp_path)
    cache_info = step_executor.build_step_cache_info(
        ctx,
        {"source_url": "https://www.youtube.com/watch?v=demo"},
        "fetch_metadata",
    )

    def _fake_dumps(
        payload: Any, *, ensure_ascii: bool, indent: int, sort_keys: bool, **_: Any
    ) -> str:
        captured.append(
            {
                "payload": payload,
                "ensure_ascii": ensure_ascii,
                "indent": indent,
                "sort_keys": sort_keys,
            }
        )
        return '{"ok": true}'

    monkeypatch.setattr(step_executor.json, "dumps", _fake_dumps)
    step_executor._write_step_cache(
        cache_info, StepExecution(status="succeeded", output={"message": "你好"})
    )

    assert len(captured) == 2
    assert all(call["ensure_ascii"] is False for call in captured)
    assert all(call["indent"] == 2 for call in captured)
    assert all(call["sort_keys"] is True for call in captured)


def test_write_step_cache_handles_missing_cache_meta_in_record(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    cache_info = step_executor.build_step_cache_info(
        ctx,
        {"source_url": "https://www.youtube.com/watch?v=demo"},
        "fetch_metadata",
    )

    class _RecordWithoutCacheMeta:
        def to_record(self) -> dict[str, Any]:
            return {
                "status": "succeeded",
                "output": {"ok": True},
                "state_updates": {"done": True},
            }

    step_executor._write_step_cache(cache_info, _RecordWithoutCacheMeta())  # type: ignore[arg-type]
    payload = json.loads(cache_info["cache_path"].read_text(encoding="utf-8"))
    assert payload["cache_meta"]["cache_key"] == cache_info["cache_key"]
    assert payload["cache_meta"]["signature"] == cache_info["signature"]
    assert payload["cache_meta"]["version"] == cache_info["version"]
    assert isinstance(payload["cache_meta"]["cached_at"], str)


def test_write_step_cache_uses_utf8_and_keeps_non_ascii(monkeypatch: Any, tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    cache_info = step_executor.build_step_cache_info(
        ctx,
        {"source_url": "https://www.youtube.com/watch?v=demo"},
        "fetch_metadata",
    )
    execution = StepExecution(
        status="succeeded",
        output={"title": "演示视频"},
        state_updates={"digest": "中文内容"},
    )
    writes: list[tuple[Path, str, str | None]] = []

    def _fake_write_text(self: Path, text: str, encoding: str | None = None, **_: Any) -> int:
        writes.append((self, text, encoding))
        return len(text)

    monkeypatch.setattr(Path, "write_text", _fake_write_text)
    step_executor._write_step_cache(cache_info, execution)

    assert len(writes) == 2
    for path, text, encoding in writes:
        assert path in {cache_info["cache_path"], cache_info["legacy_path"]}
        assert encoding == "utf-8"
        assert "演示视频" in text
        assert "\\u6f14\\u793a" not in text


def test_append_degradation_preserves_explicit_retry_and_cache_meta(tmp_path: Path) -> None:
    _ = tmp_path
    state: dict[str, Any] = {"degradations": []}
    retry_meta = {"attempts": 2, "strategy": "manual"}
    cache_meta = {"source": "manual_cache"}

    step_executor.append_degradation(
        state,
        "fetch_metadata",
        status="failed",
        reason="manual_failure",
        error="boom",
        error_kind="timeout",
        retry_meta=retry_meta,
        cache_meta=cache_meta,
    )
    step_executor.append_degradation(state, "fetch_metadata", status="failed")

    first, second = state["degradations"]
    assert first["retry_meta"] == retry_meta
    assert first["cache_meta"] == cache_meta
    assert first["reason"] == "manual_failure"
    assert first["error"] == "boom"
    assert first["error_kind"] == "timeout"
    assert second["retry_meta"] == {}
    assert second["cache_meta"] == {}
    assert second["retry_meta"] is not first["retry_meta"]
    assert second["cache_meta"] is not first["cache_meta"]


def test_append_degradation_initializes_state_bucket_when_missing() -> None:
    state: dict[str, Any] = {}

    step_executor.append_degradation(state, "collect_subtitles", status="skipped", reason="empty")

    assert "degradations" in state
    assert isinstance(state["degradations"], list)
    assert len(state["degradations"]) == 1
    entry = state["degradations"][0]
    assert entry["step"] == "collect_subtitles"
    assert entry["status"] == "skipped"
    assert entry["reason"] == "empty"


def test_execute_step_uses_cache_hit_without_calling_step_func(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    step_executor._write_step_cache(
        cache_info,
        StepExecution(status="succeeded", output={"cached": True}, state_updates={"from_cache": 1}),
    )
    called = {"count": 0}

    async def _should_not_run(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_should_not_run,
        )
    )

    assert called["count"] == 0
    assert result["status"] == "skipped"
    assert result["reason"] == "cache_hit"
    assert result["cache_meta"] == {
        "source": "cache_hit",
        "cache_key": cache_info["cache_key"],
        "signature": cache_info["signature"],
        "version": cache_info["version"],
        "cached_at": result["cache_meta"]["cached_at"],
    }
    assert result["retry_meta"] == {
        "attempts": 0,
        "retries_used": 0,
        "retries_configured": 0,
        "classification": None,
        "strategy": "cache",
        "resume_hint": False,
    }
    assert result["cache_meta"]["cached_at"]
    assert len(sqlite_store.checkpoints) == 1


def test_execute_step_resume_hint_recovers_checkpoint_payload(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    sqlite_store.latest_step_run = {
        "result_json": json.dumps(
            StepExecution(
                status="succeeded", output={"checkpoint": True}, state_updates={"k": "v"}
            ).to_record()
        )
    }
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")

    async def _not_expected(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        raise AssertionError("step_func should not run when checkpoint can be recovered")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_not_expected,
            resume_hint=True,
        )
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "checkpoint_recovered"
    assert result["cache_meta"] == {
        "source": "checkpoint",
        "cache_key": cache_info["cache_key"],
        "signature": cache_info["signature"],
        "version": cache_info["version"],
    }
    assert result["retry_meta"] == {
        "attempts": 0,
        "retries_used": 0,
        "retries_configured": 0,
        "classification": None,
        "strategy": "checkpoint",
        "resume_hint": True,
    }
    assert state["k"] == "v"
    assert len(sqlite_store.latest_step_queries) == 1
    latest_query = sqlite_store.latest_step_queries[0]
    assert latest_query["job_id"] == ctx.job_id
    assert latest_query["step_name"] == "fetch_metadata"
    assert latest_query["status"] == "succeeded"
    assert latest_query["cache_key"] == str(cache_info["cache_key"])
    assert sqlite_store.finished[0]["status"] == "skipped"
    assert sqlite_store.finished[0]["error_payload"]["reason"] == "checkpoint_recovered"
    assert (
        sqlite_store.finished[0]["result_payload"]["cache_meta"]["version"] == cache_info["version"]
    )
    assert sqlite_store.checkpoints[0]["payload"]["reason"] == "checkpoint_recovered"
    assert sqlite_store.checkpoints[0]["payload"]["error_kind"] is None
    assert isinstance(sqlite_store.checkpoints[0]["payload"]["cache_key"], str)


def test_execute_step_resume_hint_invalid_checkpoint_payload_falls_back_to_live_step(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    sqlite_store.latest_step_run = {"result_json": "{invalid-json"}
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    called = {"count": 0}

    async def _step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded", state_updates={"ran_live": True})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_step,
            resume_hint=True,
        )
    )

    assert called["count"] == 1
    assert result["status"] == "succeeded"
    assert result["retry_meta"]["strategy"] == "retry_wrapper"
    assert result["retry_meta"]["resume_hint"] is True
    assert result["retry_meta"]["attempts"] == 1
    assert state["ran_live"] is True
    assert sqlite_store.finished[0]["status"] == "succeeded"
    assert sqlite_store.checkpoints[0]["payload"]["status"] == "succeeded"
    assert sqlite_store.checkpoints[0]["payload"]["reason"] is None
    assert sqlite_store.checkpoints[0]["payload"]["error_kind"] is None
    assert len(sqlite_store.latest_step_queries) == 1


def test_execute_step_resume_hint_non_string_checkpoint_payload_falls_back_to_live_step(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    sqlite_store.latest_step_run = {"result_json": {"not": "a string"}}
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    called = {"count": 0}

    async def _step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded", state_updates={"ran_live_non_string": True})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_step,
            resume_hint=True,
        )
    )

    assert called["count"] == 1
    assert result["status"] == "succeeded"
    assert result["retry_meta"]["strategy"] == "retry_wrapper"
    assert result["retry_meta"]["resume_hint"] is True
    assert state["ran_live_non_string"] is True
    assert len(sqlite_store.latest_step_queries) == 1


def test_execute_step_resume_hint_checkpoint_failed_status_falls_back_to_live_step(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    sqlite_store.latest_step_run = {
        "result_json": json.dumps(
            StepExecution(status="failed", reason="old_failure", error="old_error").to_record()
        )
    }
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    called = {"count": 0}
    observed: dict[str, Any] = {}

    async def _step(live_ctx: PipelineContext, live_state: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        observed["ctx"] = live_ctx
        observed["state"] = live_state
        return StepExecution(status="succeeded", state_updates={"ran_live_failed_checkpoint": True})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_step,
            resume_hint=True,
        )
    )

    assert called["count"] == 1
    assert observed == {"ctx": ctx, "state": state}
    assert result["status"] == "succeeded"
    assert result["retry_meta"]["strategy"] == "retry_wrapper"
    assert result["retry_meta"]["resume_hint"] is True
    assert result["retry_meta"]["retries_configured"] == 0
    assert state["ran_live_failed_checkpoint"] is True
    assert len(sqlite_store.latest_step_queries) == 1


def test_execute_step_mode_matrix_skip_is_not_degradation_and_keeps_skip_reason(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="download_media",
            step_func=step_executor.build_mode_skip_step("download_media", "text_only"),
            force_run=True,
        )
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "mode_matrix_skip"
    assert result["retry_meta"]["strategy"] == "retry_wrapper"
    assert result["retry_meta"]["attempts"] == 1
    assert state["degradations"] == []
    assert sqlite_store.finished[0]["status"] == "skipped"
    assert sqlite_store.finished[0]["error_payload"]["reason"] == "mode_matrix_skip"
    assert sqlite_store.checkpoints[0]["payload"]["status"] == "skipped"
    assert sqlite_store.checkpoints[0]["payload"]["reason"] == "mode_matrix_skip"


def test_execute_step_retries_then_succeeds_and_writes_cache(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(step_executor.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(step_executor, "retry_delay_seconds", lambda _policy, _retries: 0.2)

    async def _flaky_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return StepExecution(status="failed", reason="timeout", error="timeout")
        return StepExecution(status="succeeded", state_updates={"done": True})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_flaky_step,
            force_run=True,
        )
    )

    assert result["status"] == "succeeded"
    assert result["retry_meta"]["attempts"] == 2
    assert sleep_calls == [0.2]
    assert state["done"] is True
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    assert cache_info["cache_path"].exists()
    assert cache_info["legacy_path"].exists()


def test_execute_step_retry_delay_receives_monotonic_retry_index(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    retry_indexes: list[int] = []

    async def _fake_sleep(_delay: float) -> None:
        return None

    def _fake_build_retry_policy(
        _settings: Settings,
        *,
        step_name: str,
        llm_policy: dict[str, Any] | None,
    ) -> dict[str, dict[str, int]]:
        assert step_name == "fetch_metadata"
        assert llm_policy is None
        return {"fatal": {"retries": 2, "backoff": 0, "max_backoff": 0}}

    def _fake_retry_delay_seconds(_policy: dict[str, int], retries_used: int) -> float:
        retry_indexes.append(retries_used)
        if retry_indexes != list(range(len(retry_indexes))):
            raise AssertionError(f"non_monotonic_retry_indexes:{retry_indexes}")
        return 0.0

    monkeypatch.setattr(step_executor.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(step_executor, "build_retry_policy", _fake_build_retry_policy)
    monkeypatch.setattr(step_executor, "classify_error", lambda *_args, **_kwargs: "fatal")
    monkeypatch.setattr(step_executor, "retry_delay_seconds", _fake_retry_delay_seconds)

    async def _always_fail(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="failed", reason="boom", error="boom")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_always_fail,
            force_run=True,
        )
    )

    assert retry_indexes == [0, 1]
    assert result["status"] == "failed"
    assert result["retry_meta"]["attempts"] == 3
    assert result["retry_meta"]["retries_used"] == 2


def test_execute_step_sets_fatal_error_and_degradation_for_failed_critical(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}

    def _invalid_result(_: PipelineContext, __: dict[str, Any]) -> dict[str, str]:
        return {"bad": "payload"}

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_invalid_result,
            critical=True,
            force_run=True,
        )
    )

    assert result["status"] == "failed"
    assert result["reason"] is None
    assert result["error"] == "invalid_step_result:fetch_metadata"
    assert result["degraded"] is True
    assert result["error_kind"] == "fatal"
    assert result["retry_meta"]["classification"] == "fatal"
    assert state["fatal_error"] == "fetch_metadata:invalid_step_result:fetch_metadata"
    assert len(state["degradations"]) == 1
    assert state["degradations"][0]["status"] == "failed"
    assert state["degradations"][0]["reason"] is None
    assert state["degradations"][0]["error"] == "invalid_step_result:fetch_metadata"
    assert sqlite_store.finished[0]["error_payload"] == {
        "reason": "step_failed",
        "error": "invalid_step_result:fetch_metadata",
        "error_kind": "fatal",
        "retry_meta": result["retry_meta"],
    }
    assert sqlite_store.finished[0]["result_payload"]["status"] == "failed"
    assert sqlite_store.finished[0]["result_payload"]["degraded"] is True
    assert sqlite_store.checkpoints == []

    sqlite_store_reason_only = _FakeSQLiteStore()
    ctx_reason_only = _make_ctx(tmp_path / "reason-only", sqlite_store=sqlite_store_reason_only)
    state_reason_only: dict[str, Any] = {"steps": {}, "degradations": []}

    async def _reason_only(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="failed", reason="reason_only_failure")

    result_reason_only = asyncio.run(
        step_executor.execute_step(
            ctx_reason_only,
            state_reason_only,
            step_name="fetch_metadata",
            step_func=_reason_only,
            critical=True,
            force_run=True,
        )
    )

    assert result_reason_only["status"] == "failed"
    assert state_reason_only["fatal_error"] == "fetch_metadata:reason_only_failure"

    sqlite_store_blank = _FakeSQLiteStore()
    ctx_blank = _make_ctx(tmp_path / "blank", sqlite_store=sqlite_store_blank)
    state_blank: dict[str, Any] = {"steps": {}, "degradations": []}

    async def _blank_failure(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="failed")

    result_blank = asyncio.run(
        step_executor.execute_step(
            ctx_blank,
            state_blank,
            step_name="fetch_metadata",
            step_func=_blank_failure,
            critical=True,
            force_run=True,
        )
    )

    assert result_blank["status"] == "failed"
    assert state_blank["fatal_error"] == "fetch_metadata:failed"


def test_execute_step_unhandled_exception_uses_failure_contract(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}

    async def _boom(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        raise RuntimeError("boom")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_boom,
            force_run=True,
        )
    )

    assert result["status"] == "failed"
    assert result["reason"] == "unhandled_exception"
    assert result["error"] == "unhandled_exception:boom"
    assert result["degraded"] is True
    assert result["error_kind"] == "fatal"
    assert result["retry_meta"]["classification"] == "fatal"
    assert result["retry_meta"]["history"] == ["fatal"]
    assert state["degradations"][0]["reason"] == "unhandled_exception"
    assert state["degradations"][0]["error"] == "unhandled_exception:boom"
    assert sqlite_store.finished[0]["error_payload"] == {
        "reason": "unhandled_exception",
        "error": "unhandled_exception:boom",
        "error_kind": "fatal",
        "retry_meta": result["retry_meta"],
    }
    assert sqlite_store.finished[0]["result_payload"]["status"] == "failed"
    assert sqlite_store.checkpoints == []


def test_execute_step_llm_hard_failure_does_not_append_degradation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    captured: dict[str, Any] = {}

    def _fake_retry_policy(
        _settings: Settings, *, step_name: str, llm_policy: dict[str, Any] | None
    ) -> dict[str, dict[str, int]]:
        captured["step_name"] = step_name
        captured["llm_policy"] = dict(llm_policy or {})
        return {"fatal": {"retries": 0}, "transient": {"retries": 0}}

    monkeypatch.setattr(step_executor, "build_retry_policy", _fake_retry_policy)
    monkeypatch.setattr(step_executor, "retry_delay_seconds", lambda _policy, _retries: 0.0)

    async def _llm_fail(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="failed", reason="llm_failed", error="provider_error")

    scenarios = [
        (
            "llm_outline",
            {"steps": {}, "degradations": [], "llm_policy": {"hard_required": True}},
            [],
        ),
        ("llm_outline", {"steps": {}, "degradations": []}, []),
        ("llm_outline", {"steps": {}, "degradations": [], "llm_policy": {}}, []),
        (
            "llm_outline",
            {"steps": {}, "degradations": [], "llm_policy": {"hard_required": False}},
            [
                {
                    "step": "llm_outline",
                    "status": "failed",
                    "reason": "llm_failed",
                    "error": "provider_error",
                    "error_kind": "transient",
                }
            ],
        ),
        (
            "llm_digest",
            {"steps": {}, "degradations": [], "llm_policy": {"hard_required": True}},
            [],
        ),
    ]

    for step_name, state, expected_degradations in scenarios:
        sqlite_store = _FakeSQLiteStore()
        ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
        result = asyncio.run(
            asyncio.wait_for(
                step_executor.execute_step(
                    ctx,
                    state,
                    step_name=step_name,
                    step_func=_llm_fail,
                    force_run=True,
                ),
                timeout=0.5,
            )
        )

        assert result["status"] == "failed"
        assert result["reason"] == "llm_failed"
        assert result["error"] == "provider_error"
        if expected_degradations:
            assert len(state["degradations"]) == 1
            degradation = state["degradations"][0]
            assert degradation["step"] == step_name
            assert degradation["status"] == "failed"
            assert degradation["reason"] == "llm_failed"
            assert degradation["error"] == "provider_error"
            assert degradation["error_kind"] == "transient"
        else:
            assert state["degradations"] == []
        assert sqlite_store.checkpoints == []
        assert captured["step_name"] == step_name
        assert captured["llm_policy"] == dict(state.get("llm_policy") or {})


def test_execute_step_llm_hard_required_defaults_true_when_policy_missing_or_empty(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    scenarios = [
        ("missing", {"steps": {}, "degradations": []}),
        ("empty", {"steps": {}, "degradations": [], "llm_policy": {}}),
    ]

    monkeypatch.setattr(step_executor, "retry_delay_seconds", lambda _policy, _retries: 0.0)

    for label, state in scenarios:
        sqlite_store = _FakeSQLiteStore()
        ctx = _make_ctx(tmp_path / label, sqlite_store=sqlite_store)

        async def _llm_fail(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
            return StepExecution(status="failed", reason="llm_failed", error="provider_error")

        result = asyncio.run(
            asyncio.wait_for(
                step_executor.execute_step(
                    ctx,
                    state,
                    step_name="llm_outline",
                    step_func=_llm_fail,
                    force_run=True,
                ),
                timeout=0.5,
            )
        )

        assert result["status"] == "failed"
        assert result["reason"] == "llm_failed"
        assert result["error"] == "provider_error"
        assert result["error_kind"] == "transient"
        assert result["retry_meta"]["classification"] == "transient"
        assert state["degradations"] == []
        assert sqlite_store.checkpoints == []


def test_execute_step_marks_custom_skips_as_degradation(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state: dict[str, Any] = {"steps": {}, "degradations": []}

    async def _skip_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="skipped", reason="custom_skip_reason")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_skip_step,
            force_run=True,
        )
    )

    assert result["status"] == "skipped"
    assert len(state["degradations"]) == 1
    assert state["degradations"][0]["reason"] == "custom_skip_reason"


def test_execute_step_cache_hit_skip_is_not_degradation(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    step_executor._write_step_cache(
        cache_info,
        StepExecution(status="succeeded", state_updates={"from_cache": "ok"}),
    )
    called = {"count": 0}

    async def _should_not_run(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_should_not_run,
        )
    )

    assert called["count"] == 0
    assert result["status"] == "skipped"
    assert result["reason"] == "cache_hit"
    assert state["degradations"] == []
    assert sqlite_store.checkpoints[0]["job_id"] == ctx.job_id
    assert sqlite_store.checkpoints[0]["payload"]["status"] == "skipped"
    assert sqlite_store.checkpoints[0]["payload"]["reason"] == "cache_hit"
    assert sqlite_store.finished[0]["error_payload"]["reason"] == "cache_hit"


def test_execute_step_failed_noncritical_appends_degradation_without_checkpoint(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    monkeypatch.setattr(step_executor, "retry_delay_seconds", lambda _policy, _retries: 0.0)

    async def _fail_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(
            status="failed",
            reason="network_flaky",
            error="timeout",
            error_kind="transient",
            cache_meta={"source": "none"},
        )

    result = asyncio.run(
        asyncio.wait_for(
            step_executor.execute_step(
                ctx,
                state,
                step_name="fetch_metadata",
                step_func=_fail_step,
                critical=False,
                force_run=True,
            ),
            timeout=0.5,
        )
    )

    assert result["status"] == "failed"
    assert len(state["degradations"]) == 1
    assert state["degradations"][0]["status"] == "failed"
    assert state["degradations"][0]["reason"] == "network_flaky"
    assert state["degradations"][0]["error"] == "timeout"
    assert state["degradations"][0]["error_kind"] == "transient"
    assert state["degradations"][0]["retry_meta"] == result["retry_meta"]
    assert state["degradations"][0]["cache_meta"] == {"source": "none"}
    assert sqlite_store.finished[0]["error_payload"]["reason"] == "network_flaky"
    assert sqlite_store.finished[0]["error_payload"]["error"] == "timeout"
    assert sqlite_store.finished[0]["error_payload"]["error_kind"] == "transient"
    assert sqlite_store.finished[0]["result_payload"]["status"] == "failed"
    assert sqlite_store.finished[0]["result_payload"]["reason"] == "network_flaky"
    assert sqlite_store.finished[0]["retry_meta"]["strategy"] == "retry_wrapper"
    assert sqlite_store.checkpoints == []
    assert "fatal_error" not in state


def test_execute_step_success_writes_cache_meta_and_checkpoint(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"degradations": []}
    captured: dict[str, Any] = {}

    def _capture_write(cache_info: dict[str, Any], execution: StepExecution) -> None:
        captured["cache_info"] = dict(cache_info)
        captured["cache_meta"] = dict(execution.cache_meta)

    monkeypatch.setattr(step_executor, "_write_step_cache", _capture_write)

    async def _ok_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(
            status="succeeded",
            output={"ok": True},
            state_updates={"done": True},
            cache_meta={"preexisting": "keep"},
        )

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_ok_step,
            force_run=True,
        )
    )

    assert result["status"] == "succeeded"
    assert state["done"] is True
    assert state["steps"]["fetch_metadata"]["status"] == "succeeded"
    assert sqlite_store.checkpoints[0]["job_id"] == ctx.job_id
    assert sqlite_store.checkpoints[0]["last_completed_step"] == "fetch_metadata"
    assert sqlite_store.checkpoints[0]["payload"]["status"] == "succeeded"
    assert sqlite_store.checkpoints[0]["payload"]["reason"] is None
    assert sqlite_store.checkpoints[0]["payload"]["error_kind"] is None
    assert sqlite_store.finished[0]["result_payload"]["status"] == "succeeded"
    assert sqlite_store.finished[0]["result_payload"]["output"] == {"ok": True}
    assert sqlite_store.finished[0]["error_payload"] is None
    assert sqlite_store.finished[0]["retry_meta"]["strategy"] == "retry_wrapper"
    assert sqlite_store.finished[0]["retry_meta"]["attempts"] == 1
    assert sqlite_store.finished[0]["retry_meta"]["retries_used"] == 0
    assert captured["cache_meta"]["preexisting"] == "keep"
    assert captured["cache_meta"]["cache_key"] == captured["cache_info"]["cache_key"]
    assert captured["cache_meta"]["signature"] == captured["cache_info"]["signature"]
    assert captured["cache_meta"]["version"] == captured["cache_info"]["version"]


def test_execute_step_default_critical_false_does_not_set_fatal_error(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    signature = inspect.signature(step_executor.execute_step)
    assert signature.parameters["critical"].default is step_executor._DEFAULT_ARG_UNSET

    async def _fail_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="failed", reason="failed_by_default", error="boom")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_fail_step,
            force_run=True,
        )
    )

    assert result["status"] == "failed"
    assert result["reason"] == "failed_by_default"
    assert result["error"] == "boom"
    assert result["retry_meta"]["strategy"] == "retry_wrapper"
    assert result["retry_meta"]["attempts"] == 1
    assert state["steps"]["fetch_metadata"]["status"] == "failed"
    assert "fatal_error" not in state
    assert state["steps"]["fetch_metadata"]["reason"] == "failed_by_default"
    assert state["steps"]["fetch_metadata"]["retry_meta"]["classification"] == "fatal"
    assert state["degradations"][0]["reason"] == "failed_by_default"
    assert state["degradations"][0]["error"] == "boom"
    assert "fatal_error" not in state


def test_execute_step_default_resume_hint_false_executes_step_instead_of_checkpoint(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    sqlite_store.latest_step_run = {
        "result_json": json.dumps(
            StepExecution(status="succeeded", state_updates={"from_checkpoint": True}).to_record()
        )
    }
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    called = {"count": 0}
    observed: dict[str, Any] = {}

    async def _step(live_ctx: PipelineContext, live_state: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        observed["ctx"] = live_ctx
        observed["state"] = live_state
        return StepExecution(status="succeeded", state_updates={"ran_live_step": True})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_step,
        )
    )

    assert called["count"] == 1
    assert observed == {"ctx": ctx, "state": state}
    assert result["status"] == "succeeded"
    assert result["retry_meta"]["retries_configured"] == 0
    assert state["ran_live_step"] is True
    assert "from_checkpoint" not in state


def test_execute_step_default_force_run_false_uses_cache_hit(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    step_executor._write_step_cache(
        cache_info,
        StepExecution(status="succeeded", output={"cache": True}, state_updates={"from_cache": 1}),
    )
    called = {"count": 0}

    async def _should_not_run(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_should_not_run,
        )
    )

    assert called["count"] == 0
    assert result["status"] == "skipped"
    assert result["reason"] == "cache_hit"
    assert state["from_cache"] == 1


def test_execute_step_force_run_true_bypasses_cache_hit_and_runs_live_step(tmp_path: Path) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    step_executor._write_step_cache(
        cache_info,
        StepExecution(
            status="succeeded",
            output={"cache": True},
            state_updates={"from_cache": 1},
        ),
    )
    called = {"count": 0}

    async def _run_live_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded", state_updates={"from_live": 2})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_run_live_step,
            force_run=True,
        )
    )

    assert called["count"] == 1
    assert result["status"] == "succeeded"
    assert result["reason"] is None
    assert result["retry_meta"]["strategy"] == "retry_wrapper"
    assert "from_cache" not in state
    assert state["from_live"] == 2


def test_execute_step_cache_hit_with_resume_hint_true_uses_checkpoint_recovered_reason(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    cache_info = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")
    step_executor._write_step_cache(
        cache_info,
        StepExecution(status="succeeded", state_updates={"from_cache": "ok"}),
    )

    async def _should_not_run(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        raise AssertionError("cache-hit path should not execute live step")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_should_not_run,
            resume_hint=True,
        )
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "checkpoint_recovered"
    assert result["cache_meta"]["source"] == "cache_hit"
    assert result["retry_meta"]["strategy"] == "cache"
    assert result["retry_meta"]["resume_hint"] is True
    assert sqlite_store.checkpoints[0]["payload"]["reason"] == "checkpoint_recovered"


def test_execute_step_cache_hit_fallback_uses_cache_hit_when_cache_reason_missing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    called = {"count": 0}

    def _fake_load_step_execution_from_cache(_: dict[str, Any]) -> tuple[StepExecution, None]:
        return (
            StepExecution(status="succeeded", state_updates={"from_cache": "fallback"}),
            None,
        )

    monkeypatch.setattr(
        step_executor,
        "_load_step_execution_from_cache",
        _fake_load_step_execution_from_cache,
    )

    async def _should_not_run(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        called["count"] += 1
        return StepExecution(status="succeeded")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_should_not_run,
        )
    )

    assert called["count"] == 0
    assert result["status"] == "skipped"
    assert result["reason"] == "cache_hit"
    assert result["cache_meta"]["source"] == "cache_hit"
    assert result["retry_meta"]["strategy"] == "cache"
    assert sqlite_store.finished[0]["error_payload"]["reason"] == "cache_hit"
    assert sqlite_store.checkpoints[0]["payload"]["reason"] == "cache_hit"


def test_execute_step_default_kwdefaults_contract() -> None:
    defaults = step_executor.execute_step.__kwdefaults__ or {}

    assert defaults["critical"] is step_executor._DEFAULT_ARG_UNSET
    assert defaults["resume_hint"] is step_executor._DEFAULT_ARG_UNSET
    assert defaults["force_run"] is step_executor._DEFAULT_ARG_UNSET


def test_execute_step_marks_running_and_finished_payload_contract_on_success(
    tmp_path: Path,
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    expected_cache_key = step_executor.build_step_cache_info(ctx, state, "fetch_metadata")[
        "cache_key"
    ]

    async def _ok_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="succeeded", output={"ok": True}, state_updates={"done": True})

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_ok_step,
            force_run=True,
        )
    )

    assert result["status"] == "succeeded"
    assert state["done"] is True

    assert len(sqlite_store.started) == 1
    started_payload = sqlite_store.started[0]
    assert set(started_payload) == {"job_id", "step_name", "attempt", "cache_key"}
    assert started_payload["job_id"] == ctx.job_id
    assert started_payload["step_name"] == "fetch_metadata"
    assert started_payload["attempt"] == ctx.attempt
    assert started_payload["cache_key"] == expected_cache_key

    assert len(sqlite_store.finished) == 1
    finished_payload = sqlite_store.finished[0]
    assert finished_payload["job_id"] == ctx.job_id
    assert finished_payload["step_name"] == "fetch_metadata"
    assert finished_payload["attempt"] == ctx.attempt
    assert finished_payload["status"] == "succeeded"
    assert finished_payload["error_payload"] is None
    assert finished_payload["error_kind"] is None
    assert finished_payload["retry_meta"]["strategy"] == "retry_wrapper"
    assert finished_payload["retry_meta"]["attempts"] == 1
    assert finished_payload["retry_meta"]["resume_hint"] is False
    assert finished_payload["cache_key"] == expected_cache_key
    assert finished_payload["result_payload"]["status"] == "succeeded"
    assert finished_payload["result_payload"]["output"] == {"ok": True}
    assert finished_payload["result_payload"]["retry_meta"]["strategy"] == "retry_wrapper"


def test_execute_step_success_creates_steps_mapping_when_missing(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state: dict[str, Any] = {"degradations": []}

    async def _ok_step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="succeeded", output={"created": True})

    step_record = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="fetch_metadata",
            step_func=_ok_step,
            force_run=True,
        )
    )

    assert "steps" in state
    assert state["steps"]["fetch_metadata"] == step_record
    assert state["steps"]["fetch_metadata"]["status"] == "succeeded"
    assert state["steps"]["fetch_metadata"]["output"] == {"created": True}


def test_execute_step_passes_llm_policy_to_retry_builder_for_llm_digest(
    monkeypatch: Any, tmp_path: Path
) -> None:
    ctx = _make_ctx(tmp_path)
    state: dict[str, Any] = {
        "steps": {},
        "degradations": [],
        "llm_policy": {"hard_required": False, "max_retries": 7},
    }
    captured: dict[str, Any] = {}

    def _fake_build_retry_policy(
        settings: Any,
        *,
        step_name: str,
        llm_policy: dict[str, Any] | None,
    ) -> dict[str, dict[str, float | int]]:
        captured["settings"] = settings
        captured["step_name"] = step_name
        captured["llm_policy"] = dict(llm_policy or {})
        return {
            "transient": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
            "rate_limit": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
            "auth": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
            "fatal": {"retries": 0, "backoff": 0.0, "max_backoff": 0.0},
        }

    monkeypatch.setattr(step_executor, "build_retry_policy", _fake_build_retry_policy)

    async def _step(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="succeeded")

    result = asyncio.run(
        step_executor.execute_step(
            ctx,
            state,
            step_name="llm_digest",
            step_func=_step,
            force_run=True,
        )
    )

    assert result["status"] == "succeeded"
    assert captured["step_name"] == "llm_digest"
    assert captured["settings"] is ctx.settings
    assert captured["llm_policy"] == {"hard_required": False, "max_retries": 7}


def test_execute_step_classifies_failures_with_exact_reason_error_and_fatal_fallback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}
    classify_calls: list[tuple[str | None, str | None]] = []
    sleep_calls: list[float] = []

    class _SentinelPolicy(dict[str, int]):
        def get(self, key: object, default: object = None) -> object:
            if key == "retries" and default == 0:
                return 2
            if key == "retries" and default is None:
                return 52
            if key is None:
                return 62
            if key == "XXretriesXX":
                return 72
            if key == "RETRIES":
                return 82
            return super().get(key, default)

    def _fake_classify_error(reason: str | None, error: str | None) -> str:
        classify_calls.append((reason, error))
        return "mystery" if (reason, error) == ("boom_reason", "boom_error") else "fatal"

    def _fake_build_retry_policy(
        _settings: Settings,
        *,
        step_name: str,
        llm_policy: dict[str, Any] | None,
    ) -> dict[str, dict[str, int]]:
        assert step_name == "fetch_metadata"
        assert llm_policy is None
        return {"fatal": _SentinelPolicy()}

    monkeypatch.setattr(step_executor, "classify_error", _fake_classify_error)
    monkeypatch.setattr(step_executor, "build_retry_policy", _fake_build_retry_policy)
    monkeypatch.setattr(step_executor, "retry_delay_seconds", lambda _policy, _retries: 0.0)

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(step_executor.asyncio, "sleep", _fake_sleep)

    async def _fail(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(status="failed", reason="boom_reason", error="boom_error")

    result = asyncio.run(
        asyncio.wait_for(
            step_executor.execute_step(
                ctx,
                state,
                step_name="fetch_metadata",
                step_func=_fail,
                force_run=True,
            ),
            timeout=0.5,
        )
    )

    assert classify_calls == [("boom_reason", "boom_error")] * 3
    assert result["status"] == "failed"
    assert result["reason"] == "boom_reason"
    assert result["error"] == "boom_error"
    assert result["error_kind"] == "mystery"
    assert result["retry_meta"]["classification"] == "mystery"
    assert result["retry_meta"]["history"] == ["mystery"] * 3
    assert result["retry_meta"]["retries_configured"] == 2
    assert result["retry_meta"]["attempts"] == 3
    assert result["retry_meta"]["retries_used"] == 2
    assert result["retry_meta"]["delays_seconds"] == [0.0, 0.0]
    assert sleep_calls == []
    assert sqlite_store.finished[0]["error_kind"] == "mystery"
    assert sqlite_store.finished[0]["retry_meta"]["history"] == ["mystery"] * 3
    assert sqlite_store.finished[0]["retry_meta"]["delays_seconds"] == [0.0, 0.0]


def test_execute_step_retry_budget_does_not_hang_even_when_step_keeps_failing(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sqlite_store = _FakeSQLiteStore()
    ctx = _make_ctx(tmp_path, sqlite_store=sqlite_store)
    state: dict[str, Any] = {"steps": {}, "degradations": []}

    def _fake_build_retry_policy(
        _settings: Settings,
        *,
        step_name: str,
        llm_policy: dict[str, Any] | None,
    ) -> dict[str, dict[str, int]]:
        assert step_name == "fetch_metadata"
        assert llm_policy is None
        return {"fatal": {"retries": 0}, "transient": {"retries": 2}}

    monkeypatch.setattr(step_executor, "build_retry_policy", _fake_build_retry_policy)
    monkeypatch.setattr(step_executor, "retry_delay_seconds", lambda _policy, _retries: 0.0)

    async def _always_fail(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(
            status="failed", reason="network_flaky", error="timeout", error_kind="transient"
        )

    result = asyncio.run(
        asyncio.wait_for(
            step_executor.execute_step(
                ctx,
                state,
                step_name="fetch_metadata",
                step_func=_always_fail,
                force_run=True,
            ),
            timeout=0.5,
        )
    )

    assert result["status"] == "failed"
    assert result["error_kind"] == "transient"
    assert result["retry_meta"]["attempts"] == 3
    assert result["retry_meta"]["retries_used"] == 2
    assert result["retry_meta"]["retries_configured"] == 2
    assert result["retry_meta"]["history"] == ["transient", "transient", "transient"]


def test_run_command_once_handles_error_modes(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        step_executor.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )
    missing = step_executor.run_command_once(["missing-binary"], timeout_seconds=1)
    assert missing.ok is False
    assert missing.returncode is None
    assert missing.stdout == ""
    assert missing.stderr == ""
    assert missing.reason == "binary_not_found"

    def _raise_timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["sleep", "1"], timeout=1)

    monkeypatch.setattr(step_executor.subprocess, "run", _raise_timeout)
    timeout = step_executor.run_command_once(["sleep", "1"], timeout_seconds=1)
    assert timeout.ok is False
    assert timeout.returncode is None
    assert timeout.stdout == ""
    assert timeout.stderr == ""
    assert timeout.reason == "timeout"

    monkeypatch.setattr(
        step_executor.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["cmd"],
            returncode=2,
            stdout="",
            stderr="boom",
        ),
    )
    failed = step_executor.run_command_once(["cmd"], timeout_seconds=1)
    assert failed.ok is False
    assert failed.returncode == 2
    assert failed.stdout == ""
    assert failed.stderr == "boom"
    assert failed.reason == "non_zero_exit"


def test_run_command_once_success_preserves_completed_process_fields(monkeypatch: Any) -> None:
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

    assert called == {
        "args": (["echo", "ok"],),
        "kwargs": {
            "capture_output": True,
            "text": True,
            "timeout": 7,
            "check": False,
        },
    }
    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout == "ok\n"
    assert result.stderr == ""
    assert result.reason is None


def test_run_command_binary_missing_and_terminate_variants(
    monkeypatch: Any, tmp_path: Path
) -> None:
    ctx = _make_ctx(tmp_path)

    async def _raise_missing(*_args: Any, **_kwargs: Any) -> Any:
        raise FileNotFoundError

    monkeypatch.setattr(step_executor.asyncio, "create_subprocess_exec", _raise_missing)
    result = asyncio.run(step_executor.run_command(ctx, ["missing-binary"]))
    assert result.reason == "binary_not_found"

    class _Process:
        def __init__(self, *, pid: int | None = 123) -> None:
            self.returncode: int | None = None
            self.pid = pid
            self.terminate_called = False
            self.kill_called = False
            self.wait_calls = 0

        async def wait(self) -> int:
            self.wait_calls += 1
            self.returncode = 0
            return 0

        def terminate(self) -> None:
            self.terminate_called = True

        def kill(self) -> None:
            self.kill_called = True
            self.returncode = -9

    proc_done = _Process()
    proc_done.returncode = 0
    asyncio.run(step_executor._terminate_subprocess(proc_done))
    assert proc_done.wait_calls == 0

    proc_timeout = _Process(pid=999)

    async def _raise_wait_for(_awaitable: Any, timeout: float) -> Any:
        close_fn = getattr(_awaitable, "close", None)
        if callable(close_fn):
            close_fn()
        raise TimeoutError

    monkeypatch.setattr(step_executor.asyncio, "wait_for", _raise_wait_for)
    asyncio.run(step_executor._terminate_subprocess(proc_timeout))
    assert proc_timeout.terminate_called is True
    assert proc_timeout.kill_called is True
    assert proc_timeout.wait_calls == 1

    proc_fallback = _Process(pid=None)
    asyncio.run(step_executor._terminate_subprocess(proc_fallback))
    assert proc_fallback.terminate_called is True
    assert proc_fallback.kill_called is True
