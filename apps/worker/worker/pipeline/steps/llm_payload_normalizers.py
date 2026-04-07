from __future__ import annotations

from typing import Any

from worker.pipeline.policies import coerce_int, coerce_str_list
from worker.pipeline.runner_rendering import estimate_duration_seconds, timestamp_link
from worker.pipeline.step_executor import utc_now_iso


def normalize_outline_payload(payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(state.get("metadata") or {})
    frames = list(state.get("frames") or [])
    source_url = str(state.get("source_url") or metadata.get("webpage_url") or "")
    title = str(
        payload.get("title") or metadata.get("title") or state.get("title") or "Untitled Video"
    )
    tldr = coerce_str_list(payload.get("tldr"), limit=8)
    highlights = coerce_str_list(payload.get("highlights"), limit=12)
    actions = coerce_str_list(
        payload.get("recommended_actions") or payload.get("action_items"),
        limit=12,
    )
    pitfalls = coerce_str_list(payload.get("risk_or_pitfalls"), limit=12)
    raw_chapters = payload.get("chapters")
    if not isinstance(raw_chapters, list):
        raw_chapters = []
    duration_s = estimate_duration_seconds(metadata, frames, max(1, len(raw_chapters)))
    chapter_span = max(1, duration_s // max(1, len(raw_chapters)))
    chapters: list[dict[str, Any]] = []
    for idx, chapter in enumerate(raw_chapters, start=1):
        if not isinstance(chapter, dict):
            continue
        chapter_no = coerce_int(chapter.get("chapter_no"), idx)
        chapter_title = str(chapter.get("title") or f"Chapter {chapter_no}")
        start_s = coerce_int(chapter.get("start_s"), (idx - 1) * chapter_span)
        end_s = coerce_int(
            chapter.get("end_s"),
            duration_s if idx == len(raw_chapters) else max(start_s, idx * chapter_span - 1),
        )
        end_s = max(start_s, end_s)
        bullets = coerce_str_list(chapter.get("bullets"), limit=8)
        summary = str(chapter.get("summary") or "").strip() or (
            bullets[0] if bullets else "（无小结）"
        )
        key_terms = coerce_str_list(chapter.get("key_terms"), limit=8)
        code_snippets: list[dict[str, Any]] = []
        raw_snippets = chapter.get("code_snippets")
        if isinstance(raw_snippets, list):
            for s_idx, snippet in enumerate(raw_snippets, start=1):
                if not isinstance(snippet, dict):
                    continue
                body = str(snippet.get("snippet") or "").strip()
                if not body:
                    continue
                code_snippets.append(
                    {
                        "title": str(snippet.get("title") or f"Snippet {s_idx}"),
                        "language": str(snippet.get("language") or "text"),
                        "snippet": body[:1200],
                        "range_start_s": coerce_int(snippet.get("range_start_s"), start_s),
                        "range_end_s": coerce_int(snippet.get("range_end_s"), end_s),
                    }
                )
        anchor = str(chapter.get("anchor") or f"chapter-{chapter_no:02d}")
        chapters.append(
            {
                "chapter_no": chapter_no,
                "title": chapter_title,
                "anchor": anchor,
                "start_s": start_s,
                "end_s": end_s,
                "start_link": timestamp_link(source_url, start_s),
                "end_link": timestamp_link(source_url, end_s),
                "summary": summary,
                "bullets": bullets,
                "key_terms": key_terms,
                "code_snippets": code_snippets,
            }
        )
    refs_raw = payload.get("timestamp_references")
    timestamp_references: list[dict[str, Any]] = []
    if isinstance(refs_raw, list):
        for idx, ref in enumerate(refs_raw, start=1):
            if isinstance(ref, dict):
                timestamp_references.append(
                    {
                        "ts_s": coerce_int(ref.get("ts_s"), 0),
                        "label": str(ref.get("label") or f"Reference {idx}"),
                        "reason": str(ref.get("reason") or ""),
                    }
                )
    return {
        "title": title,
        "tldr": tldr,
        "highlights": highlights,
        "recommended_actions": actions,
        "risk_or_pitfalls": pitfalls,
        "chapters": chapters,
        "timestamp_references": timestamp_references,
        "generated_by": "gemini",
        "generated_at": str(payload.get("generated_at") or utc_now_iso()),
    }


def normalize_digest_payload(payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(state.get("metadata") or {})
    title = str(
        payload.get("title") or metadata.get("title") or state.get("title") or "Untitled Video"
    )
    summary = str(payload.get("summary") or "").strip()
    tldr = coerce_str_list(payload.get("tldr"), limit=8)
    highlights = coerce_str_list(payload.get("highlights"), limit=12)
    action_items = coerce_str_list(
        payload.get("action_items") or payload.get("recommended_actions"),
        limit=12,
    )
    fallback_notes = coerce_str_list(payload.get("fallback_notes"), limit=8)
    code_blocks_raw = payload.get("code_blocks")
    code_blocks: list[dict[str, Any]] = []
    if isinstance(code_blocks_raw, list):
        for idx, item in enumerate(code_blocks_raw, start=1):
            if isinstance(item, dict):
                snippet = str(item.get("snippet") or "").strip()
                if snippet:
                    code_blocks.append(
                        {
                            "title": str(item.get("title") or f"Snippet {idx}"),
                            "language": str(item.get("language") or "text"),
                            "snippet": snippet[:1200],
                            "range_start_s": coerce_int(item.get("range_start_s"), 0),
                            "range_end_s": coerce_int(
                                item.get("range_end_s"), coerce_int(item.get("range_start_s"), 0)
                            ),
                        }
                    )
    refs_raw = payload.get("timestamp_references")
    timestamp_references: list[dict[str, Any]] = []
    if isinstance(refs_raw, list):
        for idx, ref in enumerate(refs_raw, start=1):
            if isinstance(ref, dict):
                timestamp_references.append(
                    {
                        "ts_s": coerce_int(ref.get("ts_s"), 0),
                        "label": str(ref.get("label") or f"Reference {idx}"),
                        "reason": str(ref.get("reason") or ""),
                    }
                )
    return {
        "title": title,
        "summary": summary,
        "tldr": tldr,
        "highlights": highlights,
        "action_items": action_items,
        "code_blocks": code_blocks,
        "timestamp_references": timestamp_references,
        "fallback_notes": fallback_notes,
        "generated_by": "gemini",
        "generated_at": str(payload.get("generated_at") or utc_now_iso()),
    }
