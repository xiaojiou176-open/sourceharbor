from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from worker.config import Settings
from worker.pipeline.steps import embedding
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
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.writes: list[dict[str, Any]] = []

    def upsert_video_embeddings(
        self,
        *,
        video_id: str,
        job_id: str,
        model: str,
        items: list[dict[str, Any]],
    ) -> int:
        if self.should_fail:
            raise RuntimeError("store unavailable")
        self.writes.append(
            {
                "video_id": video_id,
                "job_id": job_id,
                "model": model,
                "items": items,
            }
        )
        return len(items)


def _make_ctx(
    tmp_path: Path,
    *,
    video_id: str | None = "00000000-0000-0000-0000-000000000001",
    should_fail: bool = False,
) -> PipelineContext:
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
        pg_store=_FakePGStore(should_fail=should_fail),  # type: ignore[arg-type]
        job_id="job-embedding-extra",
        attempt=1,
        job_record={"video_id": video_id} if video_id else {},
        work_dir=work_dir,
        cache_dir=cache_dir,
        download_dir=download_dir,
        frames_dir=frames_dir,
        artifacts_dir=artifacts_dir,
    )


def _install_fake_google_genai(monkeypatch: Any, *, client_cls: Any) -> None:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")
    types_module = types.ModuleType("google.genai.types")

    class _EmbedContentConfig:
        def __init__(self, output_dimensionality: int) -> None:
            self.output_dimensionality = output_dimensionality

    types_module.EmbedContentConfig = _EmbedContentConfig
    genai_module.Client = client_cls
    genai_module.types = types_module
    google_module.genai = genai_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.genai", genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", types_module)


def test_embedding_helpers_cover_chunk_building_and_value_extraction() -> None:
    assert embedding._split_long_text("", chunk_chars=1200, overlap_chars=120) == []
    chunks = embedding._split_long_text("x" * 720, chunk_chars=350, overlap_chars=400)
    assert len(chunks) >= 2

    outline_text = embedding._normalize_outline_text(
        {
            "title": "Demo",
            "highlights": ["h1", "", "h2"],
            "chapters": [
                {"title": "A", "summary": "s", "bullets": ["b1", "b2"]},
                "ignore-me",
            ],
        }
    )
    assert "Title: Demo" in outline_text
    assert "Highlights:" in outline_text
    assert "## A" in outline_text

    class _ObjValues:
        values = [1, 2]

    class _ObjEmbedding:
        embedding = types.SimpleNamespace(values=[3, 4])

    assert embedding._extract_embedding_values(_ObjValues()) == [1.0, 2.0]
    assert embedding._extract_embedding_values(_ObjEmbedding()) == [3.0, 4.0]
    assert embedding._extract_embedding_values({"values": [5, 6]}) == [5.0, 6.0]
    assert embedding._extract_embedding_values({"embedding": {"values": [7, 8]}}) == [7.0, 8.0]
    assert embedding._extract_embedding_values({"unexpected": True}) is None


def test_gemini_embed_texts_handles_empty_and_missing_key() -> None:
    settings = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_api_key="test-key",
    )
    assert embedding.gemini_embed_texts(settings, [], model="gemini-embedding-001") == []

    missing_key_settings = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_api_key=None,
    )
    with pytest.raises(RuntimeError, match="gemini_api_key_missing"):
        embedding.gemini_embed_texts(
            missing_key_settings,
            ["hello"],
            model="gemini-embedding-001",
        )


