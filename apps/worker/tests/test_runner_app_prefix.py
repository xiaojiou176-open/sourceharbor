from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any

import pytest

from apps.worker.worker.config import Settings
from apps.worker.worker.pipeline.types import ARTICLE_PIPELINE_STEPS, PIPELINE_STEPS, StepExecution


def _apps_runner():
    return importlib.reload(importlib.import_module("apps.worker.worker.pipeline.runner"))


def _settings() -> Settings:
    return Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
    )


def test_app_prefix_runner_policy_wrappers_delegate_to_policy_impls(monkeypatch: Any) -> None:
    runner = _apps_runner()
    settings = _settings()
    captured_retry_policy_calls: list[dict[str, Any]] = []
    captured_classify_error_calls: list[dict[str, str | None]] = []

    def _fake_build_retry_policy_impl(
        current_settings: Settings,
        *,
        step_name: str | None,
        llm_policy: Any,
    ) -> dict[str, dict[str, float | int]]:
        captured_retry_policy_calls.append(
            {
                "settings": current_settings,
                "step_name": step_name,
                "llm_policy": llm_policy,
            }
        )
        return {
            "transient": {"max_retries": 1, "backoff": 0.5, "max_backoff": 1.0},
            "rate_limit": {"max_retries": 1, "backoff": 0.5, "max_backoff": 1.0},
            "auth": {"max_retries": 1, "backoff": 0.5, "max_backoff": 1.0},
            "fatal": {"max_retries": 0, "backoff": 0.0, "max_backoff": 0.0},
        }

    monkeypatch.setattr(runner, "_build_retry_policy_impl", _fake_build_retry_policy_impl)

    assert runner._build_retry_policy.__defaults__ == (None,)
    default_retry_policy = runner._build_retry_policy(settings)
    retry_policy = runner._build_retry_policy(settings, step_name="llm_outline")

    assert captured_retry_policy_calls[0] == {
        "settings": settings,
        "step_name": "write_artifacts",
        "llm_policy": None,
    }
    assert captured_retry_policy_calls[1] == {
        "settings": settings,
        "step_name": "llm_outline",
        "llm_policy": None,
    }
    assert default_retry_policy == retry_policy
    assert isinstance(retry_policy, dict)
    assert set(retry_policy) == {"transient", "rate_limit", "auth", "fatal"}
    assert runner._retry_delay_seconds({"backoff": 0.5, "max_backoff": 1.0}, retries_used=2) == 1.0
    assert runner._classify_error("429", None) == "rate_limit"

    def _fake_classify_error_impl(reason: str | None, error: str | None) -> str:
        captured_classify_error_calls.append({"reason": reason, "error": error})
        return "auth"

    monkeypatch.setattr(runner, "_classify_error_impl", _fake_classify_error_impl)

    assert runner._classify_error("401", "unauthorized") == "auth"
    assert captured_classify_error_calls == [{"reason": "401", "error": "unauthorized"}]


def test_app_prefix_runner_build_retry_policy_keeps_explicit_empty_step_name(
    monkeypatch: Any,
) -> None:
    runner = _apps_runner()
    settings = _settings()
    captured: dict[str, Any] = {}

    def _fake_build_retry_policy_impl(
        current_settings: Settings,
        *,
        step_name: str | None,
        llm_policy: Any,
    ) -> dict[str, dict[str, float | int]]:
        captured["settings"] = current_settings
        captured["step_name"] = step_name
        captured["llm_policy"] = llm_policy
        return {
            "transient": {"max_retries": 0, "backoff": 0.0, "max_backoff": 0.0},
            "rate_limit": {"max_retries": 0, "backoff": 0.0, "max_backoff": 0.0},
            "auth": {"max_retries": 0, "backoff": 0.0, "max_backoff": 0.0},
            "fatal": {"max_retries": 0, "backoff": 0.0, "max_backoff": 0.0},
        }

    monkeypatch.setattr(runner, "_build_retry_policy_impl", _fake_build_retry_policy_impl)

    runner._build_retry_policy(settings, step_name="")
    assert captured == {"settings": settings, "step_name": "", "llm_policy": None}


