from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline import runner

from apps.worker.worker.pipeline.steps.llm_computer_use import build_default_computer_use_handler


def _build_ctx(tmp_path: Path, *, settings: Settings | None = None) -> runner.PipelineContext:
    current_settings = settings or Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
    )
    return runner.PipelineContext(
        settings=current_settings,
        sqlite_store=None,  # type: ignore[arg-type]
        pg_store=None,  # type: ignore[arg-type]
        job_id="job",
        attempt=1,
        job_record={},
        work_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        download_dir=tmp_path / "download",
        frames_dir=tmp_path / "frames",
        artifacts_dir=tmp_path / "artifacts",
    )


def test_step_collect_comments_applies_overrides(monkeypatch: Any, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class _FakeYouTubeCollector:
        def __init__(self, **kwargs: Any) -> None:
            captured["collector_kwargs"] = dict(kwargs)

        async def collect(self, *, source_url: str | None, video_uid: str | None) -> dict[str, Any]:
            captured["source_url"] = source_url
            captured["video_uid"] = video_uid
            return {
                "sort": "hot",
                "top_comments": [
                    {
                        "comment_id": "older",
                        "author": "old",
                        "content": "old",
                        "like_count": 99,
                        "published_at": "2024-01-01T00:00:00+00:00",
                        "replies": [
                            {"reply_id": "r1", "content": "1"},
                            {"reply_id": "r2", "content": "2"},
                        ],
                    },
                    {
                        "comment_id": "newer",
                        "author": "new",
                        "content": "new",
                        "like_count": 1,
                        "published_at": "2024-01-02T00:00:00+00:00",
                        "replies": [
                            {"reply_id": "r3", "content": "3"},
                            {"reply_id": "r4", "content": "4"},
                        ],
                    },
                ],
            }

    monkeypatch.setattr(runner, "YouTubeCommentCollector", _FakeYouTubeCollector)
    settings = Settings(
        youtube_api_key="test-key",
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
    )
    ctx = _build_ctx(tmp_path, settings=settings)
    state = {
        "platform": "youtube",
        "source_url": "https://www.youtube.com/watch?v=demo",
        "video_uid": "demo",
        "comments_policy": {"top_n": 2, "replies_per_comment": 1, "sort": "new"},
    }

    execution = asyncio.run(runner._step_collect_comments(ctx, state))

    assert execution.status == "succeeded"
    assert captured["collector_kwargs"]["top_n"] == 2
    assert captured["collector_kwargs"]["replies_per_comment"] == 1
    comments = execution.state_updates["comments"]
    assert comments["sort"] == "new"
    assert comments["top_n"] == 2
    assert comments["replies_per_comment"] == 1
    assert comments["top_comments"][0]["comment_id"] == "newer"
    assert len(comments["top_comments"][0]["replies"]) == 1


def test_step_extract_frames_applies_overrides(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / "frames").mkdir(parents=True, exist_ok=True)
    media_path = tmp_path / "video.mp4"
    media_path.write_bytes(b"fake-video")
    captured: dict[str, Any] = {}

    async def _fake_run_command(_: runner.PipelineContext, cmd: list[str]) -> runner.CommandResult:
        captured["cmd"] = list(cmd)
        for idx in range(2):
            (tmp_path / "frames" / f"frame_{idx:03d}.jpg").write_bytes(b"\xff\xd8\xff")
        return runner.CommandResult(ok=True, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)
    ctx = _build_ctx(tmp_path)
    state = {
        "media_path": str(media_path.resolve()),
        "frame_policy": {"method": "scene", "max_frames": 2},
    }

    execution = asyncio.run(runner._step_extract_frames(ctx, state))

    assert execution.status == "succeeded"
    assert execution.output["method"] == "scene"
    assert execution.output["max_frames"] == 2
    cmd = captured["cmd"]
    assert "select='gt(scene,0.3)'" in cmd
    assert cmd[cmd.index("-frames:v") + 1] == "2"


def test_step_llm_outline_applies_overrides(monkeypatch: Any, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def _fake_gemini_generate(
        _settings: Settings,
        _prompt: str,
        *,
        media_path: str | None = None,
        frame_paths: list[str] | None = None,
        llm_input_mode: str = "auto",
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_schema: dict[str, Any] | None = None,
        response_mime_type: str | None = None,
        thinking_level: str | None = None,
        include_thoughts: bool | None = None,
        use_context_cache: bool = True,
        enable_function_calling: bool = True,
        media_resolution: dict[str, Any] | str | None = None,
        max_function_call_rounds: int = 2,
        enable_computer_use: bool = False,
        computer_use_handler: Any | None = None,
        computer_use_require_confirmation: bool = True,
        computer_use_confirmed: bool = False,
        computer_use_max_steps: int = 3,
        computer_use_timeout_seconds: float = 30.0,
    ) -> tuple[str | None, str]:
        calls.append(
            {
                "media_path": media_path,
                "frame_paths": list(frame_paths or []),
                "llm_input_mode": llm_input_mode,
                "model": model,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "response_schema": response_schema,
                "response_mime_type": response_mime_type,
                "thinking_level": thinking_level,
                "include_thoughts": include_thoughts,
                "use_context_cache": use_context_cache,
                "enable_function_calling": enable_function_calling,
                "media_resolution": media_resolution,
                "max_function_call_rounds": max_function_call_rounds,
                "enable_computer_use": enable_computer_use,
                "computer_use_handler": computer_use_handler,
                "computer_use_require_confirmation": computer_use_require_confirmation,
                "computer_use_confirmed": computer_use_confirmed,
                "computer_use_max_steps": computer_use_max_steps,
                "computer_use_timeout_seconds": computer_use_timeout_seconds,
            }
        )
        return (
            '{"title":"演示视频","tldr":["梳理了接口调用链与关键异常点。"],"highlights":["通过链路追踪定位到超时根因并给出修复方向。"],"recommended_actions":["先收敛重试策略，再补充慢查询索引。"],"risk_or_pitfalls":["盲目增加重试会放大下游压力。"],"chapters":[{"chapter_no":1,"title":"问题定位","anchor":"chapter-01","start_s":0,"end_s":59,"summary":"本章说明如何通过日志与指标定位超时瓶颈。","bullets":["先看错误分布，再看下游耗时。"],"key_terms":["超时","重试"],"code_snippets":[]}],"timestamp_references":[{"ts_s":18,"label":"关键转折","reason":"开始出现稳定超时信号"}]}',
            "text",
        )

    monkeypatch.setattr(runner, "_gemini_generate", _fake_gemini_generate)
    ctx = _build_ctx(
        tmp_path,
        settings=Settings(
            pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
            pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
            gemini_computer_use_enabled=True,
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
        "llm_policy": {
            "model": "gemini-2.0-flash",
            "temperature": 0.2,
            "max_output_tokens": 1024,
            "include_thoughts": True,
            "media_resolution": {"frame": "high", "image": "medium", "pdf": "low"},
            "max_function_call_rounds": 3,
            "enable_computer_use": True,
            "computer_use_require_confirmation": False,
            "computer_use_max_steps": 5,
            "computer_use_timeout_seconds": 8.0,
        },
    }

    execution = asyncio.run(runner._step_llm_outline(ctx, state))

    assert execution.status == "succeeded"
    assert len(calls) == 1
    first = calls[0]
    assert first["model"] == "gemini-2.0-flash"
    assert first["temperature"] == 0.2
    assert first["max_output_tokens"] == 1024
    assert first["include_thoughts"] is True
    assert first["max_function_call_rounds"] == 3
    assert first["enable_computer_use"] is True
    assert callable(first["computer_use_handler"])
    assert first["computer_use_require_confirmation"] is False
    assert first["computer_use_max_steps"] == 5
    assert first["computer_use_timeout_seconds"] == 8.0
    assert first["media_resolution"] == {"frame": "high", "image": "medium", "pdf": "low"}
    computer_use_result = first["computer_use_handler"](action="click")
    assert computer_use_result["status"] == "degraded"
    assert computer_use_result["ok"] is False
    assert computer_use_result["executor"] == "playwright"
    assert computer_use_result["fallback_from"] == "playwright"
    assert computer_use_result["target"]["url"] == "https://www.youtube.com/watch?v=demo"


def test_selected_runner_suite_covers_computer_use_handler_playwright_branches(
    monkeypatch: Any,
) -> None:
    recorded: list[tuple[str, Any]] = []

    class FakePage:
        def __init__(self) -> None:
            self.url = "https://example.com/original"

        def goto(self, url: str, *, timeout: int, wait_until: str) -> None:
            recorded.append(("goto", url, timeout, wait_until))
            self.url = url

        def click(self, selector: str, *, timeout: int) -> None:
            recorded.append(("click", selector, timeout))

        def fill(self, selector: str, text: str, *, timeout: int) -> None:
            recorded.append(("fill", selector, text, timeout))

        def wait_for_timeout(self, wait_ms: int) -> None:
            recorded.append(("wait", wait_ms))

        def evaluate(self, script: str) -> None:
            recorded.append(("evaluate", script))

        def screenshot(self, *, type: str, full_page: bool) -> bytes:
            recorded.append(("screenshot", type, full_page))
            return b"png-bytes"

    class FakeBrowser:
        def __init__(self) -> None:
            self.page = FakePage()

        def new_page(self) -> FakePage:
            return self.page

        def close(self) -> None:
            recorded.append(("close",))

    class FakeChromium:
        def launch(self, *, headless: bool) -> FakeBrowser:
            recorded.append(("launch", headless))
            return FakeBrowser()

    class FakePlaywright:
        def __enter__(self) -> types.SimpleNamespace:
            return types.SimpleNamespace(chromium=FakeChromium())

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        types.SimpleNamespace(sync_playwright=FakePlaywright),
    )

    handler = build_default_computer_use_handler(
        state={
            "source_url": "https://example.com/start",
            "computer_use": {
                "executor": "playwright",
                "context": {"from": "state"},
            },
        },
        llm_policy={},
        section_policy={},
    )

    fill_result = handler(action="fill", element="#search", text="needle")
    wait_result = handler(action="wait")
    scroll_result = handler(action="scroll")
    navigate_result = handler(action="navigate", url="https://example.com/next")

    assert fill_result["status"] == "ok"
    assert wait_result["status"] == "ok"
    assert scroll_result["status"] == "ok"
    assert navigate_result["status"] == "ok"
    assert fill_result["target"]["context"] == {"from": "state"}
    assert ("fill", "#search", "needle", 8000) in recorded
    assert ("wait", 800) in recorded
    assert ("evaluate", "window.scrollBy(0, Math.max(200, window.innerHeight * 0.8));") in recorded
    assert ("goto", "https://example.com/next", 8000, "domcontentloaded") in recorded


def test_cache_signature_includes_override_policies(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    base_state = {
        "source_url": "https://www.youtube.com/watch?v=demo",
        "platform": "youtube",
        "video_uid": "demo",
        "comments_policy": {"top_n": 10, "replies_per_comment": 2, "sort": "hot"},
        "media_path": str((tmp_path / "video.mp4").resolve()),
        "frame_policy": {"method": "fps", "max_frames": 6},
        "title": "Demo",
        "metadata": {},
        "transcript": "hello",
        "comments": {"top_comments": []},
        "frames": [],
        "llm_input_mode": "auto",
        "llm_media_input": {"video_available": False, "frame_count": 0},
        "llm_policy": {"model": "gemini-1.5-flash", "temperature": None, "max_output_tokens": None},
        "outline": {},
    }

    comment_sig_1 = runner._build_step_cache_info(ctx, base_state, "collect_comments")["signature"]
    changed_comments = dict(base_state)
    changed_comments["comments_policy"] = {"top_n": 3, "replies_per_comment": 2, "sort": "hot"}
    comment_sig_2 = runner._build_step_cache_info(ctx, changed_comments, "collect_comments")[
        "signature"
    ]
    assert comment_sig_1 != comment_sig_2

    frame_sig_1 = runner._build_step_cache_info(ctx, base_state, "extract_frames")["signature"]
    changed_frames = dict(base_state)
    changed_frames["frame_policy"] = {"method": "scene", "max_frames": 6}
    frame_sig_2 = runner._build_step_cache_info(ctx, changed_frames, "extract_frames")["signature"]
    assert frame_sig_1 != frame_sig_2

    download_sig_1 = runner._build_step_cache_info(ctx, base_state, "download_media")["signature"]
    changed_download = dict(base_state)
    changed_download["metadata"] = {"duration": 3600, "language": "zh"}
    download_sig_2 = runner._build_step_cache_info(ctx, changed_download, "download_media")[
        "signature"
    ]
    assert download_sig_1 != download_sig_2

    subtitle_sig_1 = runner._build_step_cache_info(ctx, base_state, "collect_subtitles")[
        "signature"
    ]
    changed_subtitles = dict(base_state)
    changed_subtitles["metadata"] = {"duration": 5400, "language": "zh"}
    subtitle_sig_2 = runner._build_step_cache_info(ctx, changed_subtitles, "collect_subtitles")[
        "signature"
    ]
    assert subtitle_sig_1 != subtitle_sig_2

    llm_sig_1 = runner._build_step_cache_info(ctx, base_state, "llm_outline")["signature"]
    changed_llm = dict(base_state)
    changed_llm["llm_policy"] = {
        "model": "gemini-2.0-flash",
        "temperature": 0.2,
        "max_output_tokens": 1024,
    }
    llm_sig_2 = runner._build_step_cache_info(ctx, changed_llm, "llm_outline")["signature"]
    assert llm_sig_1 != llm_sig_2


def test_build_llm_policy_supports_thoughts_media_and_function_rounds(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
        gemini_include_thoughts=False,
        gemini_computer_use_enabled=True,
    )

    policy = runner._build_llm_policy(
        settings,
        {
            "llm": {
                "include_thoughts": True,
                "media_resolution": {"default": "low", "frame": "high"},
                "max_function_call_rounds": 4,
                "enable_computer_use": True,
                "computer_use_require_confirmation": False,
                "computer_use_max_steps": 6,
                "computer_use_timeout_seconds": 7.5,
            },
            "llm_outline": {
                "include_thoughts": False,
                "media_resolution": {"image": "medium"},
                "max_function_call_rounds": 1,
            },
        },
    )

    assert policy["include_thoughts"] is True
    assert policy["max_function_call_rounds"] == 4
    assert policy["enable_computer_use"] is True
    assert policy["computer_use_require_confirmation"] is False
    assert policy["computer_use_max_steps"] == 6
    assert policy["computer_use_timeout_seconds"] == 7.5
    assert policy["media_resolution"]["default"] == "low"
    assert policy["media_resolution"]["frame"] == "high"
    assert policy["outline"]["include_thoughts"] is False
    assert policy["outline"]["max_function_call_rounds"] == 1
    assert policy["outline"]["media_resolution"]["image"] == "medium"
    assert policy["digest"]["include_thoughts"] is True
    assert policy["analysis_mode"] == "advanced"
    assert policy["raw_stage"]["analysis_mode"] == "advanced"
    assert policy["raw_stage"]["video_input_required"] is True
    assert policy["raw_stage"]["review_required"] is True


def test_build_llm_policy_blocks_computer_use_override_when_globally_disabled(
    tmp_path: Path,
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifacts").resolve()),
        gemini_computer_use_enabled=False,
    )
    policy = runner._build_llm_policy(
        settings,
        {
            "llm": {"enable_computer_use": True},
            "llm_outline": {"enable_computer_use": True},
            "llm_digest": {"enable_computer_use": True},
        },
    )

    assert policy["enable_computer_use"] is False
    assert policy["outline"]["enable_computer_use"] is False
    assert policy["digest"]["enable_computer_use"] is False
    assert policy["raw_stage"]["analysis_mode"] == "advanced"
