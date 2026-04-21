from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline.steps import subtitles
from worker.pipeline.types import CommandResult, PipelineContext


class _FakeSQLiteStore:
    def mark_step_running(self, **_: Any) -> None:
        return None

    def mark_step_finished(self, **_: Any) -> None:
        return None

    def update_checkpoint(self, **_: Any) -> None:
        return None

    def get_latest_step_run(self, **_: Any) -> dict[str, Any] | None:
        return None


class _FakePGStore:
    def upsert_video_embeddings(self, **_: Any) -> int:
        return 0


def _make_ctx(tmp_path: Path, **settings_overrides: Any) -> PipelineContext:
    work_dir = tmp_path / "work"
    cache_dir = work_dir / "cache"
    download_dir = work_dir / "downloads"
    frames_dir = work_dir / "frames"
    artifacts_dir = tmp_path / "artifacts"
    cache_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        **settings_overrides,
    )
    return PipelineContext(
        settings=settings,
        sqlite_store=_FakeSQLiteStore(),  # type: ignore[arg-type]
        pg_store=_FakePGStore(),  # type: ignore[arg-type]
        job_id="job-subtitles",
        attempt=1,
        job_record={},
        work_dir=work_dir,
        cache_dir=cache_dir,
        download_dir=download_dir,
        frames_dir=frames_dir,
        artifacts_dir=artifacts_dir,
    )


def test_subtitle_helpers_parse_candidates_and_asr_files(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / "a.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<00:00:01.000>Hello\n",
        encoding="utf-8",
    )
    (download_dir / "b.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nSubtitle line\n",
        encoding="utf-8",
    )
    (download_dir / "c.ass").write_text(
        "Dialogue: 0,0:00:00.00,0:00:02.00,Hello\n", encoding="utf-8"
    )
    (download_dir / "demo.txt").write_text("preferred asr", encoding="utf-8")

    found = subtitles.subtitle_candidates(download_dir)
    transcript, used_files = subtitles.collect_subtitle_text_from_files(found, limit=2)
    assert len(found) == 3
    assert len(used_files) == 2
    assert "Subtitle line" in transcript

    asr_text = subtitles.collect_asr_output_text(download_dir, str(download_dir / "demo.mp4"))
    assert asr_text == "preferred asr"


def test_extract_youtube_video_id_variants() -> None:
    assert subtitles.extract_youtube_video_id("", "abc123") == "abc123"
    assert subtitles.extract_youtube_video_id("https://youtu.be/xyz987", "") == "xyz987"
    assert (
        subtitles.extract_youtube_video_id("https://www.youtube.com/watch?v=vvv001", "") == "vvv001"
    )
    assert (
        subtitles.extract_youtube_video_id("https://www.youtube.com/shorts/short01", "")
        == "short01"
    )
    assert subtitles.extract_youtube_video_id("https://example.com/watch?v=nope", "") == ""


def test_fetch_youtube_transcript_text_supports_multiple_sdk_shapes(monkeypatch: Any) -> None:
    module = types.ModuleType("youtube_transcript_api")

    class _StaticTranscriptApi:
        @staticmethod
        def get_transcript(video_id: str, languages: list[str]) -> list[dict[str, str]]:
            assert video_id == "vid-1"
            assert "en" in languages
            return [{"text": "line-1"}, {"text": "line-2"}]

    module.YouTubeTranscriptApi = _StaticTranscriptApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", module)
    assert subtitles.fetch_youtube_transcript_text("vid-1") == "line-1\nline-2"

    class _FetchOnlyApi:
        def fetch(self, _video_id: str, languages: list[str] | None = None) -> list[dict[str, str]]:
            if languages is not None:
                raise TypeError("legacy signature")
            return [{"text": "legacy-line"}]

    module.YouTubeTranscriptApi = _FetchOnlyApi
    assert subtitles.fetch_youtube_transcript_text("vid-2") == "legacy-line"


