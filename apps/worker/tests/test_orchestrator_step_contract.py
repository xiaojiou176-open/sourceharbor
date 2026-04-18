from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from apps.worker.worker.config import Settings
from apps.worker.worker.pipeline import orchestrator
from apps.worker.worker.pipeline.types import PIPELINE_STEPS, StepExecution


class _FakeSQLiteStore:
    def __init__(self, checkpoint: dict[str, Any] | None = None) -> None:
        self._checkpoint = checkpoint
        self.last_checkpoint_job_id: str | None = None

    def get_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        self.last_checkpoint_job_id = job_id
        return self._checkpoint


class _FakePGStore:
    def __init__(self, record: dict[str, Any] | None = None) -> None:
        self._record = record

    def get_job_with_video(self, *, job_id: str) -> dict[str, Any]:
        if self._record is not None:
            return dict(self._record)
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
    )


def test_orchestrator_default_handlers_match_pipeline_steps(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-step-contract",
            attempt=1,
            mode="full",
        )
    )

    assert seen_steps == PIPELINE_STEPS
    assert list(result["steps"].keys()) == PIPELINE_STEPS


def test_orchestrator_import_chain_uses_single_apps_namespace() -> None:
    imported_symbols = (
        orchestrator.Settings,
        orchestrator.PipelineContext,
        orchestrator.PostgresBusinessStore,
        orchestrator.SQLiteStateStore,
    )

    for symbol in imported_symbols:
        assert symbol.__module__.startswith("apps.worker.worker.")
        assert not symbol.__module__.startswith("worker.")


def test_build_context_creates_expected_directories(tmp_path: Path) -> None:
    ctx = orchestrator.build_context(
        _make_settings(tmp_path),
        _FakeSQLiteStore(),  # type: ignore[arg-type]
        _FakePGStore(),  # type: ignore[arg-type]
        job_id="job-build-context",
        attempt=2,
    )

    assert ctx.job_id == "job-build-context"
    assert ctx.attempt == 2
    assert ctx.job_record["platform"] == "youtube"
    assert ctx.work_dir.is_dir()
    assert ctx.cache_dir.is_dir()
    assert ctx.download_dir.is_dir()
    assert ctx.download_dir.name == "downloads"
    assert ctx.frames_dir.is_dir()
    assert ctx.frames_dir.name == "frames"
    assert ctx.artifacts_dir.is_dir()
    assert ctx.artifacts_dir.as_posix().endswith("/youtube/video-uid/job-build-context")


def test_build_context_falls_back_to_unknown_platform_and_video_uid(tmp_path: Path) -> None:
    ctx = orchestrator.build_context(
        _make_settings(tmp_path),
        _FakeSQLiteStore(),  # type: ignore[arg-type]
        _FakePGStore(
            record={
                "job_id": "job-build-context-unknown",
                "job_status": "running",
                "job_kind": "phase2_ingest_stub",
            }
        ),  # type: ignore[arg-type]
        job_id="job-build-context-unknown",
        attempt=3,
    )

    assert ctx.artifacts_dir.as_posix().endswith("/unknown/unknown/job-build-context-unknown")


def test_build_context_uses_requested_job_id_and_cache_directory_name(tmp_path: Path) -> None:
    requested_job_id = "job-build-context-requested"
    ctx = orchestrator.build_context(
        _make_settings(tmp_path),
        _FakeSQLiteStore(),  # type: ignore[arg-type]
        _FakePGStore(),  # type: ignore[arg-type]
        job_id=requested_job_id,
        attempt=1,
    )

    assert ctx.job_record["job_id"] == requested_job_id
    assert ctx.cache_dir.name == "cache"


def test_build_context_keeps_injected_settings_and_store_instances(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    sqlite_store = _FakeSQLiteStore()
    pg_store = _FakePGStore()
    ctx = orchestrator.build_context(
        settings,
        sqlite_store,  # type: ignore[arg-type]
        pg_store,  # type: ignore[arg-type]
        job_id="job-build-context-injected",
        attempt=9,
    )

    assert ctx.settings is settings
    assert ctx.sqlite_store is sqlite_store
    assert ctx.pg_store is pg_store


def test_resolve_llm_gate_hard_required_true_missing_steps_fails() -> None:
    llm_required, gate_passed, hard_fail_reason = orchestrator.resolve_llm_gate(
        {"fetch_metadata": {"status": "succeeded"}},
        pipeline_llm_hard_required=True,
    )

    assert llm_required is True
    assert gate_passed is False
    assert hard_fail_reason == "llm_step_missing"


def test_resolve_llm_gate_hard_required_true_matches_expected_behavior() -> None:
    step_records = {
        "llm_outline": {"status": "failed", "reason": "provider_unavailable"},
        "llm_digest": {"status": "succeeded"},
    }
    by_explicit_true = orchestrator.resolve_llm_gate(
        step_records,
        pipeline_llm_hard_required=True,
    )
    by_explicit_false = orchestrator.resolve_llm_gate(
        step_records,
        pipeline_llm_hard_required=False,
    )

    assert by_explicit_true != by_explicit_false
    assert by_explicit_true == (True, False, "provider_unavailable")


def test_resolve_llm_gate_hard_required_false_allows_failed_llm_steps() -> None:
    llm_required, gate_passed, hard_fail_reason = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "failed", "reason": "provider_unavailable"},
            "llm_digest": {"status": "failed", "reason": "provider_unavailable"},
        },
        pipeline_llm_hard_required=False,
    )

    assert llm_required is False
    assert gate_passed is True
    assert hard_fail_reason is None


def test_resolve_pipeline_status_soft_llm_failure_is_degraded() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "fetch_metadata": {"status": "succeeded"},
            "llm_outline": {"status": "failed"},
            "llm_digest": {"status": "succeeded"},
            "write_artifacts": {"status": "succeeded"},
        },
        degradations=[],
        pipeline_llm_hard_required=False,
    )

    assert status == "degraded"


def test_resolve_pipeline_status_and_llm_gate_cover_failed_and_missing_cases() -> None:
    assert (
        orchestrator.resolve_pipeline_status(
            {"fetch_metadata": {"status": "running"}},
            degradations=[],
            pipeline_llm_hard_required=True,
        )
        == "failed"
    )
    assert (
        orchestrator.resolve_pipeline_status(
            {
                "fetch_metadata": {"status": "succeeded"},
                "write_artifacts": {"status": "skipped"},
            },
            degradations=[{"step": "download_media"}],
            pipeline_llm_hard_required=True,
        )
        == "degraded"
    )

    failed_required, failed_gate, failed_reason = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "failed", "reason": "provider_unavailable"},
            "llm_digest": {"status": "succeeded"},
        },
        pipeline_llm_hard_required=True,
    )
    assert (failed_required, failed_gate, failed_reason) == (
        True,
        False,
        "provider_unavailable",
    )

    missing_required, missing_gate, missing_reason = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "running"},
        },
        pipeline_llm_hard_required=True,
    )
    assert (missing_required, missing_gate, missing_reason) == (True, False, "llm_step_missing")


def test_resolve_llm_gate_reason_priority_and_default() -> None:
    assert orchestrator.resolve_llm_gate(
        {"llm_outline": {"status": "failed", "reason": "first_reason", "error": "second_error"}},
        pipeline_llm_hard_required=True,
    ) == (True, False, "first_reason")

    assert orchestrator.resolve_llm_gate(
        {"llm_outline": {"status": "failed", "reason": "   ", "error": "second_error"}},
        pipeline_llm_hard_required=True,
    ) == (True, False, "llm_step_failed")

    assert orchestrator.resolve_llm_gate(
        {"llm_outline": {"status": "failed", "reason": "  ", "error": ""}},
        pipeline_llm_hard_required=True,
    ) == (True, False, "llm_step_failed")


