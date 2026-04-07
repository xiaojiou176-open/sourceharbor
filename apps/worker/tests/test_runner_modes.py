from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline import runner


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


def _patch_stub_steps(monkeypatch: Any, tmp_path: Path) -> None:
    async def _fetch(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"provider": "stub"},
            state_updates={"metadata": {"title": "Demo", "duration_s": 120}},
        )

    async def _download(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"mode": "media"},
            state_updates={
                "media_path": str((tmp_path / "video.mp4").resolve()),
                "download_mode": "media",
            },
        )

    async def _subtitles(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"subtitle_files": 1},
            state_updates={"transcript": "hello", "subtitle_files": ["demo.vtt"]},
        )

    async def _comments(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"count": 1},
            state_updates={
                "comments": {
                    "sort": "hot",
                    "top_n": 10,
                    "replies_per_comment": 2,
                    "top_comments": [
                        {
                            "comment_id": "c1",
                            "author": "alice",
                            "content": "great",
                            "like_count": 7,
                            "replies": [],
                        }
                    ],
                    "fetched_at": "2024-01-01T00:00:00+00:00",
                }
            },
        )

    async def _frames(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"frames": 1},
            state_updates={
                "frames": [{"path": str((tmp_path / "f1.jpg").resolve()), "timestamp_s": 10}]
            },
        )

    async def _outline(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"provider": "stub"},
            state_updates={
                "outline": {
                    "title": "Demo",
                    "tldr": [],
                    "highlights": [],
                    "recommended_actions": [],
                    "risk_or_pitfalls": [],
                    "chapters": [],
                    "timestamp_references": [],
                    "generated_by": "stub",
                    "generated_at": "2024-01-01T00:00:00+00:00",
                }
            },
        )

    async def _digest(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"provider": "stub"},
            state_updates={
                "digest": {
                    "title": "Demo",
                    "summary": "summary",
                    "tldr": [],
                    "highlights": [],
                    "action_items": [],
                    "code_blocks": [],
                    "timestamp_references": [],
                    "fallback_notes": [],
                    "generated_by": "stub",
                    "generated_at": "2024-01-01T00:00:00+00:00",
                }
            },
        )

    async def _write(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"artifact_dir": str((tmp_path / "artifacts").resolve())},
            state_updates={
                "artifact_dir": str((tmp_path / "artifacts").resolve()),
                "artifacts": {"digest": str((tmp_path / "artifacts" / "digest.md").resolve())},
            },
        )

    async def _embeddings(_: runner.PipelineContext, __: dict[str, Any]) -> runner.StepExecution:
        return runner.StepExecution(
            status="succeeded",
            output={"provider": "stub", "stored_count": 2},
            state_updates={
                "embeddings": {
                    "provider": "stub",
                    "stored_count": 2,
                    "retrievable": True,
                }
            },
        )

    monkeypatch.setattr(runner, "_step_fetch_metadata", _fetch)
    monkeypatch.setattr(runner, "_step_download_media", _download)
    monkeypatch.setattr(runner, "_step_collect_subtitles", _subtitles)
    monkeypatch.setattr(runner, "_step_collect_comments", _comments)
    monkeypatch.setattr(runner, "_step_extract_frames", _frames)
    monkeypatch.setattr(runner, "_step_llm_outline", _outline)
    monkeypatch.setattr(runner, "_step_llm_digest", _digest)
    monkeypatch.setattr(runner, "_step_build_embeddings", _embeddings)
    monkeypatch.setattr(runner, "_step_write_artifacts", _write)


def _make_settings(tmp_path: Path) -> Settings:
    return Settings(
        pipeline_workspace_dir=str((tmp_path / "workspace").resolve()),
        pipeline_artifact_root=str((tmp_path / "artifact-root").resolve()),
        pipeline_llm_input_mode="auto",
    )


def test_run_pipeline_text_only_mode_skips_media_steps(monkeypatch: Any, tmp_path: Path) -> None:
    _patch_stub_steps(monkeypatch, tmp_path)
    settings = _make_settings(tmp_path)
    sqlite_store = _FakeSQLiteStore()
    pg_store = _FakePGStore()

    result = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-text-only",
            attempt=1,
            mode="text_only",
        )
    )

    assert result["mode"] == "text_only"
    assert result["steps"]["download_media"]["status"] == "skipped"
    assert result["steps"]["download_media"]["reason"] == "mode_matrix_skip"
    assert result["steps"]["collect_subtitles"]["status"] == "skipped"
    assert result["steps"]["extract_frames"]["status"] == "skipped"
    assert result["llm_media_input"] == {"video_available": False, "frame_count": 0}


def test_run_pipeline_refresh_comments_forces_target_steps(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _patch_stub_steps(monkeypatch, tmp_path)
    settings = _make_settings(tmp_path)
    sqlite_store = _FakeSQLiteStore()
    pg_store = _FakePGStore()

    asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-refresh-comments",
            attempt=1,
            mode="full",
        )
    )
    second = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-refresh-comments",
            attempt=1,
            mode="refresh_comments",
        )
    )

    assert second["mode"] == "refresh_comments"
    assert second["steps"]["fetch_metadata"]["status"] == "skipped"
    assert second["steps"]["collect_comments"]["status"] == "succeeded"
    assert second["steps"]["llm_outline"]["status"] == "succeeded"
    assert second["steps"]["llm_digest"]["status"] == "succeeded"
    assert second["steps"]["write_artifacts"]["status"] == "succeeded"


def test_run_pipeline_refresh_llm_forces_only_llm_steps(monkeypatch: Any, tmp_path: Path) -> None:
    _patch_stub_steps(monkeypatch, tmp_path)
    settings = _make_settings(tmp_path)
    sqlite_store = _FakeSQLiteStore()
    pg_store = _FakePGStore()

    asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-refresh-llm",
            attempt=1,
            mode="full",
        )
    )
    second = asyncio.run(
        runner.run_pipeline(
            settings,
            sqlite_store,  # type: ignore[arg-type]
            pg_store,  # type: ignore[arg-type]
            job_id="job-refresh-llm",
            attempt=1,
            mode="refresh_llm",
        )
    )

    assert second["mode"] == "refresh_llm"
    assert second["steps"]["collect_comments"]["status"] == "skipped"
    assert second["steps"]["llm_outline"]["status"] == "succeeded"
    assert second["steps"]["llm_digest"]["status"] == "succeeded"
    assert second["steps"]["write_artifacts"]["status"] == "succeeded"
