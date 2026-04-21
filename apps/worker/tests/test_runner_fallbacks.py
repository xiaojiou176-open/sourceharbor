from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from worker.config import Settings
from worker.pipeline import runner


def _build_ctx(tmp_path: Path, *, settings: Settings) -> runner.PipelineContext:
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


def test_step_download_media_bilibili_auto_falls_back_to_bbdown(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        bilibili_downloader="auto",
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    async def _fake_run_command(
        current_ctx: runner.PipelineContext, cmd: list[str]
    ) -> runner.CommandResult:
        if cmd and cmd[0] == "yt-dlp":
            return runner.CommandResult(
                ok=False, returncode=1, stderr="yt failed", reason="non_zero_exit"
            )
        media_path = current_ctx.download_dir / "bili_video.mp4"
        media_path.write_bytes(b"fake-video")
        return runner.CommandResult(
            ok=True, returncode=0, stdout=str(media_path.resolve()), stderr=""
        )

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)

    execution = asyncio.run(
        runner._step_download_media(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            },
        )
    )

    assert execution.status == "succeeded"
    assert execution.output["provider"] == "bbdown"
    assert execution.state_updates["download_mode"] == "media"
    assert str(execution.state_updates["media_path"]).endswith(".mp4")


def test_step_download_media_bilibili_force_ytdlp_no_fallback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        bilibili_downloader="yt-dlp",
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    async def _fake_run_command(_: runner.PipelineContext, __: list[str]) -> runner.CommandResult:
        return runner.CommandResult(
            ok=False, returncode=1, stderr="yt failed", reason="non_zero_exit"
        )

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)

    execution = asyncio.run(
        runner._step_download_media(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            },
        )
    )

    assert execution.status == "failed"
    assert execution.output["providers_tried"] == ["yt-dlp"]
    assert execution.state_updates["download_mode"] == "text_only"


def test_step_download_media_bilibili_extends_timeout_for_long_video(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        bilibili_downloader="yt-dlp",
        pipeline_subprocess_timeout_seconds=180,
    )
    ctx = _build_ctx(tmp_path, settings=settings)
    seen_timeouts: list[int] = []

    async def _fake_run_command(
        current_ctx: runner.PipelineContext, __: list[str]
    ) -> runner.CommandResult:
        seen_timeouts.append(current_ctx.settings.pipeline_subprocess_timeout_seconds)
        media_path = current_ctx.download_dir / "bili_video.mp4"
        media_path.write_bytes(b"fake-video")
        return runner.CommandResult(
            ok=True, returncode=0, stdout=str(media_path.resolve()), stderr=""
        )

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)

    execution = asyncio.run(
        runner._step_download_media(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "metadata": {
                    "duration": 2811,
                    "title": "中文长视频访谈",
                    "language": "zh",
                },
            },
        )
    )

    assert execution.status == "succeeded"
    assert seen_timeouts
    assert seen_timeouts[0] >= 600


def test_step_download_media_bilibili_passes_cookie_header_to_ytdlp(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        bilibili_downloader="yt-dlp",
        bilibili_cookie="SESSDATA=demo",
    )
    ctx = _build_ctx(tmp_path, settings=settings)
    seen_cmds: list[list[str]] = []

    async def _fake_run_command(
        current_ctx: runner.PipelineContext, cmd: list[str]
    ) -> runner.CommandResult:
        del current_ctx
        seen_cmds.append(cmd)
        media_path = ctx.download_dir / "bili_video.mp4"
        media_path.write_bytes(b"fake-video")
        return runner.CommandResult(
            ok=True, returncode=0, stdout=str(media_path.resolve()), stderr=""
        )

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)

    execution = asyncio.run(
        runner._step_download_media(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            },
        )
    )

    assert execution.status == "succeeded"
    assert seen_cmds
    assert "--add-header" in seen_cmds[0]
    assert "Cookie: SESSDATA=demo" in seen_cmds[0]


