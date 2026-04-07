from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from integrations.providers.gemini import build_gemini_client, load_gemini_sdk
from worker.config import Settings
from worker.pipeline.types import PipelineContext, StepExecution

EMBEDDING_DIMENSION = 768
DEFAULT_CHUNK_CHARS = 1200
DEFAULT_CHUNK_OVERLAP = 120


def _split_long_text(text: str, *, chunk_chars: int, overlap_chars: int) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []

    chunk_size = max(300, int(chunk_chars))
    overlap = max(0, min(int(overlap_chars), chunk_size // 2))
    stride = max(1, chunk_size - overlap)

    chunks: list[str] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(length, start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start += stride
    return chunks


def _normalize_outline_text(outline: dict[str, Any]) -> str:
    title = str(outline.get("title") or "").strip()
    highlights = [
        str(item).strip() for item in outline.get("highlights") or [] if str(item).strip()
    ]
    chapters = outline.get("chapters")

    lines: list[str] = []
    if title:
        lines.append(f"Title: {title}")

    if highlights:
        lines.append("Highlights:")
        for item in highlights[:20]:
            lines.append(f"- {item}")

    if isinstance(chapters, list) and chapters:
        lines.append("Chapters:")
        for chapter in chapters[:60]:
            if not isinstance(chapter, dict):
                continue
            chapter_title = str(chapter.get("title") or "").strip()
            chapter_summary = str(chapter.get("summary") or "").strip()
            bullets = [
                str(item).strip() for item in chapter.get("bullets") or [] if str(item).strip()
            ]
            if chapter_title:
                lines.append(f"## {chapter_title}")
            if chapter_summary:
                lines.append(chapter_summary)
            for bullet in bullets[:8]:
                lines.append(f"- {bullet}")

    return "\n".join(lines).strip()


def _build_embedding_chunks(state: dict[str, Any]) -> list[dict[str, Any]]:
    transcript = str(state.get("transcript") or "").strip()
    outline = dict(state.get("outline") or {})

    chunks: list[dict[str, Any]] = []

    transcript_chunks = _split_long_text(
        transcript,
        chunk_chars=DEFAULT_CHUNK_CHARS,
        overlap_chars=DEFAULT_CHUNK_OVERLAP,
    )
    for idx, chunk in enumerate(transcript_chunks):
        chunks.append(
            {
                "content_type": "transcript",
                "chunk_index": idx,
                "chunk_text": chunk,
                "metadata": {"source": "transcript", "chunk_index": idx},
            }
        )

    outline_text = _normalize_outline_text(outline)
    outline_chunks = _split_long_text(
        outline_text,
        chunk_chars=DEFAULT_CHUNK_CHARS,
        overlap_chars=DEFAULT_CHUNK_OVERLAP,
    )
    for idx, chunk in enumerate(outline_chunks):
        chunks.append(
            {
                "content_type": "outline",
                "chunk_index": idx,
                "chunk_text": chunk,
                "metadata": {"source": "outline", "chunk_index": idx},
            }
        )

    return chunks


def _extract_embedding_values(item: Any) -> list[float] | None:
    values = getattr(item, "values", None)
    if isinstance(values, list) and values:
        return [float(v) for v in values]

    embedding = getattr(item, "embedding", None)
    if embedding is not None:
        nested = getattr(embedding, "values", None)
        if isinstance(nested, list) and nested:
            return [float(v) for v in nested]

    if isinstance(item, dict):
        item_values = item.get("values")
        if isinstance(item_values, list) and item_values:
            return [float(v) for v in item_values]
        nested_embedding = item.get("embedding")
        if isinstance(nested_embedding, dict):
            nested_values = nested_embedding.get("values")
            if isinstance(nested_values, list) and nested_values:
                return [float(v) for v in nested_values]
    return None


def gemini_embed_texts(
    settings: Settings,
    texts: list[str],
    *,
    model: str,
    output_dimensionality: int = EMBEDDING_DIMENSION,
) -> list[list[float]]:
    if not texts:
        return []
    if not settings.gemini_api_key:
        raise RuntimeError("gemini_api_key_missing")

    try:
        sdk = load_gemini_sdk()
        genai_types = sdk.genai_types
    except Exception as exc:
        raise RuntimeError(f"embedding_sdk_unavailable:{exc}") from exc

    try:
        client = build_gemini_client(api_key=settings.gemini_api_key)
    except Exception as exc:
        raise RuntimeError(f"embedding_client_init_failed:{exc}") from exc

    vectors: list[list[float]] = []
    batch_size = 16
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            response = client.models.embed_content(
                model=model,
                contents=batch,
                config=genai_types.EmbedContentConfig(output_dimensionality=output_dimensionality),
            )
        except Exception as exc:
            raise RuntimeError(f"embedding_provider_unavailable:{exc}") from exc

        items = getattr(response, "embeddings", None)
        if not isinstance(items, list) or not items:
            maybe_single = _extract_embedding_values(response)
            if maybe_single is not None:
                items = [response]
            else:
                raise RuntimeError("embedding_provider_unavailable:empty_embeddings")

        parsed = [_extract_embedding_values(item) for item in items]
        if any(item is None for item in parsed):
            raise RuntimeError("embedding_provider_unavailable:invalid_embedding_payload")

        vectors.extend([item for item in parsed if item is not None])

    if len(vectors) != len(texts):
        raise RuntimeError(
            f"embedding_provider_unavailable:mismatched_embeddings:{len(vectors)}:{len(texts)}"
        )
    return vectors


async def step_build_embeddings(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    gemini_embed_texts_fn: Callable[..., list[list[float]]] = gemini_embed_texts,
) -> StepExecution:
    chunks = _build_embedding_chunks(state)
    model = (
        str(ctx.settings.gemini_embedding_model or "gemini-embedding-001").strip()
        or "gemini-embedding-001"
    )
    video_id = str(ctx.job_record.get("video_id") or "").strip()

    if not chunks:
        return StepExecution(
            status="succeeded",
            output={
                "provider": "gemini",
                "model": model,
                "chunk_count": 0,
                "stored_count": 0,
                "retrievable": False,
            },
            state_updates={
                "embeddings": {
                    "provider": "gemini",
                    "model": model,
                    "chunk_count": 0,
                    "stored_count": 0,
                    "retrievable": False,
                }
            },
        )

    if not video_id:
        return StepExecution(
            status="succeeded",
            degraded=True,
            reason="embedding_video_id_missing",
            error="embedding_video_id_missing",
            output={
                "provider": "gemini",
                "model": model,
                "chunk_count": len(chunks),
                "stored_count": 0,
                "retrievable": False,
            },
            state_updates={
                "embeddings": {
                    "provider": "gemini",
                    "model": model,
                    "chunk_count": len(chunks),
                    "stored_count": 0,
                    "retrievable": False,
                }
            },
        )

    texts = [str(chunk["chunk_text"]) for chunk in chunks]
    try:
        vectors = await asyncio.to_thread(
            gemini_embed_texts_fn,
            ctx.settings,
            texts,
            model=model,
            output_dimensionality=EMBEDDING_DIMENSION,
        )
    except Exception as exc:
        error = str(exc) or "embedding_provider_unavailable"
        return StepExecution(
            status="succeeded",
            degraded=True,
            reason="embedding_provider_unavailable",
            error=error,
            output={
                "provider": "gemini",
                "model": model,
                "chunk_count": len(chunks),
                "stored_count": 0,
                "retrievable": False,
            },
            state_updates={
                "embeddings": {
                    "provider": "gemini",
                    "model": model,
                    "chunk_count": len(chunks),
                    "stored_count": 0,
                    "retrievable": False,
                }
            },
        )

    items: list[dict[str, Any]] = []
    for chunk, vector in zip(chunks, vectors, strict=False):
        items.append(
            {
                "content_type": str(chunk["content_type"]),
                "chunk_index": int(chunk["chunk_index"]),
                "chunk_text": str(chunk["chunk_text"]),
                "embedding": vector,
                "metadata": dict(chunk.get("metadata") or {}),
            }
        )

    try:
        stored_count = await asyncio.to_thread(
            ctx.pg_store.upsert_video_embeddings,
            video_id=video_id,
            job_id=ctx.job_id,
            model=model,
            items=items,
        )
    except Exception as exc:
        return StepExecution(
            status="succeeded",
            degraded=True,
            reason="embedding_store_write_failed",
            error=f"embedding_store_write_failed:{exc}",
            output={
                "provider": "gemini",
                "model": model,
                "chunk_count": len(chunks),
                "stored_count": 0,
                "retrievable": False,
            },
            state_updates={
                "embeddings": {
                    "provider": "gemini",
                    "model": model,
                    "chunk_count": len(chunks),
                    "stored_count": 0,
                    "retrievable": False,
                }
            },
        )

    return StepExecution(
        status="succeeded",
        output={
            "provider": "gemini",
            "model": model,
            "chunk_count": len(chunks),
            "stored_count": stored_count,
            "retrievable": stored_count > 0,
        },
        state_updates={
            "embeddings": {
                "provider": "gemini",
                "model": model,
                "chunk_count": len(chunks),
                "stored_count": stored_count,
                "retrievable": stored_count > 0,
            }
        },
    )