def test_app_prefix_runner_step_wrappers_delegate_to_impls(monkeypatch: Any) -> None:
    runner = _apps_runner()
    ctx = SimpleNamespace()
    state: dict[str, Any] = {"k": "v"}
    captures: dict[str, dict[str, Any]] = {}

    def _recording_step(key: str):
        async def _impl(
            current_ctx: Any, current_state: dict[str, Any], **kwargs: Any
        ) -> StepExecution:
            captures[key] = {"ctx": current_ctx, "state": current_state, "kwargs": dict(kwargs)}
            return StepExecution(status="succeeded", output={"wrapped": key})

        return _impl

    def _recording_plain_step(key: str):
        async def _impl(current_ctx: Any, current_state: dict[str, Any]) -> StepExecution:
            captures[key] = {"ctx": current_ctx, "state": current_state, "kwargs": {}}
            return StepExecution(status="succeeded", output={"wrapped": key})

        return _impl

    monkeypatch.setattr(runner, "_step_fetch_metadata_impl", _recording_step("fetch_metadata"))
    monkeypatch.setattr(
        runner, "_step_fetch_article_content_impl", _recording_step("fetch_article_content")
    )
    monkeypatch.setattr(runner, "_step_download_media_impl", _recording_step("download_media"))
    monkeypatch.setattr(runner, "_step_extract_frames_impl", _recording_step("extract_frames"))
    monkeypatch.setattr(
        runner, "_step_collect_subtitles_impl", _recording_step("collect_subtitles")
    )
    monkeypatch.setattr(runner, "_step_collect_comments_impl", _recording_step("collect_comments"))
    monkeypatch.setattr(runner, "_step_llm_outline_impl", _recording_step("llm_outline"))
    monkeypatch.setattr(runner, "_step_llm_digest_impl", _recording_step("llm_digest"))
    monkeypatch.setattr(
        runner, "_step_write_artifacts_impl", _recording_plain_step("write_artifacts")
    )
    monkeypatch.setattr(
        runner, "_step_build_embeddings_impl", _recording_plain_step("build_embeddings")
    )

    assert asyncio.run(runner._step_fetch_metadata(ctx, state)).output == {
        "wrapped": "fetch_metadata"
    }
    assert asyncio.run(runner._step_fetch_article_content(ctx, state)).output == {
        "wrapped": "fetch_article_content"
    }
    assert asyncio.run(runner._step_download_media(ctx, state)).output == {
        "wrapped": "download_media"
    }
    assert asyncio.run(runner._step_extract_frames(ctx, state)).output == {
        "wrapped": "extract_frames"
    }
    assert asyncio.run(runner._step_collect_subtitles(ctx, state)).output == {
        "wrapped": "collect_subtitles"
    }
    assert asyncio.run(runner._step_collect_comments(ctx, state)).output == {
        "wrapped": "collect_comments"
    }
    assert asyncio.run(runner._step_llm_outline(ctx, state)).output == {"wrapped": "llm_outline"}
    assert asyncio.run(runner._step_llm_digest(ctx, state)).output == {"wrapped": "llm_digest"}
    assert asyncio.run(runner._step_write_artifacts(ctx, state)).output == {
        "wrapped": "write_artifacts"
    }
    assert asyncio.run(runner._step_build_embeddings(ctx, state)).output == {
        "wrapped": "build_embeddings"
    }

    assert captures["fetch_metadata"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {"run_command": runner._run_command},
    }
    assert captures["fetch_article_content"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {"run_command": runner._run_command},
    }
    assert captures["download_media"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {"run_command": runner._run_command},
    }
    assert captures["extract_frames"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {"run_command": runner._run_command},
    }
    assert captures["collect_subtitles"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {
            "run_command": runner._run_command,
            "fetch_youtube_transcript_text_fn": runner._fetch_youtube_transcript_text,
        },
    }
    assert captures["collect_comments"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {
            "bilibili_collector_cls": runner.BilibiliCommentCollector,
            "youtube_collector_cls": runner.YouTubeCommentCollector,
        },
    }
    assert captures["llm_outline"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {"gemini_generate_fn": runner._gemini_generate},
    }
    assert captures["llm_digest"] == {
        "ctx": ctx,
        "state": state,
        "kwargs": {"gemini_generate_fn": runner._gemini_generate},
    }
    assert captures["write_artifacts"] == {"ctx": ctx, "state": state, "kwargs": {}}
    assert captures["build_embeddings"] == {"ctx": ctx, "state": state, "kwargs": {}}


