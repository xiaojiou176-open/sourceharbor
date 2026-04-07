from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from worker.config import Settings
from worker.pipeline.steps.embedding import EMBEDDING_DIMENSION, step_build_embeddings
from worker.pipeline.types import PipelineContext


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
    def __init__(self) -> None:
        self.last_write: dict[str, Any] | None = None

    def upsert_video_embeddings(
        self,
        *,
        video_id: str,
        job_id: str,
        model: str,
        items: list[dict[str, Any]],
    ) -> int:
        self.last_write = {
            "video_id": video_id,
            "job_id": job_id,
            "model": model,
            "items": items,
        }
        return len(items)


class _FakePGStoreTableMissing(_FakePGStore):
    def upsert_video_embeddings(
        self,
        *,
        video_id: str,
        job_id: str,
        model: str,
        items: list[dict[str, Any]],
    ) -> int:
        self.last_write = {
            "video_id": video_id,
            "job_id": job_id,
            "model": model,
            "items": items,
        }
        return 0


def _make_ctx(tmp_path: Path, *, pg_store: _FakePGStore | None = None) -> PipelineContext:
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
            gemini_api_key="test-key",
        ),
        sqlite_store=_FakeSQLiteStore(),  # type: ignore[arg-type]
        pg_store=pg_store or _FakePGStore(),  # type: ignore[arg-type]
        job_id="job-embedding",
        attempt=1,
        job_record={"video_id": "00000000-0000-0000-0000-000000000123"},
        work_dir=work_dir,
        cache_dir=cache_dir,
        download_dir=download_dir,
        frames_dir=frames_dir,
        artifacts_dir=artifacts_dir,
    )


def test_step_build_embeddings_writes_transcript_and_outline_chunks(tmp_path: Path) -> None:
    pg_store = _FakePGStore()
    ctx = _make_ctx(tmp_path, pg_store=pg_store)

    outline = {
        "title": "Demo",
        "highlights": ["first", "second"],
        "chapters": [
            {
                "title": "Part 1",
                "summary": "overview",
                "bullets": ["alpha", "beta"],
            }
        ],
    }
    state = {
        "transcript": "line-1\nline-2\nline-3",
        "outline": outline,
    }

    def _fake_embed(*_: Any, **kwargs: Any) -> list[list[float]]:
        texts = list(kwargs.get("texts") or _[1])
        return [[0.01] * EMBEDDING_DIMENSION for _ in texts]

    execution = asyncio.run(step_build_embeddings(ctx, state, gemini_embed_texts_fn=_fake_embed))

    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["stored_count"] >= 2
    assert execution.state_updates["embeddings"]["retrievable"] is True
    assert pg_store.last_write is not None
    assert pg_store.last_write["video_id"] == "00000000-0000-0000-0000-000000000123"
    assert pg_store.last_write["job_id"] == "job-embedding"
    assert len(pg_store.last_write["items"]) >= 2


def test_step_build_embeddings_degrades_when_provider_unavailable(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    state = {
        "transcript": "line-1\nline-2",
        "outline": {"title": "Demo", "highlights": ["x"], "chapters": []},
    }

    def _raise_embed(*_: Any, **__: Any) -> list[list[float]]:
        raise RuntimeError("embedding_provider_unavailable:boom")

    execution = asyncio.run(step_build_embeddings(ctx, state, gemini_embed_texts_fn=_raise_embed))

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "embedding_provider_unavailable"
    assert execution.output["stored_count"] == 0
    assert execution.state_updates["embeddings"]["retrievable"] is False


def test_step_build_embeddings_handles_store_unavailable_table(tmp_path: Path) -> None:
    pg_store = _FakePGStoreTableMissing()
    ctx = _make_ctx(tmp_path, pg_store=pg_store)
    state = {
        "transcript": "line-1\nline-2",
        "outline": {"title": "Demo", "highlights": ["x"], "chapters": []},
    }

    def _fake_embed(*_: Any, **kwargs: Any) -> list[list[float]]:
        texts = list(kwargs.get("texts") or _[1])
        return [[0.01] * EMBEDDING_DIMENSION for _ in texts]

    execution = asyncio.run(step_build_embeddings(ctx, state, gemini_embed_texts_fn=_fake_embed))

    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["stored_count"] == 0
    assert execution.state_updates["embeddings"]["retrievable"] is False