def test_gemini_embed_texts_batches_and_parses_embedding_payloads(monkeypatch: Any) -> None:
    captured_calls: list[dict[str, Any]] = []

    class _FakeModels:
        def embed_content(self, *, model: str, contents: list[str], config: Any) -> Any:
            captured_calls.append(
                {
                    "model": model,
                    "contents": list(contents),
                    "dim": int(config.output_dimensionality),
                }
            )
            vectors = [{"values": [float(idx), 1.0]} for idx, _ in enumerate(contents)]
            return types.SimpleNamespace(embeddings=vectors)

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.models = _FakeModels()

    _install_fake_google_genai(monkeypatch, client_cls=_FakeClient)
    settings = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_api_key="test-key",
    )
    texts = [f"text-{idx}" for idx in range(17)]

    vectors = embedding.gemini_embed_texts(settings, texts, model="gemini-embedding-001")

    assert len(vectors) == len(texts)
    assert len(captured_calls) == 2
    assert captured_calls[0]["dim"] == embedding.EMBEDDING_DIMENSION


def test_gemini_embed_texts_handles_single_payload_and_invalid_payload(monkeypatch: Any) -> None:
    class _SingleValueModels:
        def __init__(self, *, invalid: bool) -> None:
            self.invalid = invalid

        def embed_content(self, **_: Any) -> Any:
            if self.invalid:
                return types.SimpleNamespace(embeddings=[{"wrong": "shape"}])
            return types.SimpleNamespace(values=[0.25, 0.5])

    class _Client:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.models = _SingleValueModels(invalid=False)

    _install_fake_google_genai(monkeypatch, client_cls=_Client)
    settings = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_api_key="test-key",
    )
    vectors = embedding.gemini_embed_texts(settings, ["a"], model="gemini-embedding-001")
    assert vectors == [[0.25, 0.5]]

    class _InvalidClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.models = _SingleValueModels(invalid=True)

    _install_fake_google_genai(monkeypatch, client_cls=_InvalidClient)
    with pytest.raises(RuntimeError, match="invalid_embedding_payload"):
        embedding.gemini_embed_texts(settings, ["a"], model="gemini-embedding-001")


def test_gemini_embed_texts_detects_mismatched_embedding_count(monkeypatch: Any) -> None:
    class _MismatchedModels:
        def embed_content(self, **_: Any) -> Any:
            return types.SimpleNamespace(embeddings=[{"values": [0.1, 0.2]}])

    class _Client:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.models = _MismatchedModels()

    _install_fake_google_genai(monkeypatch, client_cls=_Client)
    settings = Settings(
        pipeline_workspace_dir="/tmp/workspace",
        pipeline_artifact_root="/tmp/artifacts",
        gemini_api_key="test-key",
    )
    with pytest.raises(RuntimeError, match="mismatched_embeddings"):
        embedding.gemini_embed_texts(settings, ["a", "b"], model="gemini-embedding-001")


def test_step_build_embeddings_handles_no_chunks_and_missing_video_id(tmp_path: Path) -> None:
    no_chunks_ctx = _make_ctx(tmp_path / "no-chunks")
    no_chunks_execution = asyncio.run(
        embedding.step_build_embeddings(no_chunks_ctx, {"transcript": "", "outline": {}})
    )
    assert no_chunks_execution.status == "succeeded"
    assert no_chunks_execution.output["chunk_count"] == 0

    missing_id_ctx = _make_ctx(tmp_path / "missing-id", video_id=None)
    missing_id_execution = asyncio.run(
        embedding.step_build_embeddings(
            missing_id_ctx,
            {"transcript": "some transcript", "outline": {"title": "Demo"}},
            gemini_embed_texts_fn=lambda *_args, **_kwargs: [[0.1] * embedding.EMBEDDING_DIMENSION],
        )
    )
    assert missing_id_execution.status == "succeeded"
    assert missing_id_execution.degraded is True
    assert missing_id_execution.reason == "embedding_video_id_missing"


def test_step_build_embeddings_degrades_when_store_write_fails(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path / "store-fail", should_fail=True)
    execution = asyncio.run(
        embedding.step_build_embeddings(
            ctx,
            {"transcript": "line-1", "outline": {"title": "Demo"}},
            gemini_embed_texts_fn=lambda *_args, **_kwargs: [[0.1] * embedding.EMBEDDING_DIMENSION],
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is True
    assert execution.reason == "embedding_store_write_failed"
    assert execution.output["stored_count"] == 0