def test_app_prefix_runner_run_pipeline_builds_expected_step_contracts(monkeypatch: Any) -> None:
    runner = _apps_runner()
    captured: list[dict[str, Any]] = []

    assert runner.run_pipeline.__kwdefaults__ == {
        "mode": None,
        "overrides": None,
        "content_type": None,
    }

    async def _fake_run_pipeline(
        settings: Any,
        sqlite_store: Any,
        pg_store: Any,
        *,
        job_id: str,
        attempt: int,
        mode: str,
        overrides: dict[str, Any] | None,
        step_handlers: list[tuple[str, Any, bool]],
        pipeline_steps: list[str],
        content_type: str,
    ) -> dict[str, Any]:
        captured.append(
            {
                "settings": settings,
                "sqlite_store": sqlite_store,
                "pg_store": pg_store,
                "job_id": job_id,
                "attempt": attempt,
                "mode": mode,
                "overrides": overrides,
                "step_names": [name for name, _, _ in step_handlers],
                "critical_flags": [critical for _, _, critical in step_handlers],
                "pipeline_steps": list(pipeline_steps),
                "content_type": content_type,
            }
        )
        return {"final_status": "succeeded"}

    monkeypatch.setattr(runner.orchestrator, "run_pipeline", _fake_run_pipeline)

    settings = _settings()
    sqlite_store = object()
    pg_store = object()

    video_result = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-video",
            attempt=1,
            mode="full",
            overrides={"k": "v"},
            content_type="video",
        )
    )
    article_result = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-article",
            attempt=2,
            mode="article",
            overrides=None,
            content_type="article",
        )
    )

    assert video_result == {"final_status": "succeeded"}
    assert article_result == {"final_status": "succeeded"}

    video_call, article_call = captured
    assert video_call["settings"] is settings
    assert video_call["sqlite_store"] is sqlite_store
    assert video_call["pg_store"] is pg_store
    assert video_call["job_id"] == "job-video"
    assert video_call["attempt"] == 1
    assert video_call["mode"] == "full"
    assert video_call["overrides"] == {"k": "v"}
    assert video_call["content_type"] == "video"
    assert video_call["pipeline_steps"] == PIPELINE_STEPS
    assert video_call["step_names"] == PIPELINE_STEPS
    assert video_call["critical_flags"][-1] is True
    assert all(flag is False for flag in video_call["critical_flags"][:-1])

    assert article_call["settings"] is settings
    assert article_call["sqlite_store"] is sqlite_store
    assert article_call["pg_store"] is pg_store
    assert article_call["job_id"] == "job-article"
    assert article_call["attempt"] == 2
    assert article_call["mode"] == "article"
    assert article_call["content_type"] == "article"
    assert article_call["overrides"] is None
    assert article_call["pipeline_steps"] == ARTICLE_PIPELINE_STEPS
    assert article_call["step_names"] == ARTICLE_PIPELINE_STEPS
    assert article_call["critical_flags"][-1] is True
    assert all(flag is False for flag in article_call["critical_flags"][:-1])


def test_app_prefix_runner_run_pipeline_defaults_to_full_mode(monkeypatch: Any) -> None:
    runner = _apps_runner()
    captured: dict[str, Any] = {}

    async def _fake_run_pipeline(
        settings: Any,
        sqlite_store: Any,
        pg_store: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["settings"] = settings
        captured["sqlite_store"] = sqlite_store
        captured["pg_store"] = pg_store
        captured.update(kwargs)
        return {"final_status": "succeeded"}

    monkeypatch.setattr(runner.orchestrator, "run_pipeline", _fake_run_pipeline)

    settings = _settings()
    sqlite_store = object()
    pg_store = object()
    result = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-default-mode",
            attempt=1,
        )
    )

    assert result == {"final_status": "succeeded"}
    assert captured["settings"] is settings
    assert captured["sqlite_store"] is sqlite_store
    assert captured["pg_store"] is pg_store
    assert captured["mode"] == "full"
    assert [name for name, _, _ in captured["step_handlers"]] == PIPELINE_STEPS
    assert list(captured["pipeline_steps"]) == PIPELINE_STEPS


def test_app_prefix_runner_run_pipeline_article_uses_article_steps_with_default_mode(
    monkeypatch: Any,
) -> None:
    runner = _apps_runner()
    captured: dict[str, Any] = {}

    async def _fake_run_pipeline(
        settings: Any,
        sqlite_store: Any,
        pg_store: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        captured["settings"] = settings
        captured["sqlite_store"] = sqlite_store
        captured["pg_store"] = pg_store
        captured.update(kwargs)
        return {"final_status": "succeeded"}

    monkeypatch.setattr(runner.orchestrator, "run_pipeline", _fake_run_pipeline)

    settings = _settings()
    sqlite_store = object()
    pg_store = object()
    result = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-article-default-mode",
            attempt=1,
            content_type="article",
        )
    )

    assert result == {"final_status": "succeeded"}
    assert captured["settings"] is settings
    assert captured["sqlite_store"] is sqlite_store
    assert captured["pg_store"] is pg_store
    assert captured["mode"] == "full"
    assert [name for name, _, _ in captured["step_handlers"]] == ARTICLE_PIPELINE_STEPS
    assert list(captured["pipeline_steps"]) == ARTICLE_PIPELINE_STEPS


def test_app_prefix_runner_run_pipeline_rejects_unsupported_content_type(monkeypatch: Any) -> None:
    runner = _apps_runner()
    called = False

    async def _fake_run_pipeline(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"final_status": "succeeded"}

    monkeypatch.setattr(runner.orchestrator, "run_pipeline", _fake_run_pipeline)

    with pytest.raises(ValueError, match="unsupported content_type: podcast"):
        asyncio.run(
            runner.run_pipeline(
                _settings(),
                object(),  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
                job_id="job-unsupported-content-type",
                attempt=1,
                content_type="podcast",
            )
        )

    assert called is False
