from __future__ import annotations

import hashlib
import re
from typing import Any

from worker.comments import empty_comments_payload
from worker.pipeline.runner_rendering import (
    build_chapters_markdown,
    build_chapters_toc_markdown,
    build_code_blocks_markdown,
    build_comments_markdown,
    build_fallback_notes_markdown,
    build_frames_embedded_markdown,
    build_frames_markdown,
    build_timestamp_refs_markdown,
    load_digest_template,
    materialize_frames_for_artifacts,
    render_template,
)
from worker.pipeline.step_executor import utc_now_iso, write_json
from worker.pipeline.steps.llm import normalize_digest_payload, normalize_outline_payload
from worker.pipeline.types import PipelineContext, StepExecution

_TOPIC_STOP_WORDS = {
    "about",
    "after",
    "again",
    "against",
    "agent",
    "agents",
    "also",
    "because",
    "between",
    "digest",
    "from",
    "have",
    "into",
    "just",
    "more",
    "than",
    "that",
    "their",
    "them",
    "there",
    "these",
    "this",
    "video",
    "with",
}


def _extract_topic_key(*parts: str) -> tuple[str, str]:
    tokens: list[str] = []
    for part in parts:
        tokens.extend(re.findall(r"[a-z0-9]+", part.lower()))

    filtered = [token for token in tokens if len(token) >= 4 and token not in _TOPIC_STOP_WORDS]
    if not filtered:
        return "general", "General"

    ordered: list[str] = []
    for token in filtered:
        if token not in ordered:
            ordered.append(token)
    chosen = ordered[:2]
    topic_key = "-".join(chosen)
    topic_label = " / ".join(token.capitalize() for token in chosen)
    return topic_key, topic_label


def _build_claim_metadata(
    *,
    title: str,
    body: str,
    source_section: str,
    order_index: int,
    claim_kind: str,
    confidence_label: str,
) -> dict[str, Any]:
    topic_key, topic_label = _extract_topic_key(title, body, source_section)
    normalized_body = re.sub(r"\s+", " ", body.strip().lower())
    claim_seed = f"{claim_kind}|{source_section}|{normalized_body}"
    claim_id = hashlib.sha1(claim_seed.encode("utf-8")).hexdigest()[:12]
    return {
        "artifact_source": "knowledge_cards.json",
        "topic_key": topic_key,
        "topic_label": topic_label,
        "claim_id": claim_id,
        "claim_kind": claim_kind,
        "confidence_label": confidence_label,
        "source_anchor": f"{source_section}[{order_index}]",
    }