def test_step_download_media_bilibili_keeps_primary_timeout_reason_when_fallback_missing(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        bilibili_downloader="auto",
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    async def _fake_run_command(_: runner.PipelineContext, cmd: list[str]) -> runner.CommandResult:
        if cmd and cmd[0] == "yt-dlp":
            return runner.CommandResult(
                ok=False, returncode=None, stderr="timed out", reason="timeout"
            )
        return runner.CommandResult(
            ok=False, returncode=None, stderr="missing", reason="binary_not_found"
        )

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)

    execution = asyncio.run(
        runner._step_download_media(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "metadata": {
                    "duration": 2811,
                    "title": "中文长视频访谈",
                    "language": "zh",
                },
            },
        )
    )

    assert execution.status == "failed"
    assert execution.reason == "timeout"
    assert execution.output["attempts"][0]["reason"] == "timeout"
    assert execution.output["attempts"][1]["reason"] == "binary_not_found"


def test_step_collect_subtitles_uses_youtube_transcript_fallback(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        youtube_transcript_fallback_enabled=True,
        asr_fallback_enabled=False,
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    monkeypatch.setattr(runner, "_fetch_youtube_transcript_text", lambda _: "line1\nline2")

    execution = asyncio.run(
        runner._step_collect_subtitles(
            ctx,
            {
                "platform": "youtube",
                "source_url": "https://www.youtube.com/watch?v=abc123xyz09",
                "video_uid": "",
                "media_path": "",
            },
        )
    )

    assert execution.status == "succeeded"
    assert execution.output["transcript_provider"] == "youtube_transcript_fallback"
    assert execution.state_updates["transcript"] == "line1\nline2"
    assert execution.state_updates["subtitle_files"] == []


def test_step_collect_subtitles_asr_missing_binary_degrades(
    monkeypatch: Any, tmp_path: Path
) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        youtube_transcript_fallback_enabled=False,
        asr_fallback_enabled=True,
        asr_model_size="small",
    )
    ctx = _build_ctx(tmp_path, settings=settings)
    media_path = ctx.download_dir / "demo.mp4"
    media_path.write_bytes(b"fake-media")

    async def _fake_run_command(_: runner.PipelineContext, __: list[str]) -> runner.CommandResult:
        return runner.CommandResult(ok=False, reason="binary_not_found")

    monkeypatch.setattr(runner, "_run_command", _fake_run_command)

    execution = asyncio.run(
        runner._step_collect_subtitles(
            ctx,
            {
                "platform": "bilibili",
                "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                "video_uid": "BV1xx411c7mD",
                "media_path": str(media_path.resolve()),
            },
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.state_updates["transcript"] == ""
    assert "asr_failed:binary_not_found" in (execution.reason or "")


def test_settings_from_env_reads_new_fallback_flags(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("SQLITE_PATH", str((tmp_path / "state.db").resolve()))
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/sourceharbor"
    )
    monkeypatch.setenv("TEMPORAL_TARGET_HOST", "localhost:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "default")
    monkeypatch.setenv("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
    monkeypatch.setenv("PIPELINE_WORKSPACE_DIR", str((tmp_path / "workspace").resolve()))
    monkeypatch.setenv("PIPELINE_ARTIFACT_ROOT", str((tmp_path / "artifact-root").resolve()))
    monkeypatch.setenv("BILIBILI_DOWNLOADER", "bbdown")
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_FALLBACK_ENABLED", "false")
    monkeypatch.setenv("ASR_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("ASR_MODEL_SIZE", "base")
    monkeypatch.setenv("GEMINI_STRICT_SCHEMA_MODE", "false")
    monkeypatch.setenv("PIPELINE_LLM_INCLUDE_FRAMES", "true")
    monkeypatch.setenv("PIPELINE_LLM_HARD_REQUIRED", "false")
    monkeypatch.setenv("PIPELINE_LLM_FAIL_ON_PROVIDER_ERROR", "false")
    monkeypatch.setenv("PIPELINE_LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("PIPELINE_RETRY_TRANSIENT_ATTEMPTS", "7")
    monkeypatch.setenv("PIPELINE_RETRY_TRANSIENT_BACKOFF_SECONDS", "0.75")

    settings = Settings.from_env()

    assert settings.bilibili_downloader == "bbdown"
    assert settings.youtube_transcript_fallback_enabled is False
    assert settings.asr_fallback_enabled is True
    assert settings.asr_model_size == "base"
    assert settings.gemini_strict_schema_mode is False
    assert settings.pipeline_llm_include_frames is True
    assert settings.pipeline_llm_hard_required is False
    assert settings.pipeline_llm_fail_on_provider_error is False
    assert settings.pipeline_llm_max_retries == 2
    assert settings.pipeline_retry_transient_attempts == 7
    assert settings.pipeline_retry_transient_backoff_seconds == 0.75


def test_step_write_artifacts_renders_embedded_screenshots(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
    )
    ctx = _build_ctx(tmp_path, settings=settings)
    source_frame = ctx.frames_dir / "source_frame.jpg"
    source_frame.write_bytes(b"frame")

    execution = asyncio.run(
        runner._step_write_artifacts(
            ctx,
            {
                "title": "Demo",
                "source_url": "https://www.youtube.com/watch?v=abc123xyz09",
                "platform": "youtube",
                "video_uid": "abc123xyz09",
                "metadata": {"title": "Demo"},
                "outline": {},
                "digest": {"summary": "summary"},
                "comments": {},
                "transcript": "hello",
                "degradations": [],
                "frames": [{"path": str(source_frame.resolve()), "timestamp_s": 10}],
            },
        )
    )

    assert execution.status == "succeeded"
    digest_content = (ctx.artifacts_dir / "digest.md").read_text(encoding="utf-8")
    assert "## Key Frames" in digest_content
    assert "## Notes (Degradations / Missing Inputs)" in digest_content
    assert (
        "![frame-1](/api/v1/artifacts/assets?job_id=job&path=frames/frame_001.jpg)"
        in digest_content
    )

    meta_payload = json.loads((ctx.artifacts_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta_payload["frame_files"] == ["frames/frame_001.jpg"]


def test_step_write_artifacts_low_evidence_mode_blocks_fabricated_details(tmp_path: Path) -> None:
    template_path = tmp_path / "digest.md.mustache"
    template_path.write_text(
        "# {{title}}\n\n"
        "## What This Covers\n\n"
        "{{summary}}\n\n"
        "## Low-Evidence Guardrail\n\n"
        "{{fallback_notes_markdown}}\n\n"
        "## Notes (Degradations / Missing Inputs)\n\n"
        "{{degradations_markdown}}\n",
        encoding="utf-8",
    )
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        digest_template_path=str(template_path.resolve()),
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    execution = asyncio.run(
        runner._step_write_artifacts(
            ctx,
            {
                "title": "Demo",
                "source_url": "https://www.bilibili.com/video/BV1JzNUeuEEo",
                "platform": "bilibili",
                "video_uid": "BV1JzNUeuEEo",
                "metadata": {"title": "Demo"},
                "outline": {
                    "chapters": [
                        {
                            "chapter_no": 1,
                            "title": "开箱与防伪检查",
                            "start_s": 0,
                            "end_s": 60,
                            "summary": "这是模型臆测内容",
                            "bullets": ["伪造要点"],
                        }
                    ],
                    "timestamp_references": [
                        {"ts_s": 30, "label": "检查防伪标签", "reason": "臆测"}
                    ],
                },
                "digest": {
                    "summary": "这是模型臆测摘要",
                    "highlights": ["臆测高光"],
                    "action_items": ["臆测建议"],
                    "timestamp_references": [
                        {"ts_s": 30, "label": "检查防伪标签", "reason": "臆测"}
                    ],
                },
                "comments": {},
                "transcript": "",
                "degradations": [],
                "frames": [],
            },
        )
    )

    assert execution.status == "succeeded"
    digest_content = (ctx.artifacts_dir / "digest.md").read_text(encoding="utf-8")
    assert "缺少可验证证据" in digest_content
    assert "开箱与防伪检查" not in digest_content
    assert "检查防伪标签" not in digest_content
    assert "quality_gate:low_evidence_mode" in digest_content


def test_step_write_artifacts_persists_knowledge_cards_to_pg_store(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    captured: dict[str, Any] = {}

    class _FakePGStore:
        def replace_knowledge_cards(
            self, *, video_id: str, job_id: str, items: list[dict[str, Any]]
        ) -> int:
            captured["video_id"] = video_id
            captured["job_id"] = job_id
            captured["items"] = items
            return len(items)

    ctx = SimpleNamespace(**ctx.__dict__)
    ctx.pg_store = _FakePGStore()
    ctx.job_record = {"video_id": "video-1"}

    execution = asyncio.run(
        runner._step_write_artifacts(
            ctx,
            {
                "title": "Demo",
                "job_id": "job",
                "source_url": "https://www.youtube.com/watch?v=abc123xyz09",
                "platform": "youtube",
                "video_uid": "abc123xyz09",
                "metadata": {"title": "Demo"},
                "outline": {},
                "digest": {
                    "summary": "summary",
                    "highlights": ["one takeaway"],
                    "action_items": ["one action"],
                },
                "comments": {},
                "transcript": "This transcript is long enough to satisfy the evidence guard. "
                "It contains substantially more than eighty characters so knowledge cards stay aligned "
                "with the original digest payload.",
                "degradations": [],
                "frames": [],
            },
        )
    )

    assert execution.status == "succeeded"
    assert captured["video_id"] == "video-1"
    assert captured["job_id"] == "job"
    assert len(captured["items"]) >= 6
    card_types = {item["card_type"] for item in captured["items"]}
    assert {"summary", "takeaway", "action", "topic", "claim"}.issubset(card_types)
    summary_card = captured["items"][0]
    takeaway_card = captured["items"][1]
    action_card = captured["items"][2]
    topic_card = next(item for item in captured["items"] if item["card_type"] == "topic")
    claim_card = next(item for item in captured["items"] if item["card_type"] == "claim")
    assert summary_card["metadata"]["claim_kind"] == "summary"
    assert summary_card["metadata"]["confidence_label"] == "high"
    assert summary_card["metadata"]["topic_key"]
    assert takeaway_card["metadata"]["claim_kind"] == "takeaway"
    assert takeaway_card["metadata"]["source_anchor"] == "highlights[1]"
    assert action_card["metadata"]["claim_kind"] == "action"
    assert action_card["metadata"]["confidence_label"] == "medium"
    assert topic_card["metadata"]["topic_key"]
    assert topic_card["metadata"]["mentions"] >= 1
    assert claim_card["metadata"]["claim_id"]
    assert claim_card["metadata"]["claim_source_card_type"] in {"summary", "takeaway", "action"}
    assert (ctx.artifacts_dir / "knowledge_cards.json").is_file()
    knowledge_cards = json.loads(
        (ctx.artifacts_dir / "knowledge_cards.json").read_text(encoding="utf-8")
    )
    assert knowledge_cards[0]["metadata"]["claim_kind"] == "summary"
    assert knowledge_cards[1]["metadata"]["source_anchor"] == "highlights[1]"


def test_step_write_artifacts_persists_danmaku_artifact(tmp_path: Path) -> None:
    settings = Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
    )
    ctx = _build_ctx(tmp_path, settings=settings)

    execution = asyncio.run(
        runner._step_write_artifacts(
            ctx,
            {
                "title": "Demo",
                "source_url": "https://www.bilibili.com/video/BV1demo",
                "platform": "bilibili",
                "video_uid": "BV1demo",
                "metadata": {"title": "Demo", "uploader_mid": "12345"},
                "outline": {},
                "digest": {"summary": "summary"},
                "comments": {},
                "transcript": "This transcript is long enough to satisfy the evidence guard for artifacts.",
                "degradations": [],
                "frames": [],
                "danmaku": {
                    "status": "available",
                    "cid": 11,
                    "entry_count": 1,
                    "entries": [{"progress_s": 3.5, "content": "hello"}],
                },
            },
        )
    )

    assert execution.status == "succeeded"
    assert (ctx.artifacts_dir / "danmaku.json").is_file()
    danmaku_payload = json.loads((ctx.artifacts_dir / "danmaku.json").read_text(encoding="utf-8"))
    assert danmaku_payload["status"] == "available"
    assert danmaku_payload["entries"][0]["content"] == "hello"
    meta_payload = json.loads((ctx.artifacts_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta_payload["danmaku"]["entry_count"] == 1
    assert execution.output["files"]["danmaku"].endswith("danmaku.json")