def test_step_collect_subtitles_prefers_downloaded_files(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path, youtube_transcript_fallback_enabled=True, asr_fallback_enabled=True)
    (ctx.download_dir / "demo.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n字幕一\n",
        encoding="utf-8",
    )

    async def _unused_run_command(_: PipelineContext, __: list[str]) -> CommandResult:
        raise AssertionError("run_command should not be called when subtitles exist")

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {"platform": "youtube", "source_url": "https://www.youtube.com/watch?v=abc"},
            run_command=_unused_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "fallback",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["transcript_provider"] == "downloaded_subtitles"
    assert "字幕一" in execution.state_updates["transcript"]


def test_step_collect_subtitles_handles_empty_youtube_transcript_and_asr_disabled(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path, youtube_transcript_fallback_enabled=True, asr_fallback_enabled=False)

    async def _unused_run_command(_: PipelineContext, __: list[str]) -> CommandResult:
        return CommandResult(ok=False, reason="binary_not_found")

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "youtube",
                "source_url": "https://www.youtube.com/watch?v=abc123xyz09",
                "video_uid": "",
                "media_path": "",
            },
            run_command=_unused_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "   ",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "asr_fallback_disabled"
    assert "youtube_transcript_empty" in execution.output["fallback_chain"]


def test_subtitle_helpers_cover_transition_skip_and_empty_asr_result(tmp_path: Path) -> None:
    download_dir = tmp_path / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / "demo.txt").write_text("   ", encoding="utf-8")

    assert subtitles.subtitle_to_text("caption --> note\nvisible line") == "visible line"
    assert subtitles.collect_asr_output_text(download_dir, str(download_dir / "demo.mp4")) == ""


def test_step_collect_subtitles_records_empty_parsed_subtitles_and_invalid_timeout_override(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(tmp_path, youtube_transcript_fallback_enabled=True, asr_fallback_enabled=False)
    (ctx.download_dir / "empty.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\n",
        encoding="utf-8",
    )

    async def _unused_run_command(_: PipelineContext, __: list[str]) -> CommandResult:
        raise AssertionError("run_command should not be called when ASR is disabled")

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "youtube",
                "source_url": "https://example.com/not-youtube",
                "video_uid": "",
                "overrides": {
                    "subtitles": {
                        "subprocess_timeout_seconds": "invalid-timeout",
                    }
                },
            },
            run_command=_unused_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "asr_fallback_disabled"
    assert "subtitle_text_empty_after_parse" in execution.output["fallback_chain"]
    assert "youtube_video_id_not_resolved" in execution.output["fallback_chain"]


def test_step_collect_subtitles_asr_fallback_success_after_missing_binary(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
        asr_model_size="base",
    )
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    calls: list[list[str]] = []

    async def _run_command(current_ctx: PipelineContext, cmd: list[str]) -> CommandResult:
        calls.append(cmd)
        if len(calls) == 1:
            return CommandResult(ok=False, reason="binary_not_found")
        (current_ctx.download_dir / "sample.txt").write_text("asr transcript", encoding="utf-8")
        return CommandResult(ok=True)

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": str(media_path.resolve()),
            },
            run_command=_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert len(calls) == 2
    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["transcript_provider"] == "asr_fallback"
    assert execution.state_updates["transcript"] == "asr transcript"


def test_step_collect_subtitles_retries_after_empty_asr_output(tmp_path: Path) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
    )
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    call_count = 0

    async def _run_command(current_ctx: PipelineContext, __: list[str]) -> CommandResult:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            (current_ctx.download_dir / "sample.txt").write_text(
                "second pass transcript", encoding="utf-8"
            )
        return CommandResult(ok=True)

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": str(media_path.resolve()),
            },
            run_command=_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert call_count == 2
    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["transcript_provider"] == "asr_fallback"
    assert execution.state_updates["transcript"] == "second pass transcript"