def _build_knowledge_cards(
    *,
    title: str,
    digest: dict[str, Any],
    outline: dict[str, Any],
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    safe_title = title.strip() or "Untitled"

    summary = str(digest.get("summary") or "").strip()
    if summary:
        cards.append(
            {
                "card_type": "summary",
                "title": safe_title,
                "body": summary,
                "source_section": "summary",
                "order_index": 0,
                "metadata": _build_claim_metadata(
                    title=safe_title,
                    body=summary,
                    source_section="summary",
                    order_index=0,
                    claim_kind="summary",
                    confidence_label="high",
                ),
            }
        )

    highlights = [
        str(item).strip() for item in (digest.get("highlights") or []) if str(item).strip()
    ]
    for index, item in enumerate(highlights[:12], start=1):
        cards.append(
            {
                "card_type": "takeaway",
                "title": f"{safe_title} · Takeaway {index}",
                "body": item,
                "source_section": "highlights",
                "order_index": index,
                "metadata": _build_claim_metadata(
                    title=safe_title,
                    body=item,
                    source_section="highlights",
                    order_index=index,
                    claim_kind="takeaway",
                    confidence_label="high",
                ),
            }
        )

    action_items = [
        str(item).strip() for item in (digest.get("action_items") or []) if str(item).strip()
    ]
    for index, item in enumerate(action_items[:12], start=1):
        cards.append(
            {
                "card_type": "action",
                "title": f"{safe_title} · Action {index}",
                "body": item,
                "source_section": "action_items",
                "order_index": index,
                "metadata": _build_claim_metadata(
                    title=safe_title,
                    body=item,
                    source_section="action_items",
                    order_index=index,
                    claim_kind="action",
                    confidence_label="medium",
                ),
            }
        )

    topic_mentions: dict[str, dict[str, Any]] = {}
    for card in cards:
        metadata = dict(card.get("metadata") or {})
        topic_key = str(metadata.get("topic_key") or "").strip()
        topic_label = str(metadata.get("topic_label") or "").strip()
        if not topic_key or not topic_label:
            continue
        existing = topic_mentions.setdefault(
            topic_key,
            {
                "label": topic_label,
                "mentions": 0,
                "source_sections": set(),
            },
        )
        existing["mentions"] = int(existing.get("mentions") or 0) + 1
        cast_sections = existing.get("source_sections")
        if isinstance(cast_sections, set):
            cast_sections.add(str(card.get("source_section") or ""))

    for _, topic_payload in sorted(
        topic_mentions.items(),
        key=lambda item: (-int(item[1]["mentions"]), str(item[0])),
    )[:4]:
        source_sections = sorted(
            section
            for section in topic_payload.get("source_sections", set())
            if isinstance(section, str) and section
        )
        cards.append(
            {
                "card_type": "topic",
                "title": f"{safe_title} · Topic",
                "body": str(topic_payload["label"]),
                "source_section": "topics",
                "metadata": {
                    "artifact_source": "knowledge_cards.json",
                    "topic_key": _extract_topic_key(str(topic_payload["label"]))[0],
                    "topic_label": str(topic_payload["label"]),
                    "mentions": int(topic_payload["mentions"]),
                    "source_sections": source_sections,
                },
            }
        )

    claim_cards: list[dict[str, Any]] = []
    for index, card in enumerate(cards):
        if card.get("card_type") not in {"summary", "takeaway", "action"}:
            continue
        metadata = dict(card.get("metadata") or {})
        claim_cards.append(
            {
                "card_type": "claim",
                "title": f"{safe_title} · Claim {len(claim_cards) + 1}",
                "body": str(card.get("body") or ""),
                "source_section": str(card.get("source_section") or "summary"),
                "metadata": {
                    **metadata,
                    "claim_source_card_type": str(card.get("card_type") or ""),
                    "source_anchor": metadata.get("source_anchor") or f"claim[{index}]",
                },
            }
        )
    cards.extend(claim_cards)

    for index, card in enumerate(cards):
        card["order_index"] = index

    return cards


def _has_transcript_evidence(transcript: str) -> bool:
    return len(transcript.strip()) >= 80


def _has_comments_evidence(comments: dict[str, Any]) -> bool:
    top_comments = comments.get("top_comments") if isinstance(comments, dict) else None
    return isinstance(top_comments, list) and bool(top_comments)


def _is_low_evidence_mode(
    *,
    transcript: str,
    comments: dict[str, Any],
    frames: list[dict[str, Any]],
) -> bool:
    return (
        not _has_transcript_evidence(transcript)
        and not _has_comments_evidence(comments)
        and not bool(frames)
    )


def _apply_low_evidence_guard(
    digest: dict[str, Any],
    outline: dict[str, Any],
    *,
    transcript: str,
    comments: dict[str, Any],
) -> None:
    digest["summary"] = (
        "当前缺少可验证证据（字幕/评论/截图均不可用），无法生成高置信度内容摘要。"
        "以下仅保留流程性提示，不提供具体章节与时间戳结论。"
    )
    digest["tldr"] = [
        "未获取到可用字幕，无法基于语义内容做摘要。",
        "未采集到评论，缺少外部观点信号。",
        "未提取到关键截图，缺少画面证据。",
    ]
    digest["highlights"] = [
        "证据不足：本次结果不能作为视频内容事实依据。",
        "已禁用章节精读与时间戳定位，避免误导。",
        "建议补齐字幕、评论或关键帧后重新生成。",
    ]
    digest["action_items"] = [
        "检查字幕抓取链路（平台字幕/ASR）后重跑。",
        "启用评论采集或确认评论接口可用。",
        "启用关键帧提取后再次生成摘要。",
    ]
    digest["timestamp_references"] = []
    digest["code_blocks"] = []

    fallback_notes = [
        str(item) for item in (digest.get("fallback_notes") or []) if str(item).strip()
    ]
    if not _has_transcript_evidence(transcript):
        fallback_notes.append("transcript_missing_or_too_short")
    if not _has_comments_evidence(comments):
        fallback_notes.append("comments_missing")
    fallback_notes.append("frames_missing")
    fallback_notes.append("quality_gate:low_evidence_mode")
    digest["fallback_notes"] = fallback_notes

    outline["chapters"] = []
    outline["timestamp_references"] = []


async def step_write_artifacts(ctx: PipelineContext, state: dict[str, Any]) -> StepExecution:
    try:
        template = load_digest_template(ctx.settings)
        metadata = dict(state.get("metadata") or {})
        source_url = str(state.get("source_url") or metadata.get("webpage_url") or "")
        outline = normalize_outline_payload(dict(state.get("outline") or {}), state)
        digest_state = dict(state)
        digest_state["outline"] = outline
        digest = normalize_digest_payload(dict(state.get("digest") or {}), digest_state)
        comments = dict(state.get("comments") or empty_comments_payload())
        transcript = str(state.get("transcript") or "")
        degradations = list(state.get("degradations") or [])
        raw_frames = list(state.get("frames") or [])
        frames, frame_files = materialize_frames_for_artifacts(raw_frames, ctx.artifacts_dir)
        if _is_low_evidence_mode(transcript=transcript, comments=comments, frames=frames):
            _apply_low_evidence_guard(digest, outline, transcript=transcript, comments=comments)

        tldr = [str(item) for item in (digest.get("tldr") or []) if str(item).strip()]
        highlights = [str(item) for item in (digest.get("highlights") or []) if str(item).strip()]
        action_items = [
            str(item) for item in (digest.get("action_items") or []) if str(item).strip()
        ]
        if not highlights:
            highlights = ["未提取到高置信度要点。"]
        if not tldr:
            tldr = highlights[:4]
        if not action_items:
            action_items = [f"复盘：{item}" for item in highlights[:3]]

        degradation_lines = [
            f"- {item.get('step')}: {item.get('status')} ({item.get('reason') or 'n/a'})"
            for item in degradations
            if isinstance(item, dict)
        ]
        if not degradation_lines:
            degradation_lines = ["- 无明显降级。"]

        rendered_digest = render_template(
            template,
            {
                "title": str(
                    digest.get("title")
                    or metadata.get("title")
                    or state.get("title")
                    or "Untitled Video"
                ),
                "source_url": source_url,
                "platform": str(state.get("platform") or ""),
                "video_uid": str(state.get("video_uid") or ""),
                "generated_at": utc_now_iso(),
                "summary": str(digest.get("summary") or "未生成摘要。"),
                "tldr_markdown": "\n".join(f"- {item}" for item in tldr),
                "highlights_markdown": "\n".join(f"- {item}" for item in highlights),
                "action_items_markdown": "\n".join(f"- [ ] {item}" for item in action_items),
                "chapters_toc_markdown": build_chapters_toc_markdown(outline, source_url),
                "chapters_markdown": build_chapters_markdown(outline, source_url),
                "code_blocks_markdown": build_code_blocks_markdown(outline, digest, source_url),
                "comments_markdown": build_comments_markdown(comments),
                "frames_embedded_markdown": build_frames_embedded_markdown(frames, ctx.job_id),
                "frames_index_markdown": build_frames_markdown(frames, source_url),
                "timestamp_refs_markdown": build_timestamp_refs_markdown(
                    outline, digest, source_url
                ),
                "fallback_notes_markdown": build_fallback_notes_markdown(digest, degradations),
                "degradations_markdown": "\n".join(degradation_lines),
            },
        )

        meta_payload = {
            "job": ctx.job_record,
            "metadata": metadata,
            "raw_stage_contract": dict(state.get("raw_stage_contract") or {}),
            "download_mode": state.get("download_mode"),
            "media_path": state.get("media_path"),
            "subtitle_files": state.get("subtitle_files") or [],
            "frame_files": frame_files,
            "degradations": degradations,
            "generated_at": utc_now_iso(),
        }

        meta_path = ctx.artifacts_dir / "meta.json"
        comments_path = ctx.artifacts_dir / "comments.json"
        transcript_path = ctx.artifacts_dir / "transcript.txt"
        outline_path = ctx.artifacts_dir / "outline.json"
        digest_path = ctx.artifacts_dir / "digest.md"
        knowledge_cards_path = ctx.artifacts_dir / "knowledge_cards.json"

        knowledge_cards = _build_knowledge_cards(
            title=str(
                digest.get("title")
                or metadata.get("title")
                or state.get("title")
                or "Untitled Video"
            ),
            digest=digest,
            outline=outline,
        )

        write_json(meta_path, meta_payload)
        write_json(comments_path, comments)
        transcript_path.write_text(transcript, encoding="utf-8")
        write_json(outline_path, outline)
        digest_path.write_text(rendered_digest, encoding="utf-8")
        write_json(knowledge_cards_path, knowledge_cards)
        if ctx.pg_store is not None:
            video_id = str(ctx.job_record.get("video_id") or "").strip()
            if video_id and hasattr(ctx.pg_store, "replace_knowledge_cards"):
                ctx.pg_store.replace_knowledge_cards(
                    video_id=video_id,
                    job_id=ctx.job_id,
                    items=[
                        {
                            "card_type": card["card_type"],
                            "source_section": card["source_section"],
                            "title": card["title"],
                            "body": card["body"],
                            "ordinal": int(card["order_index"]),
                            "metadata": dict(card.get("metadata") or {}),
                        }
                        for card in knowledge_cards
                    ],
                )

        return StepExecution(
            status="succeeded",
            output={
                "artifact_dir": str(ctx.artifacts_dir.resolve()),
                "files": {
                    "meta": str(meta_path.resolve()),
                    "comments": str(comments_path.resolve()),
                    "transcript": str(transcript_path.resolve()),
                    "outline": str(outline_path.resolve()),
                    "digest": str(digest_path.resolve()),
                    "knowledge_cards": str(knowledge_cards_path.resolve()),
                },
            },
            state_updates={
                "artifact_dir": str(ctx.artifacts_dir.resolve()),
                "artifacts": {
                    "meta": str(meta_path.resolve()),
                    "comments": str(comments_path.resolve()),
                    "transcript": str(transcript_path.resolve()),
                    "outline": str(outline_path.resolve()),
                    "digest": str(digest_path.resolve()),
                    "knowledge_cards": str(knowledge_cards_path.resolve()),
                },
            },
        )
    except Exception as exc:  # pragma: no cover
        return StepExecution(
            status="failed",
            reason="write_artifacts_failed",
            error=str(exc),
            degraded=True,
        )
