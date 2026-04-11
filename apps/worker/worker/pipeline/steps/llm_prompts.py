from __future__ import annotations

import json
from typing import Any

from worker.pipeline.runner_rendering import (
    build_comments_prompt_context,
    build_frames_prompt_context,
)
from worker.pipeline.step_executor import jsonable


def build_translation_prompt(payload: dict[str, Any], *, schema_label: str) -> str:
    return "\n\n".join(
        [
            "Translate every reader-facing natural-language string in the JSON below into Simplified Chinese.",
            "Keep JSON keys, structure, numbers, timestamps, URLs, and IDs unchanged.",
            "If the payload includes code snippets such as code_snippets.snippet or code_blocks.snippet, do not translate the code itself.",
            "Return JSON only. Do not add explanations.",
            f"Schema: {schema_label}",
            json.dumps(jsonable(payload), ensure_ascii=False),
        ]
    )


def build_outline_prompt(
    *,
    title: str,
    metadata: dict[str, Any],
    transcript: str,
    comments: dict[str, Any],
    frames: list[dict[str, Any]],
    source_url: str,
    include_frame_context: bool,
) -> str:
    prompt_parts = [
        "You are a senior technical-video analyst. Produce a strict JSON outline from the multimodal evidence.",
        "Output contract: return JSON only. Do not return Markdown or fenced code blocks.",
        "Language contract: every reader-facing field must be Simplified Chinese. Proper nouns, product names, and code identifiers may remain in English.",
        "Structure contract: the top-level object must contain title, tldr, highlights, recommended_actions, risk_or_pitfalls, chapters, and timestamp_references.",
        "Chapter contract: each chapter must contain chapter_no, title, anchor, start_s, end_s, summary, bullets, key_terms, and code_snippets.",
        "Evidence contract: include timestamps and comment evidence whenever possible, and do not fabricate support.",
        f"Title: {title}",
        f"Metadata: {json.dumps(jsonable(metadata), ensure_ascii=False)}",
        f"Transcript (truncated):\n{transcript[:12000]}",
        f"Comment Highlights:\n{build_comments_prompt_context(comments)}",
    ]
    if include_frame_context:
        prompt_parts.append(
            f"Frame Summaries (for richer grounding):\n{build_frames_prompt_context(frames, source_url)}"
        )
    return "\n\n".join(prompt_parts)


def build_digest_prompt(
    *,
    metadata: dict[str, Any],
    outline: dict[str, Any],
    transcript: str,
    comments: dict[str, Any],
    frames: list[dict[str, Any]],
    source_url: str,
    include_frame_context: bool,
) -> str:
    prompt_parts = [
        "You are a senior technical-content editor. Produce a structured digest as JSON.",
        "Output contract: return JSON only. Do not return Markdown or fenced code blocks.",
        "Language contract: every reader-facing field must be Simplified Chinese. Proper nouns, product names, and code identifiers may remain in English.",
        "Field contract: the object must contain title, summary, tldr, highlights, action_items, code_blocks, timestamp_references, and fallback_notes.",
        "Quality contract: keep summary length around 120-220 Chinese characters, deduplicate list items, prefer actionable wording, and stay evidence-driven.",
        f"Metadata:\n{json.dumps(jsonable(metadata), ensure_ascii=False)}",
        f"Outline:\n{json.dumps(jsonable(outline), ensure_ascii=False)}",
        f"Transcript (truncated):\n{transcript[:12000]}",
        f"Comment Highlights:\n{build_comments_prompt_context(comments)}",
    ]
    if include_frame_context:
        prompt_parts.append(
            f"Frame Summaries (optional grounding):\n{build_frames_prompt_context(frames, source_url)}"
        )
    return "\n\n".join(prompt_parts)


def build_digest_review_prompt(
    *,
    metadata: dict[str, Any],
    outline: dict[str, Any],
    draft_digest: dict[str, Any],
    transcript: str,
    comments: dict[str, Any],
    frames: list[dict[str, Any]],
    source_url: str,
    include_frame_context: bool,
) -> str:
    prompt_parts = [
        "You are a senior reader-product reviewer. Review the draft digest against the original multimodal evidence and return a corrected JSON digest.",
        "Output contract: return JSON only. Do not return Markdown or fenced code blocks.",
        "Language contract: every reader-facing field must be Simplified Chinese. Proper nouns, product names, and code identifiers may remain in English.",
        "Field contract: the object must contain title, summary, tldr, highlights, action_items, code_blocks, timestamp_references, and fallback_notes.",
        "Review contract: keep supported claims, remove unsupported claims, fill major omissions, and tighten evidence wording when the draft overstates certainty.",
        f"Metadata:\n{json.dumps(jsonable(metadata), ensure_ascii=False)}",
        f"Outline:\n{json.dumps(jsonable(outline), ensure_ascii=False)}",
        f"Draft Digest:\n{json.dumps(jsonable(draft_digest), ensure_ascii=False)}",
        f"Transcript (truncated):\n{transcript[:12000]}",
        f"Comment Highlights:\n{build_comments_prompt_context(comments)}",
    ]
    if include_frame_context:
        prompt_parts.append(
            f"Frame Summaries (optional grounding):\n{build_frames_prompt_context(frames, source_url)}"
        )
    return "\n\n".join(prompt_parts)


def select_supporting_frames(
    frame_summaries: list[dict[str, Any]] | None = None,
    max_items: int = 5,
) -> dict[str, Any]:
    entries = frame_summaries if isinstance(frame_summaries, list) else []
    limit = max(1, min(20, int(max_items)))
    selected = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        selected.append(
            {
                "timestamp_s": int(item.get("timestamp_s") or 0),
                "reason": str(item.get("reason") or "supporting_frame"),
                "path": str(item.get("path") or ""),
            }
        )
        if len(selected) >= limit:
            break
    return {"frames": selected}


def build_evidence_citations(
    chapters: list[dict[str, Any]] | None = None,
    comments: list[dict[str, Any]] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    chapter_entries = chapters if isinstance(chapters, list) else []
    comment_entries = comments if isinstance(comments, list) else []
    max_items = max(1, min(30, int(limit)))

    citations: list[str] = []
    for chapter in chapter_entries:
        if not isinstance(chapter, dict):
            continue
        start_s = int(chapter.get("start_s") or 0)
        title = str(chapter.get("title") or "chapter").strip() or "chapter"
        citations.append(f"[{start_s}s] {title}")
        if len(citations) >= max_items:
            break

    if len(citations) < max_items:
        for comment in comment_entries:
            if not isinstance(comment, dict):
                continue
            content = str(comment.get("content") or "").strip()
            if not content:
                continue
            citations.append(f"[comment] {content[:60]}")
            if len(citations) >= max_items:
                break

    return {"citations": citations}