def test_step_collect_subtitles_subtitle_override_enables_asr_when_default_disabled(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=False,
        asr_model_size="small",
    )
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    seen_commands: list[list[str]] = []

    async def _run_command(current_ctx: PipelineContext, cmd: list[str]) -> CommandResult:
        seen_commands.append(cmd)
        (current_ctx.download_dir / "sample.txt").write_text(
            "override transcript",
            encoding="utf-8",
        )
        return CommandResult(ok=True)

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": str(media_path.resolve()),
                "overrides": {
                    "subtitles": {
                        "asr_fallback_enabled": True,
                        "asr_model_size": "tiny",
                        "subprocess_timeout_seconds": 420,
                    }
                },
            },
            run_command=_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["transcript_provider"] == "asr_fallback"
    assert execution.output["asr_model_size"] == "tiny"
    assert execution.output["subprocess_timeout_seconds"] == 420
    assert execution.state_updates["transcript"] == "override transcript"
    assert any("tiny" in arg for cmd in seen_commands for arg in cmd)
    assert seen_commands


def test_step_collect_subtitles_breaks_on_non_binary_asr_failure(tmp_path: Path) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
    )
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    call_count = 0

    async def _run_command(_: PipelineContext, __: list[str]) -> CommandResult:
        nonlocal call_count
        call_count += 1
        return CommandResult(ok=False, reason="non_zero_exit")

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": str(media_path.resolve()),
            },
            run_command=_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert call_count == 1
    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "asr_failed:non_zero_exit"


def test_step_collect_subtitles_escalates_model_when_long_cjk_asr_quality_is_low(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
        asr_model_size="tiny",
    )
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    seen_models: list[str] = []

    async def _run_command(current_ctx: PipelineContext, cmd: list[str]) -> CommandResult:
        model = cmd[cmd.index("--model") + 1]
        seen_models.append(model)
        transcript = (
            "你好"
            if model in {"tiny", "base"}
            else "\n".join(f"这是第{idx}句足够长的中文转写结果。" for idx in range(160))
        )
        (current_ctx.download_dir / "sample.txt").write_text(transcript, encoding="utf-8")
        return CommandResult(ok=True)

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": str(media_path.resolve()),
                "metadata": {
                    "duration": 5400,
                    "title": "中文长视频课程",
                    "description": "系统设计深入讲解",
                    "language": "zh",
                },
            },
            run_command=_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["transcript_provider"] == "asr_fallback"
    assert execution.output["asr_model_size"] in {"small", "medium"}
    assert execution.output["asr_quality"]["status"] == "passed"
    assert len(seen_models) >= 2
    assert seen_models[0] in {"base", "small"}


def test_step_collect_subtitles_marks_asr_quality_insufficient_when_escalation_exhausted(
    tmp_path: Path,
) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
        asr_model_size="tiny",
    )
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    seen_models: list[str] = []

    async def _run_command(current_ctx: PipelineContext, cmd: list[str]) -> CommandResult:
        model = cmd[cmd.index("--model") + 1]
        seen_models.append(model)
        (current_ctx.download_dir / "sample.txt").write_text("你好", encoding="utf-8")
        return CommandResult(ok=True)

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": str(media_path.resolve()),
                "metadata": {
                    "duration": 7200,
                    "title": "中文长视频课程",
                    "description": "系统设计深入讲解",
                    "language": "zh",
                },
            },
            run_command=_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "asr_quality_insufficient"
    assert execution.output["asr_quality"]["status"] == "review"
    assert len(seen_models) >= 2


def test_step_collect_subtitles_reports_missing_media_path_for_asr(tmp_path: Path) -> None:
    ctx = _make_ctx(
        tmp_path,
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
    )

    async def _unused_run_command(_: PipelineContext, __: list[str]) -> CommandResult:
        raise AssertionError("run_command should not be called when media_path is missing")

    execution = asyncio.run(
        subtitles.step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "media_path": "",
            },
            run_command=_unused_run_command,
            fetch_youtube_transcript_text_fn=lambda _video_id: "",
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "asr_media_path_missing"
    assert "asr_media_path_missing" in execution.output["fallback_chain"]