def test_resolve_llm_gate_failed_without_reason_or_error_uses_default_reason() -> None:
    result = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "failed"},
            "llm_digest": {"status": "succeeded"},
        },
        pipeline_llm_hard_required=True,
    )
    assert result == (True, False, "llm_step_failed")


def test_resolve_llm_gate_accepts_succeeded_and_skipped_outcomes() -> None:
    both_succeeded = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "succeeded"},
        },
        pipeline_llm_hard_required=True,
    )
    outline_succeeded_digest_skipped = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "skipped"},
        },
        pipeline_llm_hard_required=True,
    )

    assert both_succeeded == (True, True, None)
    assert outline_succeeded_digest_skipped == (True, True, None)


def test_resolve_pipeline_status_unknown_status_fails() -> None:
    status = orchestrator.resolve_pipeline_status(
        {"fetch_metadata": {"status": "unknown_status"}},
        degradations=[],
        pipeline_llm_hard_required=True,
    )
    assert status == "failed"


def test_resolve_pipeline_status_keeps_soft_llm_flag_boolean() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "llm_outline": {"status": "failed"},
            "write_artifacts": {"status": "succeeded"},
        },
        degradations=[],
        pipeline_llm_hard_required=False,
    )
    assert status == "degraded"


def test_resolve_pipeline_status_all_success_returns_succeeded() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "fetch_metadata": {"status": "succeeded"},
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "skipped"},
            "write_artifacts": {"status": "succeeded"},
        },
        degradations=[],
        pipeline_llm_hard_required=True,
    )
    assert status == "succeeded"


def test_resolve_pipeline_status_soft_mode_with_successful_llm_steps_stays_succeeded() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "fetch_metadata": {"status": "succeeded"},
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "skipped"},
            "write_artifacts": {"status": "succeeded"},
        },
        degradations=[],
        pipeline_llm_hard_required=False,
    )
    assert status == "succeeded"


def test_resolve_pipeline_status_none_hard_required_treats_llm_failure_as_failed() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "llm_outline": {"status": "failed"},
            "write_artifacts": {"status": "succeeded"},
        },
        degradations=[],
        pipeline_llm_hard_required=None,
    )
    assert status == "failed"


def test_resolve_pipeline_status_soft_llm_digest_failure_is_degraded() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "fetch_metadata": {"status": "succeeded"},
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "failed"},
        },
        degradations=[],
        pipeline_llm_hard_required=False,
    )
    assert status == "degraded"


def test_resolve_pipeline_status_soft_llm_then_non_llm_failure_is_failed() -> None:
    status = orchestrator.resolve_pipeline_status(
        {
            "llm_outline": {"status": "failed"},
            "fetch_metadata": {"status": "failed"},
        },
        degradations=[],
        pipeline_llm_hard_required=False,
    )
    assert status == "failed"


def test_resolve_llm_gate_none_hard_required_is_still_required() -> None:
    result = orchestrator.resolve_llm_gate(
        {"llm_outline": {"status": "failed", "reason": "provider_unavailable"}},
        pipeline_llm_hard_required=None,
    )
    assert result == (True, False, "provider_unavailable")


def test_resolve_llm_gate_only_llm_digest_failure_uses_its_reason() -> None:
    result = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": "succeeded"},
            "llm_digest": {"status": "failed", "error": "digest_provider_down"},
        },
        pipeline_llm_hard_required=True,
    )
    assert result == (True, False, "digest_provider_down")


def test_resolve_llm_gate_without_llm_steps_returns_none_gate_and_reason() -> None:
    result = orchestrator.resolve_llm_gate(
        {"fetch_metadata": {"status": "succeeded"}},
        pipeline_llm_hard_required=True,
    )
    assert result == (True, False, "llm_step_missing")


def test_resolve_llm_gate_treats_blank_status_as_missing() -> None:
    result = orchestrator.resolve_llm_gate(
        {
            "llm_outline": {"status": " "},
            "llm_digest": {"status": "succeeded"},
        },
        pipeline_llm_hard_required=True,
    )
    assert result == (True, False, "llm_step_missing")


def test_normalized_step_status_contract_for_missing_and_whitespace_values() -> None:
    assert orchestrator._normalized_step_status({}) == ""
    assert orchestrator._normalized_step_status({"status": None}) == ""
    assert orchestrator._normalized_step_status({"status": "  SuCcEeDeD  "}) == "succeeded"


def test_orchestrator_with_empty_step_handlers_is_not_succeeded(tmp_path: Path) -> None:
    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-empty-steps",
            attempt=1,
            mode="full",
            step_handlers=[],
        )
    )

    assert result["steps"] == {}
    assert result["final_status"] == "failed"


