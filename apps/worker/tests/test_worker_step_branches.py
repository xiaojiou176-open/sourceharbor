from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from worker.config import Settings
from worker.pipeline.steps.comments import step_collect_comments
from worker.pipeline.steps.frames import step_extract_frames
from worker.pipeline.steps.subtitles import step_collect_subtitles
from worker.pipeline.types import CommandResult


def _build_ctx(tmp_path: Path, *, youtube_api_key: str | None = "test-key") -> Any:
    settings = SimpleNamespace(
        comments_top_n=10,
        comments_replies_per_comment=2,
        comments_request_timeout_seconds=3.0,
        request_retry_attempts=1,
        request_retry_backoff_seconds=0.1,
        bilibili_cookie=None,
        youtube_api_key=youtube_api_key,
        pipeline_frame_interval_seconds=5,
        pipeline_max_frames=8,
    )
    return SimpleNamespace(settings=settings, frames_dir=tmp_path)


def _build_subtitle_ctx(tmp_path: Path, *, settings: Settings | None = None) -> Any:
    work_dir = tmp_path / "work"
    download_dir = work_dir / "downloads"
    work_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    current_settings = settings or Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
    )
    return SimpleNamespace(settings=current_settings, download_dir=download_dir)


class _FailingCollector:
    def __init__(self, **_: Any) -> None:
        pass

    async def collect(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("collector boom")


def test_step_collect_comments_bilibili_failure_degrades(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    execution = asyncio.run(
        step_collect_comments(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx",
                "video_uid": "BV1xx",
                "comments_policy": {"sort": "newest"},
            },
            bilibili_collector_cls=_FailingCollector,
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "comments_collection_failed_degraded"
    assert execution.output["provider"] == "bilibili"
    assert execution.state_updates["comments"]["top_comments"] == []


def test_step_collect_comments_youtube_failure_degrades(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path, youtube_api_key="yt-key")
    execution = asyncio.run(
        step_collect_comments(
            ctx,
            {
                "platform": "youtube",
                "source_url": "https://www.youtube.com/watch?v=abc123xyz09",
                "video_uid": "abc123xyz09",
            },
            youtube_collector_cls=_FailingCollector,
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "youtube_comments_collection_failed_degraded"
    assert execution.output["provider"] == "youtube_data_api"


def test_step_collect_comments_unsupported_platform_is_skipped(tmp_path: Path) -> None:
    ctx = _build_ctx(tmp_path)
    execution = asyncio.run(
        step_collect_comments(
            ctx,
            {
                "platform": "vimeo",
                "source_url": "https://vimeo.com/123",
                "video_uid": "123",
            },
        )
    )

    assert execution.status == "skipped"
    assert execution.degraded is True
    assert execution.reason == "comments_collection_skipped_platform_unsupported"


def test_step_collect_subtitles_bilibili_supported_defaults_to_asr_fallback(
    tmp_path: Path,
) -> None:
    ctx = _build_subtitle_ctx(tmp_path)
    media_path = ctx.download_dir / "sample.mp4"
    media_path.write_bytes(b"video")
    seen_commands: list[list[str]] = []

    async def _run_command(current_ctx: Any, cmd: list[str]) -> CommandResult:
        seen_commands.append(cmd)
        (current_ctx.download_dir / "sample.txt").write_text(
            "default asr transcript",
            encoding="utf-8",
        )
        return CommandResult(ok=True)

    execution = asyncio.run(
        step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "video_uid": "BV1xx411c7mD",
                "media_path": str(media_path.resolve()),
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
    assert execution.state_updates["transcript"] == "default asr transcript"
    assert seen_commands


def test_step_extract_frames_media_missing_skips() -> None:
    async def _never_called(_ctx: Any, _cmd: list[str]) -> CommandResult:
        raise AssertionError("run_command should not be called")

    execution = asyncio.run(step_extract_frames(_build_ctx(Path()), {}, run_command=_never_called))

    assert execution.status == "skipped"
    assert execution.reason == "media_path_missing"
    assert execution.state_updates["frames"] == []


def test_step_extract_frames_command_failure_and_no_output(tmp_path: Path) -> None:
    async def _missing_ffmpeg(_ctx: Any, cmd: list[str]) -> CommandResult:
        assert "fps=1/5" in cmd
        return CommandResult(ok=False, reason="binary_not_found", stderr="ffmpeg missing")

    skipped = asyncio.run(
        step_extract_frames(
            _build_ctx(tmp_path),
            {"media_path": str(tmp_path / "input.mp4"), "frame_policy": {"method": "invalid"}},
            run_command=_missing_ffmpeg,
        )
    )
    assert skipped.status == "skipped"
    assert skipped.reason == "binary_not_found"

    async def _other_failure(_ctx: Any, _cmd: list[str]) -> CommandResult:
        return CommandResult(ok=False, reason="ffmpeg_failed", stderr="decode error")

    failed = asyncio.run(
        step_extract_frames(
            _build_ctx(tmp_path),
            {"media_path": str(tmp_path / "input.mp4"), "frame_policy": {"method": "fps"}},
            run_command=_other_failure,
        )
    )
    assert failed.status == "failed"
    assert failed.reason == "ffmpeg_failed"

    async def _ok_no_frames(_ctx: Any, _cmd: list[str]) -> CommandResult:
        return CommandResult(ok=True)

    no_frames = asyncio.run(
        step_extract_frames(
            _build_ctx(tmp_path),
            {"media_path": str(tmp_path / "input.mp4")},
            run_command=_ok_no_frames,
        )
    )
    assert no_frames.status == "failed"
    assert no_frames.reason == "frame_not_generated"