def test_worker_common_schema_step_names_include_pipeline_steps() -> None:
    schema_path = (
        Path(__file__).resolve().parents[1] / "worker" / "contracts" / "common.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    step_name_def = schema.get("$defs", {}).get("StepName", {})
    step_enums = set(step_name_def.get("enum", []))

    for step in PIPELINE_STEPS:
        assert step in step_enums


def test_run_pipeline_text_only_mode_skip_and_resume_hint_rules(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    sqlite_store = _FakeSQLiteStore(checkpoint={"last_completed_step": "extract_frames"})

    async def _fake_execute_step(
        ctx: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del critical
        captured.append(
            {
                "step": step_name,
                "resume_hint": resume_hint,
                "force_run": force_run,
                "step_func_name": getattr(step_func, "__name__", "unknown"),
            }
        )
        if getattr(step_func, "__name__", "") == "_skip":
            execution = await step_func(ctx, state)
            state["steps"][step_name] = {"status": execution.status, "reason": execution.reason}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-text-only-rules",
            attempt=1,
            mode="text_only",
        )
    )

    by_step = {item["step"]: item for item in captured}
    assert by_step["fetch_metadata"]["resume_hint"] is True
    assert by_step["download_media"] == {
        "step": "download_media",
        "resume_hint": False,
        "force_run": True,
        "step_func_name": "_skip",
    }
    assert by_step["collect_subtitles"]["resume_hint"] is False
    assert by_step["collect_comments"]["resume_hint"] is True
    assert by_step["extract_frames"]["force_run"] is True
    assert by_step["llm_outline"]["resume_hint"] is False
    assert result["steps"]["download_media"]["reason"] == "mode_matrix_skip"


def test_run_pipeline_breaks_early_on_hard_required_llm_failure(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {"status": "failed", "reason": "llm_provider_unavailable"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-hard-llm-fail",
            attempt=1,
            mode="full",
        )
    )

    assert "llm_digest" not in seen_steps
    assert result["final_status"] == "failed"
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is False
    assert result["hard_fail_reason"] == "llm_provider_unavailable"
    assert result["fatal_error"] == "llm_outline:llm_provider_unavailable"


def test_run_pipeline_soft_llm_failure_does_not_break_pipeline(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {"status": "failed", "reason": "soft_provider_outage"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        pipeline_llm_hard_required=False,
    )
    result = asyncio.run(
        orchestrator.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-soft-llm-fail",
            attempt=1,
            mode="full",
        )
    )

    assert seen_steps == PIPELINE_STEPS
    assert result["final_status"] == "degraded"
    assert result["llm_required"] is False
    assert result["llm_gate_passed"] is True
    assert result["hard_fail_reason"] is None
    assert result["fatal_error"] is None


def test_run_pipeline_uses_checkpoint_payload_fallback_for_overrides(
    monkeypatch: Any, tmp_path: Path
) -> None:
    observed_overrides: list[dict[str, Any]] = []
    observed_llm_policy: list[dict[str, Any]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        observed_overrides.append(dict(state.get("overrides") or {}))
        observed_llm_policy.append(dict(state.get("llm_policy") or {}))
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)
    pg_store = _FakePGStore(
        record={
            "job_id": "job-overrides-fallback",
            "job_status": "running",
            "job_kind": "phase2_ingest_stub",
            "idempotency_key": "idem",
            "video_id": "video-id",
            "platform": "youtube",
            "video_uid": "video-uid",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Demo",
            "published_at": None,
            "overrides_json": {"llm": {"hard_required": False}},
        }
    )
    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-overrides-fallback",
            attempt=1,
            mode="full",
            overrides={},
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert observed_overrides
    assert observed_overrides[0].get("llm", {}).get("hard_required") is False
    assert observed_llm_policy[0].get("hard_required") is False
    assert result["llm_required"] is False


def test_run_pipeline_signature_mode_default_is_full_literal() -> None:
    signature = inspect.signature(orchestrator.run_pipeline)
    assert signature.parameters["mode"].default is orchestrator._DEFAULT_MODE_UNSET


def test_run_pipeline_passes_literal_auto_default_to_llm_normalizer(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    def _normalize_llm_input_mode(value: Any) -> str:
        captured["raw_llm_input_mode"] = value
        return "auto"

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    class _SettingsWithoutLlmInputMode:
        pipeline_workspace_dir = ""
        pipeline_artifact_root = ""

    settings = _SettingsWithoutLlmInputMode()
    settings.pipeline_workspace_dir = str((tmp_path / "workspace").resolve())
    settings.pipeline_artifact_root = str((tmp_path / "artifact-root").resolve())

    monkeypatch.setattr(
        orchestrator,
        "normalize_llm_input_mode",
        _normalize_llm_input_mode,
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda *_args, **_kwargs: {"top_n": 1, "replies_per_comment": 0, "sort": "hot"},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda *_args, **_kwargs: {"method": "fps", "max_frames": 1},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda *_args, **_kwargs: {"hard_required": True},
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            settings,  # type: ignore[arg-type]
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-input-literal-auto",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured["raw_llm_input_mode"] == "auto"
    assert result["llm_input_mode"] == "auto"


def test_run_pipeline_passes_build_context_inputs_through(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    original_build_context = orchestrator.build_context

    def _capturing_build_context(
        settings: Settings,
        sqlite_store: Any,
        pg_store: Any,
        *,
        job_id: str,
        attempt: int,
    ) -> orchestrator.PipelineContext:
        captured["settings"] = settings
        captured["sqlite_store"] = sqlite_store
        captured["pg_store"] = pg_store
        captured["job_id"] = job_id
        captured["attempt"] = attempt
        return original_build_context(
            settings,
            sqlite_store,
            pg_store,
            job_id=job_id,
            attempt=attempt,
        )

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    sqlite_store = _FakeSQLiteStore()
    settings = _make_settings(tmp_path)
    monkeypatch.setattr(orchestrator, "build_context", _capturing_build_context, raising=False)
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    asyncio.run(
        orchestrator.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-build-context-pass-through",
            attempt=7,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured["settings"] is settings
    assert captured["sqlite_store"] is sqlite_store
    assert captured["job_id"] == "job-build-context-pass-through"
    assert captured["attempt"] == 7


def test_run_pipeline_prefers_explicit_overrides_over_job_record_fallback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    observed: dict[str, Any] = {}
    explicit_overrides = {
        "llm": {"hard_required": False},
        "comments": {"top_n": 7},
    }

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        observed["state_overrides"] = dict(state.get("overrides") or {})
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda _settings, overrides, **_kwargs: {"from_overrides": dict(overrides)},
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    pg_store = _FakePGStore(
        record={
            "job_id": "job-explicit-overrides",
            "job_status": "running",
            "job_kind": "phase2_ingest_stub",
            "idempotency_key": "idem",
            "video_id": "video-id",
            "platform": "youtube",
            "video_uid": "video-uid",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Demo",
            "published_at": None,
            "overrides_json": {"llm": {"hard_required": True}, "comments": {"top_n": 1}},
        }
    )

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-explicit-overrides",
            attempt=1,
            overrides=explicit_overrides,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert observed["state_overrides"] == explicit_overrides
    assert result["mode"] == "full"


def test_run_pipeline_initial_state_contract_strict_keys_and_defaults(
    monkeypatch: Any, tmp_path: Path
) -> None:
    observed: dict[str, Any] = {}
    comments_policy = {"top_n": 5, "sort": "hot"}
    frame_policy = {"method": "fps", "max_frames": 3}
    llm_policy = {"hard_required": True, "provider": "gemini"}
    checkpoint = {"last_completed_step": "download_media", "payload": {"from_checkpoint": True}}

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, force_run
        observed["state"] = dict(state)
        observed["resume_hint"] = resume_hint
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda _settings, _overrides, *, platform: comments_policy | {"platform": platform},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda _settings, _overrides: dict(frame_policy),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda _settings, _overrides, **_kwargs: dict(llm_policy),
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    pg_store = _FakePGStore(
        record={
            "job_id": "job-state-contract",
            "job_status": "running",
            "job_kind": "phase2_ingest_stub",
            "idempotency_key": "idem",
            "video_id": "video-id",
            "platform": "YouTube",
            "video_uid": "u-123",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Demo State Contract",
            "published_at": "2026-01-01T00:00:00Z",
            "overrides_json": {"llm": {"hard_required": False}},
        }
    )

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(checkpoint=checkpoint),  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-state-contract",
            attempt=3,
            overrides={"comments": {"top_n": 9}},
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata", "download_media"],
        )
    )

    expected_keys = {
        "job_id",
        "attempt",
        "mode",
        "content_type",
        "source_url",
        "title",
        "platform",
        "video_uid",
        "published_at",
        "overrides",
        "comments_policy",
        "frame_policy",
        "llm_policy",
        "metadata",
        "media_path",
        "download_mode",
        "subtitle_files",
        "transcript",
        "comments",
        "frames",
        "llm_input_mode",
        "llm_media_input",
        "outline",
        "digest",
        "artifacts",
        "degradations",
        "steps",
        "resume",
    }
    state = observed["state"]
    assert set(state.keys()) == expected_keys
    assert state["content_type"] == "video"
    assert state["source_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert state["title"] == "Demo State Contract"
    assert state["video_uid"] == "u-123"
    assert state["published_at"] == "2026-01-01T00:00:00Z"
    assert state["comments_policy"]["platform"] == "youtube"
    assert state["frame_policy"] == frame_policy
    assert state["llm_policy"] == llm_policy
    assert state["llm_media_input"] == {"video_available": False, "frame_count": 0}
    assert state["download_mode"] == "text_only"
    assert state["transcript"] == ""
    assert state["resume"] == {
        "checkpoint_step": "download_media",
        "checkpoint_payload": {"from_checkpoint": True},
        "resume_upto_idx": 1,
    }
    assert observed["resume_hint"] is True
    assert result["resume"] == state["resume"]


def test_run_pipeline_return_payload_contract_includes_expected_keys(
    monkeypatch: Any, tmp_path: Path
) -> None:
    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-return-contract",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert set(result.keys()) == {
        "job_id",
        "attempt",
        "mode",
        "content_type",
        "final_status",
        "steps",
        "artifact_dir",
        "artifacts",
        "degradations",
        "llm_required",
        "llm_gate_passed",
        "hard_fail_reason",
        "llm_input_mode",
        "llm_media_input",
        "resume",
        "fatal_error",
        "completed_at",
    }
    assert result["artifact_dir"] is None
    assert result["artifacts"] == {}
    assert result["degradations"] == []
    assert result["content_type"] == "video"
    assert result["llm_media_input"] == {"video_available": False, "frame_count": 0}
    assert result["resume"] == {
        "checkpoint_step": None,
        "checkpoint_payload": {},
        "resume_upto_idx": -1,
    }
    assert result["fatal_error"] is None
    assert isinstance(result["completed_at"], str)
    assert "T" in result["completed_at"]


def test_run_pipeline_return_payload_uses_default_empty_structures(
    monkeypatch: Any, tmp_path: Path
) -> None:
    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-return-defaults",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result["artifact_dir"] is None
    assert result["artifacts"] == {}
    assert result["degradations"] == []
    assert result["resume"] == {
        "checkpoint_step": None,
        "checkpoint_payload": {},
        "resume_upto_idx": -1,
    }


def test_run_pipeline_return_payload_falls_back_when_runtime_keys_are_removed(
    monkeypatch: Any, tmp_path: Path
) -> None:
    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        state.pop("artifacts", None)
        state.pop("degradations", None)
        state.pop("llm_media_input", None)
        state.pop("resume", None)
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-return-fallbacks",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result["artifacts"] == {}
    assert result["degradations"] == []
    assert result["llm_media_input"] is None
    assert result["resume"] == {}


def test_run_pipeline_breaks_on_llm_digest_failure_when_hard_required(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_digest":
            state["steps"][step_name] = {"status": "failed", "error": "digest_failure"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-hard-llm-digest-fail",
            attempt=1,
            mode="full",
        )
    )

    assert "build_embeddings" not in seen_steps
    assert result["final_status"] == "failed"
    assert result["llm_required"] is True
    assert result["llm_gate_passed"] is False
    assert result["hard_fail_reason"] == "digest_failure"
    assert result["fatal_error"] == "llm_digest:digest_failure"


def test_run_pipeline_defaults_mode_llm_input_and_platform_policy(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}
    seen_mode_args: list[str] = []

    monkeypatch.setattr(
        orchestrator,
        "normalize_pipeline_mode",
        lambda value: seen_mode_args.append(str(value)) or "full",
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda settings, overrides, *, platform: (
            captured.setdefault(
                "comments_policy",
                {"settings": settings, "overrides": dict(overrides), "platform": platform},
            )
            or {"platform": platform}
        ),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda settings, overrides: (
            captured.setdefault(
                "frame_policy",
                {"settings": settings, "overrides": dict(overrides)},
            )
            or {"ok": True}
        ),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda settings, overrides, **_kwargs: (
            captured.setdefault(
                "llm_policy",
                {"settings": settings, "overrides": dict(overrides)},
            )
            or {"hard_required": True}
        ),
        raising=False,
    )

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        captured["state_mode"] = state["mode"]
        captured["state_llm_input_mode"] = state["llm_input_mode"]
        captured["state_platform"] = state["platform"]
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-defaults",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured["comments_policy"]["platform"] == "youtube"
    assert captured["state_platform"] == "youtube"
    assert captured["state_mode"] == "full"
    assert captured["state_llm_input_mode"] == "auto"
    assert seen_mode_args == ["full"]
    assert result["mode"] == "full"
    assert result["llm_input_mode"] == "auto"


def test_run_pipeline_calls_checkpoint_with_job_id_and_missing_checkpoint_defaults(
    monkeypatch: Any, tmp_path: Path
) -> None:
    sqlite_store = _FakeSQLiteStore(checkpoint={})
    observed_resume_hints: list[bool] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, force_run
        observed_resume_hints.append(resume_hint)
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(record={"job_id": "job-checkpoint-missing"}),  # type: ignore[arg-type]
            job_id="job-checkpoint-missing",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert sqlite_store.last_checkpoint_job_id == "job-checkpoint-missing"
    assert result["resume"]["checkpoint_step"] is None
    assert result["resume"]["resume_upto_idx"] == -1
    assert observed_resume_hints == [False]


def test_run_pipeline_default_mode_raw_value_is_full_when_normalizer_is_identity(
    monkeypatch: Any, tmp_path: Path
) -> None:
    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "normalize_pipeline_mode", lambda value: value, raising=False)
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-default-mode-raw",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result["mode"] == "full"


def test_run_pipeline_missing_platform_passes_empty_string_to_comments_policy(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured_platforms: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda _settings, _overrides, *, platform: (
            captured_platforms.append(platform) or {"platform": platform}
        ),
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda *_args, **_kwargs: {"method": "fps", "max_frames": 1},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda *_args, **_kwargs: {"hard_required": True},
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(
                record={
                    "job_id": "job-missing-platform",
                    "job_status": "running",
                    "job_kind": "phase2_ingest_stub",
                    "idempotency_key": "idem",
                    "video_id": "video-id",
                    "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "title": "Demo Missing Platform",
                    "published_at": None,
                }
            ),  # type: ignore[arg-type]
            job_id="job-missing-platform",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured_platforms == [""]
    assert result["mode"] == "full"


def test_run_pipeline_initial_llm_media_input_literal_when_refresh_is_noop(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured_llm_media_input: list[dict[str, Any]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        captured_llm_media_input.append(dict(state.get("llm_media_input") or {}))
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(
        orchestrator, "refresh_llm_media_input_dimension", lambda _state: None, raising=False
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-media-input-literal",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured_llm_media_input == [{"video_available": False, "frame_count": 0}]
    assert result["mode"] == "full"


def test_run_pipeline_llm_input_mode_uses_settings_field_only(tmp_path: Path) -> None:
    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    from pytest import MonkeyPatch

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)
    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda *_args, **_kwargs: {"top_n": 1, "replies_per_comment": 0, "sort": "hot"},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda *_args, **_kwargs: {"method": "fps", "max_frames": 1},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda *_args, **_kwargs: {"hard_required": True},
        raising=False,
    )

    settings_default = _make_settings(tmp_path)
    settings_text = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace-text").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root-text").resolve()),
        pipeline_llm_input_mode="text",
    )
    settings_missing_attr = type(
        "_SettingsWithoutLlmInputMode",
        (),
        {
            "pipeline_workspace_dir": str((tmp_path / "workspace-missing").resolve()),
            "pipeline_artifact_root": str((tmp_path / "artifact-root-missing").resolve()),
        },
    )()

    result_default = asyncio.run(
        orchestrator.run_pipeline(
            settings_default,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-input-default",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )
    result_text = asyncio.run(
        orchestrator.run_pipeline(
            settings_text,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-input-text",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )
    result_missing = asyncio.run(
        orchestrator.run_pipeline(
            settings_missing_attr,  # type: ignore[arg-type]
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-input-missing",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result_default["llm_input_mode"] == "auto"
    assert result_text["llm_input_mode"] == "text"
    assert result_missing["llm_input_mode"] == "auto"
    monkeypatch.undo()


def test_run_pipeline_normalizes_uppercase_mode_and_llm_input_defaults(
    tmp_path: Path,
) -> None:
    from pytest import MonkeyPatch

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)
    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda *_args, **_kwargs: {"top_n": 1, "replies_per_comment": 0, "sort": "hot"},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda *_args, **_kwargs: {"method": "fps", "max_frames": 1},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda *_args, **_kwargs: {"hard_required": True},
        raising=False,
    )

    result_mode_upper = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-mode-upper",
            attempt=1,
            mode="FULL",
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )
    result_llm_mode_upper = asyncio.run(
        orchestrator.run_pipeline(
            Settings(
                pipeline_workspace_dir=str((tmp_path / "workspace-upper").resolve()),
                pipeline_artifact_root=str((tmp_path / "artifact-root-upper").resolve()),
                pipeline_llm_input_mode="AUTO",
            ),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-mode-upper",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result_mode_upper["mode"] == "full"
    assert result_llm_mode_upper["llm_input_mode"] == "auto"
    monkeypatch.undo()


def test_run_pipeline_passes_exact_raw_values_to_mode_normalizers(tmp_path: Path) -> None:
    from pytest import MonkeyPatch

    seen: list[tuple[str, object]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch = MonkeyPatch()
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)
    monkeypatch.setattr(
        orchestrator,
        "build_comments_policy",
        lambda *_args, **_kwargs: {"top_n": 1, "replies_per_comment": 0, "sort": "hot"},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_frame_policy",
        lambda *_args, **_kwargs: {"method": "fps", "max_frames": 1},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda *_args, **_kwargs: {"hard_required": True},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "normalize_pipeline_mode",
        lambda value: seen.append(("mode", value)) or "full",
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "normalize_llm_input_mode",
        lambda value: seen.append(("llm_input_mode", value)) or "auto",
        raising=False,
    )

    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace-exact").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root-exact").resolve()),
        pipeline_llm_input_mode="AUTO",
    )

    asyncio.run(
        orchestrator.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-exact-args",
            attempt=1,
            mode="FULL",
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert ("mode", "FULL") in seen
    assert ("llm_input_mode", "AUTO") in seen
    monkeypatch.undo()


def test_run_pipeline_policy_builders_use_resolved_overrides_and_normalized_platform(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}
    job_overrides = {"comments": {"top_n": 3}, "llm": {"hard_required": False}}

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        captured["state_overrides"] = dict(state.get("overrides") or {})
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    def _capture_comments_policy(
        settings: Settings, overrides: dict[str, Any], *, platform: str
    ) -> dict[str, Any]:
        captured["comments_policy_args"] = {
            "settings": settings,
            "overrides": dict(overrides),
            "platform": platform,
        }
        return {"top_n": 3, "platform": platform}

    def _capture_frame_policy(settings: Settings, overrides: dict[str, Any]) -> dict[str, Any]:
        captured["frame_policy_args"] = {"settings": settings, "overrides": dict(overrides)}
        return {"method": "fps", "max_frames": 2}

    def _capture_llm_policy(
        settings: Settings,
        overrides: dict[str, Any],
        *,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        captured["llm_policy_args"] = {
            "settings": settings,
            "overrides": dict(overrides),
            "content_type": content_type,
        }
        return {"hard_required": False}

    monkeypatch.setattr(
        orchestrator, "build_comments_policy", _capture_comments_policy, raising=False
    )
    monkeypatch.setattr(orchestrator, "build_frame_policy", _capture_frame_policy, raising=False)
    monkeypatch.setattr(orchestrator, "build_llm_policy", _capture_llm_policy, raising=False)
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    settings = _make_settings(tmp_path)
    result = asyncio.run(
        orchestrator.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(
                record={
                    "job_id": "job-policy-calls",
                    "job_status": "running",
                    "job_kind": "phase2_ingest_stub",
                    "idempotency_key": "idem",
                    "video_id": "video-id",
                    "platform": "YouTube",
                    "video_uid": "video-uid",
                    "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "title": "Demo",
                    "published_at": None,
                    "overrides_json": job_overrides,
                }
            ),  # type: ignore[arg-type]
            job_id="job-policy-calls",
            attempt=1,
            overrides={},
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured["state_overrides"] == job_overrides
    assert captured["comments_policy_args"] == {
        "settings": settings,
        "overrides": job_overrides,
        "platform": "youtube",
    }
    assert captured["frame_policy_args"] == {"settings": settings, "overrides": job_overrides}
    assert captured["llm_policy_args"] == {
        "settings": settings,
        "overrides": job_overrides,
        "content_type": "video",
    }
    assert result["llm_required"] is False


def test_run_pipeline_resume_hint_boundary_without_forced_steps(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    sqlite_store = _FakeSQLiteStore(checkpoint={"last_completed_step": "step_b"})

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical
        captured.append(
            {
                "step": step_name,
                "resume_hint": resume_hint,
                "force_run": force_run,
            }
        )
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-resume-boundary",
            attempt=1,
            mode="full",
            step_handlers=[
                ("step_a", lambda *_: None, False),
                ("step_b", lambda *_: None, False),
                ("step_c", lambda *_: None, False),
            ],
            pipeline_steps=["step_a", "step_b", "step_c"],
        )
    )

    assert captured == [
        {"step": "step_a", "resume_hint": True, "force_run": False},
        {"step": "step_b", "resume_hint": True, "force_run": False},
        {"step": "step_c", "resume_hint": False, "force_run": False},
    ]
    assert result["resume"]["resume_upto_idx"] == 1


def test_run_pipeline_fatal_error_uses_literal_failed_when_llm_failure_has_no_detail(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {"status": "failed"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-hard-llm-fail-no-detail",
            attempt=1,
            mode="full",
        )
    )

    assert "llm_digest" not in seen_steps
    assert result["final_status"] == "failed"
    assert result["hard_fail_reason"] == "llm_step_failed"
    assert result["fatal_error"] == "llm_outline:failed"


def test_run_pipeline_refresh_llm_forced_steps_disable_resume_hint(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    sqlite_store = _FakeSQLiteStore(checkpoint={"last_completed_step": "write_artifacts"})

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical
        captured.append({"step": step_name, "resume_hint": resume_hint, "force_run": force_run})
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-refresh-llm-force-run",
            attempt=1,
            mode="refresh_llm",
        )
    )

    by_step = {item["step"]: item for item in captured}
    assert by_step["extract_frames"] == {
        "step": "extract_frames",
        "resume_hint": True,
        "force_run": False,
    }
    assert by_step["llm_outline"] == {
        "step": "llm_outline",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["llm_digest"] == {
        "step": "llm_digest",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["build_embeddings"] == {
        "step": "build_embeddings",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["write_artifacts"] == {
        "step": "write_artifacts",
        "resume_hint": False,
        "force_run": True,
    }
    assert result["resume"]["checkpoint_step"] == "write_artifacts"
    assert result["resume"]["resume_upto_idx"] == 8


def test_run_pipeline_checkpoint_step_not_in_pipeline_steps_disables_resume_hint(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured_resume_hints: list[bool] = []
    sqlite_store = _FakeSQLiteStore(
        checkpoint={"last_completed_step": "llm_outline", "payload": {"from": "checkpoint"}}
    )

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, force_run
        captured_resume_hints.append(resume_hint)
        state["steps"]["step_a"] = {"status": "succeeded"}
        return state["steps"]["step_a"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-checkpoint-not-in-steps",
            attempt=1,
            step_handlers=[("step_a", lambda *_: None, False), ("step_b", lambda *_: None, False)],
            pipeline_steps=["step_a", "step_b"],
        )
    )

    assert captured_resume_hints == [False, False]
    assert result["resume"] == {
        "checkpoint_step": "llm_outline",
        "checkpoint_payload": {"from": "checkpoint"},
        "resume_upto_idx": -1,
    }


def test_run_pipeline_llm_policy_hard_required_override_prevents_hard_break(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {"status": "failed", "reason": "soft_llm_outage"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda _settings, _overrides, **_kwargs: {"hard_required": False},
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            Settings(
                pipeline_workspace_dir=str((tmp_path / "workspace-llm-policy").resolve()),
                pipeline_artifact_root=str((tmp_path / "artifact-root-llm-policy").resolve()),
                pipeline_llm_hard_required=True,
            ),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-llm-policy-hard-required-override",
            attempt=1,
            mode="full",
        )
    )

    assert seen_steps == PIPELINE_STEPS
    assert result["llm_required"] is False
    assert result["llm_gate_passed"] is True
    assert result["hard_fail_reason"] is None
    assert result["fatal_error"] is None
    assert result["final_status"] == "degraded"


def test_run_pipeline_fatal_error_prefers_error_over_reason_when_both_present(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {
                "status": "failed",
                "reason": "reason_value",
                "error": "error_value",
            }
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-fatal-error-priority",
            attempt=1,
            mode="full",
        )
    )

    assert "llm_digest" not in seen_steps
    assert result["final_status"] == "failed"
    assert result["hard_fail_reason"] == "reason_value"
    assert result["fatal_error"] == "llm_outline:error_value"


def test_run_pipeline_non_llm_failure_does_not_set_fatal_error(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "fetch_metadata":
            state["steps"][step_name] = {"status": "failed", "error": "metadata_failed"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-non-llm-failure-no-fatal-error",
            attempt=1,
            mode="full",
        )
    )

    assert seen_steps == PIPELINE_STEPS
    assert result["final_status"] == "failed"
    assert result["fatal_error"] is None


def test_run_pipeline_passes_llm_policy_to_hard_required_resolver(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []
    captured: dict[str, Any] = {}

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {"status": "failed", "reason": "soft_provider_outage"}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    def _capture_hard_required(settings: Settings, llm_policy: dict[str, Any] | None) -> bool:
        captured["settings"] = settings
        captured["llm_policy"] = dict(llm_policy or {})
        return False

    monkeypatch.setattr(
        orchestrator,
        "build_llm_policy",
        lambda _settings, _overrides, **_kwargs: {"hard_required": True, "from_builder": "yes"},
        raising=False,
    )
    monkeypatch.setattr(
        orchestrator,
        "pipeline_llm_hard_required",
        _capture_hard_required,
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    settings = _make_settings(tmp_path)
    result = asyncio.run(
        orchestrator.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-hard-required-policy-arg",
            attempt=1,
            step_handlers=[
                ("llm_outline", lambda *_: None, True),
                ("llm_digest", lambda *_: None, True),
            ],
            pipeline_steps=["llm_outline", "llm_digest"],
        )
    )

    assert captured["settings"] is settings
    assert captured["llm_policy"] == {"hard_required": True, "from_builder": "yes"}
    assert seen_steps == ["llm_outline", "llm_digest"]
    assert result["llm_required"] is False
    assert result["fatal_error"] is None


def test_run_pipeline_hard_required_resolver_receives_runtime_llm_policy(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["llm_policy"] = {"hard_required": False, "max_retries": 3}
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    def _capture_hard_required(settings: Settings, llm_policy: dict[str, Any] | None) -> bool:
        captured["settings"] = settings
        captured["llm_policy"] = dict(llm_policy or {})
        return False

    monkeypatch.setattr(
        orchestrator,
        "pipeline_llm_hard_required",
        _capture_hard_required,
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    settings = _make_settings(tmp_path)
    asyncio.run(
        orchestrator.run_pipeline(
            settings,
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-runtime-llm-policy",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert captured["settings"] is settings
    assert captured["llm_policy"]["hard_required"] is True
    assert captured["llm_policy"]["max_retries"] is None


def test_run_pipeline_checkpoint_none_uses_resume_literal_defaults(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical
        captured.append(
            {
                "step": step_name,
                "resume_hint": resume_hint,
                "force_run": force_run,
            }
        )
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(checkpoint=None),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-checkpoint-none",
            attempt=1,
            step_handlers=[
                ("step_a", lambda *_: None, False),
                ("step_b", lambda *_: None, False),
            ],
            pipeline_steps=["step_a", "step_b"],
        )
    )

    assert captured == [
        {"step": "step_a", "resume_hint": False, "force_run": False},
        {"step": "step_b", "resume_hint": False, "force_run": False},
    ]
    assert result["resume"] == {
        "checkpoint_step": None,
        "checkpoint_payload": {},
        "resume_upto_idx": -1,
    }


def test_run_pipeline_resume_hint_stays_false_past_checkpoint_boundary(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    sqlite_store = _FakeSQLiteStore(checkpoint={"last_completed_step": "step_a"})

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, force_run
        captured.append({"step": step_name, "resume_hint": resume_hint})
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-resume-boundary",
            attempt=1,
            step_handlers=[
                ("step_a", lambda *_: None, False),
                ("step_b", lambda *_: None, False),
                ("step_c", lambda *_: None, False),
            ],
            pipeline_steps=["step_a", "step_b", "step_c"],
        )
    )

    assert captured == [
        {"step": "step_a", "resume_hint": True},
        {"step": "step_b", "resume_hint": False},
        {"step": "step_c", "resume_hint": False},
    ]


def test_run_pipeline_refresh_comments_forced_steps_disable_resume_hint(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    sqlite_store = _FakeSQLiteStore(checkpoint={"last_completed_step": "write_artifacts"})

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical
        captured.append({"step": step_name, "resume_hint": resume_hint, "force_run": force_run})
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-refresh-comments-force-run",
            attempt=1,
            mode="refresh_comments",
        )
    )

    by_step = {item["step"]: item for item in captured}
    assert by_step["fetch_metadata"] == {
        "step": "fetch_metadata",
        "resume_hint": True,
        "force_run": False,
    }
    assert by_step["download_media"] == {
        "step": "download_media",
        "resume_hint": True,
        "force_run": False,
    }
    assert by_step["collect_subtitles"] == {
        "step": "collect_subtitles",
        "resume_hint": True,
        "force_run": False,
    }
    assert by_step["collect_comments"] == {
        "step": "collect_comments",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["llm_outline"] == {
        "step": "llm_outline",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["llm_digest"] == {
        "step": "llm_digest",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["build_embeddings"] == {
        "step": "build_embeddings",
        "resume_hint": False,
        "force_run": True,
    }
    assert by_step["write_artifacts"] == {
        "step": "write_artifacts",
        "resume_hint": False,
        "force_run": True,
    }
    assert result["resume"]["checkpoint_step"] == "write_artifacts"
    assert result["resume"]["resume_upto_idx"] == 8


def test_run_pipeline_default_handler_execution_order_and_critical_flags(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, resume_hint, force_run
        captured.append({"step": step_name, "critical": critical})
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-default-handler-critical-contract",
            attempt=1,
            mode="full",
        )
    )

    assert [item["step"] for item in captured] == PIPELINE_STEPS
    by_step = {item["step"]: item["critical"] for item in captured}
    assert by_step == {
        "fetch_metadata": False,
        "download_media": False,
        "collect_subtitles": False,
        "collect_comments": False,
        "extract_frames": False,
        "llm_outline": True,
        "llm_digest": True,
        "build_embeddings": False,
        "write_artifacts": True,
    }


def test_run_pipeline_text_only_mode_uses_skip_callable_for_all_skipped_steps(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []

    async def _fake_execute_step(
        ctx: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del critical, resume_hint
        step_func_name = getattr(step_func, "__name__", "unknown")
        captured.append(
            {"step": step_name, "step_func_name": step_func_name, "force_run": force_run}
        )
        if step_func_name == "_skip":
            execution = await step_func(ctx, state)
            state["steps"][step_name] = {"status": execution.status, "reason": execution.reason}
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-text-only-skip-callable-contract",
            attempt=1,
            mode="text_only",
        )
    )

    by_step = {item["step"]: item for item in captured}
    for skipped_step in ("download_media", "collect_subtitles", "extract_frames"):
        assert by_step[skipped_step]["step_func_name"] == "_skip"
        assert by_step[skipped_step]["force_run"] is True


def test_run_pipeline_text_only_mode_relaxes_video_raw_stage_contract(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured_raw_stage: dict[str, Any] = {}

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        if step_name == "llm_digest":
            captured_raw_stage.update(dict(state["llm_policy"]["raw_stage"]))
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-text-only-raw-stage-relaxed",
            attempt=1,
            mode="text_only",
        )
    )

    assert captured_raw_stage["video_first"] is False
    assert captured_raw_stage["video_input_required"] is False
    assert captured_raw_stage["review_required"] is False
    assert captured_raw_stage["primary_input_mode"] == "text"
    assert captured_raw_stage["review_input_mode"] == "text"


def test_run_pipeline_skip_builder_receives_exact_step_name_and_mode(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[tuple[str, str]] = []

    def _fake_build_mode_skip_step(step_name: str, mode: str):
        captured.append((step_name, mode))

        async def _skip(_: Any, __: dict[str, Any]) -> StepExecution:
            return StepExecution(status="skipped", reason="mode_matrix_skip")

        return _skip

    async def _fake_execute_step(
        ctx: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del critical, resume_hint, force_run
        execution = await step_func(ctx, state)
        state["steps"][step_name] = {"status": execution.status, "reason": execution.reason}
        return state["steps"][step_name]

    monkeypatch.setattr(
        orchestrator, "build_mode_skip_step", _fake_build_mode_skip_step, raising=False
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-skip-builder-args",
            attempt=1,
            mode="text_only",
            pipeline_steps=["download_media", "collect_subtitles", "extract_frames"],
        )
    )

    assert captured == [
        ("download_media", "text_only"),
        ("collect_subtitles", "text_only"),
        ("extract_frames", "text_only"),
    ]


def test_run_pipeline_resume_payload_non_dict_raises_value_error(
    monkeypatch: Any, tmp_path: Path
) -> None:
    import pytest

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    with pytest.raises(ValueError, match="dictionary update sequence element"):
        asyncio.run(
            orchestrator.run_pipeline(
                _make_settings(tmp_path),
                _FakeSQLiteStore(
                    checkpoint={
                        "last_completed_step": "fetch_metadata",
                        "payload": "not-a-dict",
                    }
                ),  # type: ignore[arg-type]
                _FakePGStore(),  # type: ignore[arg-type]
                job_id="job-resume-payload-non-dict",
                attempt=1,
                step_handlers=[("fetch_metadata", lambda *_: None, False)],
                pipeline_steps=["fetch_metadata"],
            )
        )


def test_run_pipeline_fatal_error_falls_back_to_reason_when_error_is_blank(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_digest":
            state["steps"][step_name] = {
                "status": "failed",
                "error": "",
                "reason": "digest_reason_fallback",
            }
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-fatal-error-empty-error-fallback",
            attempt=1,
            mode="full",
        )
    )

    assert "build_embeddings" not in seen_steps
    assert result["hard_fail_reason"] == "digest_reason_fallback"
    assert result["fatal_error"] == "llm_digest:digest_reason_fallback"


def test_run_pipeline_full_mode_force_run_overrides_resume_hint_when_patched(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: list[dict[str, Any]] = []
    sqlite_store = _FakeSQLiteStore(checkpoint={"last_completed_step": "step_c"})

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical
        captured.append({"step": step_name, "resume_hint": resume_hint, "force_run": force_run})
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(
        orchestrator,
        "PIPELINE_MODE_FORCE_STEPS",
        {
            "full": {"step_a"},
            "refresh_llm": set(orchestrator.PIPELINE_MODE_FORCE_STEPS.get("refresh_llm", set())),
            "refresh_comments": set(
                orchestrator.PIPELINE_MODE_FORCE_STEPS.get("refresh_comments", set())
            ),
            "text_only": set(orchestrator.PIPELINE_MODE_FORCE_STEPS.get("text_only", set())),
        },
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            sqlite_store,  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-force-over-resume",
            attempt=1,
            mode="full",
            step_handlers=[
                ("step_a", lambda *_: None, False),
                ("step_b", lambda *_: None, False),
                ("step_c", lambda *_: None, False),
            ],
            pipeline_steps=["step_a", "step_b", "step_c"],
        )
    )

    assert captured == [
        {"step": "step_a", "resume_hint": False, "force_run": True},
        {"step": "step_b", "resume_hint": True, "force_run": False},
        {"step": "step_c", "resume_hint": True, "force_run": False},
    ]
    assert result["resume"]["resume_upto_idx"] == 2


def test_run_pipeline_fatal_error_uses_reason_when_error_is_falsey_non_string(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen_steps: list[str] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_func, critical, resume_hint, force_run
        seen_steps.append(step_name)
        if step_name == "llm_outline":
            state["steps"][step_name] = {
                "status": "failed",
                "error": 0,
                "reason": "reason_from_falsey_error",
            }
        else:
            state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-falsey-error-priority",
            attempt=1,
            mode="full",
        )
    )

    assert "llm_digest" not in seen_steps
    assert result["hard_fail_reason"] == "reason_from_falsey_error"
    assert result["fatal_error"] == "llm_outline:reason_from_falsey_error"


def test_run_pipeline_return_payload_propagates_runtime_state_values(
    monkeypatch: Any, tmp_path: Path
) -> None:
    expected_artifact_dir = str((tmp_path / "artifacts" / "runtime").resolve())
    expected_artifacts = {"digest": "digest.md", "meta": "meta.json"}
    expected_degradations = [
        {"step": "fetch_metadata", "reason": "fallback_used", "status": "succeeded"}
    ]

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["artifact_dir"] = expected_artifact_dir
        state["artifacts"] = dict(expected_artifacts)
        state["degradations"] = list(expected_degradations)
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-return-state-values",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result["artifact_dir"] == expected_artifact_dir
    assert result["artifacts"] == expected_artifacts
    assert result["degradations"] == expected_degradations
    assert result["fatal_error"] is None


def test_run_pipeline_passes_exact_degradations_list_to_status_resolver(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}
    expected_degradations = [{"step": "fetch_metadata", "reason": "fallback_used"}]

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        state["degradations"] = list(expected_degradations)
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    def _fake_resolve_pipeline_status(
        step_records: dict[str, Any],
        degradations: list[dict[str, Any]] | None = None,
        *,
        pipeline_llm_hard_required: bool | None = True,
    ) -> str:
        captured["step_records"] = dict(step_records)
        captured["degradations"] = degradations
        captured["pipeline_llm_hard_required"] = pipeline_llm_hard_required
        return "degraded"

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)
    monkeypatch.setattr(
        orchestrator,
        "resolve_pipeline_status",
        _fake_resolve_pipeline_status,
        raising=False,
    )

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-degradations-resolver",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result["final_status"] == "degraded"
    assert captured["degradations"] == expected_degradations
    assert captured["degradations"] is not expected_degradations


def test_run_pipeline_default_fetch_metadata_handler_preserves_ctx_state_and_run_command(
    monkeypatch: Any, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_fetch_metadata(
        current_ctx: Any,
        current_state: dict[str, Any],
        *,
        run_command: Any,
    ) -> Any:
        captured["ctx"] = current_ctx
        captured["state"] = current_state
        captured["run_command"] = run_command
        return SimpleNamespace(status="succeeded")

    monkeypatch.setattr(orchestrator, "step_fetch_metadata", _fake_fetch_metadata, raising=False)

    async def _fake_execute_step(
        ctx: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del critical, resume_hint, force_run
        execution = await step_func(ctx, state)
        state["steps"][step_name] = {"status": execution.status}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-default-fetch-handler",
            attempt=1,
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert result["steps"]["fetch_metadata"]["status"] == "succeeded"
    assert captured["ctx"].job_id == "job-default-fetch-handler"
    assert captured["state"]["job_id"] == "job-default-fetch-handler"
    assert captured["state"]["mode"] == "full"
    assert captured["run_command"] is orchestrator.run_command


def test_run_pipeline_default_handlers_delegate_expected_collaborators(
    monkeypatch: Any, tmp_path: Path
) -> None:
    seen: dict[str, dict[str, Any]] = {}
    call_order: list[str] = []

    def _recording_step(name: str):
        async def _step(ctx: Any, state: dict[str, Any], **kwargs: Any) -> Any:
            seen[name] = {"ctx": ctx, "state": state, "kwargs": dict(kwargs)}
            call_order.append(name)
            return StepExecution(status="succeeded")

        return _step

    monkeypatch.setattr(
        orchestrator, "step_fetch_metadata", _recording_step("fetch_metadata"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_download_media", _recording_step("download_media"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_collect_subtitles", _recording_step("collect_subtitles"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_collect_comments", _recording_step("collect_comments"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_extract_frames", _recording_step("extract_frames"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_llm_outline", _recording_step("llm_outline"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_llm_digest", _recording_step("llm_digest"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_build_embeddings", _recording_step("build_embeddings"), raising=False
    )
    monkeypatch.setattr(
        orchestrator, "step_write_artifacts", _recording_step("write_artifacts"), raising=False
    )

    async def _fake_execute_step(
        ctx: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del critical, resume_hint, force_run
        execution = await step_func(ctx, state)
        state["steps"][step_name] = {"status": execution.status}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-default-handler-delegate-contract",
            attempt=1,
            mode="full",
        )
    )

    assert call_order == PIPELINE_STEPS
    assert result["final_status"] == "succeeded"
    assert seen["extract_frames"]["ctx"].job_id == "job-default-handler-delegate-contract"
    assert seen["extract_frames"]["state"]["job_id"] == "job-default-handler-delegate-contract"
    assert seen["llm_digest"]["ctx"].job_id == "job-default-handler-delegate-contract"
    assert seen["llm_digest"]["state"]["job_id"] == "job-default-handler-delegate-contract"
    assert seen["fetch_metadata"]["kwargs"] == {"run_command": orchestrator.run_command}
    assert seen["download_media"]["kwargs"] == {"run_command": orchestrator.run_command}
    assert seen["collect_subtitles"]["kwargs"] == {
        "run_command": orchestrator.run_command,
        "fetch_youtube_transcript_text_fn": orchestrator.fetch_youtube_transcript_text,
    }
    assert seen["collect_comments"]["kwargs"] == {
        "bilibili_collector_cls": orchestrator.BilibiliCommentCollector,
        "youtube_collector_cls": orchestrator.YouTubeCommentCollector,
    }
    assert seen["extract_frames"]["kwargs"] == {"run_command": orchestrator.run_command}
    assert seen["llm_outline"]["kwargs"] == {"gemini_generate_fn": orchestrator.gemini_generate}
    assert seen["llm_digest"]["kwargs"] == {"gemini_generate_fn": orchestrator.gemini_generate}
    assert seen["build_embeddings"]["kwargs"] == {}
    assert seen["write_artifacts"]["kwargs"] == {}


def test_run_pipeline_unknown_mode_uses_empty_skip_and_force_sets(
    monkeypatch: Any, tmp_path: Path
) -> None:
    observed: list[dict[str, Any]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        observed.append(
            {
                "step_name": step_name,
                "force_run": force_run,
                "step_func_name": getattr(step_func, "__name__", type(step_func).__name__),
            }
        )
        state["steps"][step_name] = {"status": "succeeded"}
        return state["steps"][step_name]

    monkeypatch.setattr(orchestrator, "normalize_pipeline_mode", lambda _raw: "unknown_mode")
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-unknown-mode-fallback",
            attempt=1,
            mode="full",
            pipeline_steps=["fetch_metadata", "extract_frames", "llm_digest"],
            step_handlers=[
                ("fetch_metadata", lambda *_args, **_kwargs: None, False),
                ("extract_frames", lambda *_args, **_kwargs: None, False),
                ("llm_digest", lambda *_args, **_kwargs: None, True),
            ],
        )
    )

    assert result["mode"] == "unknown_mode"
    assert observed == [
        {"step_name": "fetch_metadata", "force_run": False, "step_func_name": "<lambda>"},
        {"step_name": "extract_frames", "force_run": False, "step_func_name": "<lambda>"},
        {"step_name": "llm_digest", "force_run": False, "step_func_name": "<lambda>"},
    ]


def test_run_pipeline_initial_comments_uses_empty_comments_payload_result(
    monkeypatch: Any, tmp_path: Path
) -> None:
    expected_comments = {
        "sort": "hot",
        "top_comments": [{"comment_id": "c1"}],
        "replies": {"c1": []},
        "fetched_at": "2026-03-09T12:00:00+00:00",
    }
    observed_comments: list[dict[str, Any]] = []

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        observed_comments.append(dict(state.get("comments") or {}))
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(
        orchestrator,
        "empty_comments_payload",
        lambda: dict(expected_comments),
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-empty-comments-payload-contract",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert observed_comments == [expected_comments]
    assert result["steps"]["fetch_metadata"]["status"] == "succeeded"


def test_run_pipeline_refresh_llm_media_input_updates_state_and_return_payload(
    monkeypatch: Any, tmp_path: Path
) -> None:
    refresh_calls: list[dict[str, Any]] = []
    observed_from_step: list[dict[str, Any]] = []

    def _refresh_llm_media_input_dimension(state: dict[str, Any]) -> None:
        refresh_calls.append(dict(state.get("llm_media_input") or {}))
        state["llm_media_input"] = {"video_available": True, "frame_count": 8}

    async def _fake_execute_step(
        _: orchestrator.PipelineContext,
        state: dict[str, Any],
        *,
        step_name: str,
        step_func: Any,
        critical: bool = False,
        resume_hint: bool = False,
        force_run: bool = False,
    ) -> dict[str, Any]:
        del step_name, step_func, critical, resume_hint, force_run
        observed_from_step.append(dict(state.get("llm_media_input") or {}))
        state["steps"]["fetch_metadata"] = {"status": "succeeded"}
        return state["steps"]["fetch_metadata"]

    monkeypatch.setattr(
        orchestrator,
        "refresh_llm_media_input_dimension",
        _refresh_llm_media_input_dimension,
        raising=False,
    )
    monkeypatch.setattr(orchestrator, "execute_step", _fake_execute_step, raising=False)

    result = asyncio.run(
        orchestrator.run_pipeline(
            _make_settings(tmp_path),
            _FakeSQLiteStore(),  # type: ignore[arg-type]
            _FakePGStore(),  # type: ignore[arg-type]
            job_id="job-refresh-llm-media-input-contract",
            attempt=1,
            step_handlers=[("fetch_metadata", lambda *_: None, False)],
            pipeline_steps=["fetch_metadata"],
        )
    )

    assert refresh_calls == [{"video_available": False, "frame_count": 0}]
    assert observed_from_step == [{"video_available": True, "frame_count": 8}]
    assert result["llm_media_input"] == {"video_available": True, "frame_count": 8}
