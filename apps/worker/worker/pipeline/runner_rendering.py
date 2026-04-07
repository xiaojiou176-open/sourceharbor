from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from worker.config import Settings
from worker.pipeline.runner_policies import coerce_bool, coerce_int, coerce_str_list


def parse_duration_seconds(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if not isinstance(value, str):
        return 0
    text = value.strip()
    if not text:
        return 0
    if text.isdigit():
        return max(0, int(text))
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return 0
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return 0
    if len(nums) == 2:
        mm, ss = nums
        return max(0, mm * 60 + ss)
    hh, mm, ss = nums
    return max(0, hh * 3600 + mm * 60 + ss)


def estimate_duration_seconds(
    metadata: dict[str, Any], frames: list[dict[str, Any]], fallback_points: int
) -> int:
    for key in ("duration_s", "duration", "duration_seconds"):
        parsed = parse_duration_seconds(metadata.get(key))
        if parsed > 0:
            return parsed
    frame_max = max((coerce_int(frame.get("timestamp_s"), 0) for frame in frames), default=0)
    if frame_max > 0:
        return max(frame_max + 15, 60)
    return max(fallback_points * 90, 180)


def timestamp_link(source_url: str, timestamp_s: int) -> str:
    if not source_url:
        return ""
    timestamp_s = max(timestamp_s, 0)
    try:
        parsed = urlparse(source_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        host = (parsed.hostname or "").lower()
        is_youtube_host = (
            host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
        )
        if is_youtube_host:
            query["t"] = f"{timestamp_s}s"
        else:
            query["t"] = str(timestamp_s)
        return urlunparse(parsed._replace(query=urlencode(query)))
    except Exception:
        return source_url


def build_comments_prompt_context(comments: dict[str, Any], *, top_n: int = 4) -> str:
    top_comments = comments.get("top_comments") if isinstance(comments, dict) else None
    if not isinstance(top_comments, list) or not top_comments:
        return "No comment data available."
    lines: list[str] = []
    for idx, item in enumerate(top_comments[:top_n], start=1):
        if not isinstance(item, dict):
            continue
        author = str(item.get("author") or "unknown")
        content = str(item.get("content") or "").strip() or "empty"
        likes = coerce_int(item.get("like_count"), 0)
        lines.append(f"{idx}. {author} (likes={likes}): {content}")
        replies = item.get("replies")
        if isinstance(replies, list):
            for reply in replies[:2]:
                if not isinstance(reply, dict):
                    continue
                reply_author = str(reply.get("author") or "unknown")
                reply_text = str(reply.get("content") or "").strip() or "empty"
                reply_likes = coerce_int(reply.get("like_count"), 0)
                lines.append(f"   - Reply from {reply_author} (likes={reply_likes}): {reply_text}")
    return "\n".join(lines) if lines else "No comment data available."


def should_include_frame_prompt(settings: Settings) -> bool:
    if hasattr(settings, "pipeline_llm_include_frames"):
        return coerce_bool(settings.pipeline_llm_include_frames, default=False)
    return False


def format_seconds(seconds: int) -> str:
    value = max(0, int(seconds))
    h = value // 3600
    m = (value % 3600) // 60
    s = value % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_frames_prompt_context(
    frames: list[dict[str, Any]], source_url: str, *, limit: int = 8
) -> str:
    if not frames:
        return "No frame data."
    lines: list[str] = []
    for idx, frame in enumerate(frames[:limit], start=1):
        ts = coerce_int(frame.get("timestamp_s"), 0)
        reason = str(frame.get("reason") or "key frame").strip()
        note = str(frame.get("note") or "").strip()
        path = str(frame.get("path") or "").strip()
        lines.append(
            f"{idx}. [{format_seconds(ts)}] {timestamp_link(source_url, ts) or 'n/a'} | {reason} | {note or 'n/a'} | {path or 'n/a'}"
        )
    return "\n".join(lines) if lines else "No frame data."


def extract_code_snippets(transcript: str, *, limit: int = 4) -> list[dict[str, Any]]:
    if not transcript.strip():
        return []
    pattern = re.compile(r"```(?P<lang>[A-Za-z0-9_+-]*)\n(?P<body>[\s\S]*?)```")
    snippets: list[dict[str, Any]] = []
    for idx, match in enumerate(pattern.finditer(transcript), start=1):
        snippet = match.group("body").strip()
        if not snippet:
            continue
        snippets.append(
            {
                "title": f"Snippet {idx}",
                "language": (match.group("lang") or "text").strip() or "text",
                "snippet": snippet[:1000],
                "range_start_s": 0,
                "range_end_s": 0,
            }
        )
        if len(snippets) >= limit:
            break
    return snippets


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_digest_template(settings: Settings) -> str:
    template_path = Path(settings.digest_template_path)
    if template_path.exists():
        return _read_text_file(template_path)
    return (
        "# {{title}}\n\n"
        "> Source: [Original video]({{source_url}})\n"
        "> Platform: {{platform}} | Video ID: {{video_uid}} | Generated at: {{generated_at}}\n\n"
        "## One-Minute Summary\n\n"
        "{{tldr_markdown}}\n\n"
        "## What This Covers\n\n"
        "{{summary}}\n\n"
        "## Key Takeaways\n\n"
        "{{highlights_markdown}}\n\n"
        "## Chapter Guide\n\n"
        "{{chapters_toc_markdown}}\n\n"
        "## Chapter Deep Dive\n\n"
        "{{chapters_markdown}}\n\n"
        "## Comment Insights\n\n"
        "{{comments_markdown}}\n\n"
        "## Key Frames\n\n"
        "{{frames_embedded_markdown}}\n\n"
        "## Timestamp References\n\n"
        "{{timestamp_refs_markdown}}\n\n"
        "## Recommended Actions\n\n"
        "{{action_items_markdown}}\n\n"
        "## Notes (Degradations / Missing Inputs)\n\n"
        "{{degradations_markdown}}\n"
    )


def render_template(template: str, values: dict[str, str]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = re.sub(
            r"{{\s*" + re.escape(key) + r"\s*}}",
            lambda _, replacement=value: replacement,
            rendered,
        )
    return rendered


def build_chapters_toc_markdown(outline: dict[str, Any], source_url: str) -> str:
    chapters = outline.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return "- （暂无章节）"
    lines: list[str] = []
    for idx, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            continue
        title = str(chapter.get("title") or chapter.get("heading") or f"Chapter {idx}")
        chapter_no = coerce_int(chapter.get("chapter_no"), idx)
        anchor = str(chapter.get("anchor") or f"chapter-{chapter_no:02d}")
        start_s = coerce_int(chapter.get("start_s"), 0)
        end_s = coerce_int(chapter.get("end_s"), start_s)
        start_link = timestamp_link(source_url, start_s)
        end_link = timestamp_link(source_url, end_s)
        lines.append(
            f"- [{chapter_no}. {title}](#{anchor})（[{format_seconds(start_s)}]({start_link}) - [{format_seconds(end_s)}]({end_link})）"
        )
    return "\n".join(lines).strip() or "- （暂无章节）"


def build_chapters_markdown(outline: dict[str, Any], source_url: str) -> str:
    chapters = outline.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return "（暂无章节）"

    lines: list[str] = []
    for idx, chapter in enumerate(chapters, start=1):
        if not isinstance(chapter, dict):
            continue
        title = str(chapter.get("title") or chapter.get("heading") or f"Chapter {idx}")
        chapter_no = coerce_int(chapter.get("chapter_no"), idx)
        anchor = str(chapter.get("anchor") or f"chapter-{chapter_no:02d}")
        start_s = coerce_int(chapter.get("start_s"), 0)
        end_s = coerce_int(chapter.get("end_s"), start_s)
        summary = str(chapter.get("summary") or "").strip() or "（无小结）"
        start_link = timestamp_link(source_url, start_s)
        end_link = timestamp_link(source_url, end_s)

        lines.append(f'<a id="{anchor}"></a>')
        lines.append(f"### {chapter_no}. {title}")
        lines.append(
            f"- 时间范围：[{format_seconds(start_s)}]({start_link}) - [{format_seconds(end_s)}]({end_link})"
        )
        lines.append(f"- 核心结论：{summary}")
        lines.append("- 要点：")
        bullets = coerce_str_list(chapter.get("bullets"), limit=4)
        if bullets:
            for bullet in bullets:
                lines.append(f"- {bullet}")
        else:
            lines.append("- （无要点）")
        lines.append("")
    return "\n".join(lines).strip() or "（暂无章节）"


def build_comments_markdown(comments: dict[str, Any]) -> str:
    top_comments = comments.get("top_comments") if isinstance(comments, dict) else None
    if not isinstance(top_comments, list) or not top_comments:
        return "（未采集到评论，或当前未启用评论采集）"

    def _clip(text: str, *, limit: int = 180) -> str:
        compact = " ".join(text.split()).strip()
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit].rstrip()}…"

    lines: list[str] = []
    for idx, item in enumerate(top_comments[:5], start=1):
        if not isinstance(item, dict):
            continue
        author = str(item.get("author") or "unknown")
        content = _clip(str(item.get("content") or ""))
        likes = item.get("like_count")
        lines.append(f"{idx}. **{author}**（👍 {likes if likes is not None else 0}）")
        lines.append(f"   - 观点：{content or '（空）'}")
        replies = item.get("replies")
        if isinstance(replies, list) and replies:
            for reply in replies[:1]:
                if not isinstance(reply, dict):
                    continue
                reply_author = str(reply.get("author") or "unknown")
                reply_content = _clip(str(reply.get("content") or "")) or "（空）"
                reply_likes = reply.get("like_count")
                lines.append(
                    f"   - ↳ **{reply_author}**（👍 {reply_likes if reply_likes is not None else 0}）：{reply_content}"
                )
    return "\n".join(lines) if lines else "（评论数据为空）"


def collect_code_blocks(
    outline: dict[str, Any],
    digest: dict[str, Any],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    raw_blocks = digest.get("code_blocks")
    if isinstance(raw_blocks, list):
        for block in raw_blocks:
            if isinstance(block, dict):
                merged.append(dict(block))
    chapters = outline.get("chapters")
    if isinstance(chapters, list):
        for chapter in chapters:
            if not isinstance(chapter, dict):
                continue
            chapter_blocks = chapter.get("code_snippets")
            if not isinstance(chapter_blocks, list):
                continue
            for block in chapter_blocks:
                if isinstance(block, dict):
                    merged.append(dict(block))
    return merged


def build_code_blocks_markdown(
    outline: dict[str, Any],
    digest: dict[str, Any],
    source_url: str,
) -> str:
    blocks = collect_code_blocks(outline, digest)
    if not blocks:
        return "（无代码片段）"
    lines: list[str] = []
    for idx, block in enumerate(blocks, start=1):
        title = str(block.get("title") or f"Snippet {idx}")
        language = str(block.get("language") or "text").strip() or "text"
        snippet = str(block.get("snippet") or "").strip()
        if not snippet:
            continue
        start_s = coerce_int(block.get("range_start_s"), 0)
        end_s = coerce_int(block.get("range_end_s"), start_s)
        start_link = timestamp_link(source_url, start_s)
        end_link = timestamp_link(source_url, end_s)
        lines.append(
            f"#### {idx}. {title}（[{format_seconds(start_s)}]({start_link}) - [{format_seconds(end_s)}]({end_link})）"
        )
        lines.append(f"```{language}")
        lines.append(snippet)
        lines.append("```")
        lines.append("")
    return "\n".join(lines).strip() or "（无代码片段）"


def build_timestamp_refs_markdown(
    outline: dict[str, Any],
    digest: dict[str, Any],
    source_url: str,
) -> str:
    refs_raw = digest.get("timestamp_references")
    references: list[dict[str, Any]] = []
    if isinstance(refs_raw, list):
        for item in refs_raw:
            if isinstance(item, dict):
                references.append(item)
    if not references:
        refs_outline = outline.get("timestamp_references")
        if isinstance(refs_outline, list):
            for item in refs_outline:
                if isinstance(item, dict):
                    references.append(item)
    if not references:
        return "- （无时间戳引用）"

    lines: list[str] = []
    for idx, item in enumerate(references[:10], start=1):
        ts = coerce_int(item.get("ts_s"), 0)
        label = str(item.get("label") or f"Reference {idx}")
        reason = str(item.get("reason") or "").strip()
        link = timestamp_link(source_url, ts)
        suffix = f" - {reason}" if reason else ""
        lines.append(f"- [{format_seconds(ts)}]({link}) {label}{suffix}")
    return "\n".join(lines).strip() or "- （无时间戳引用）"


def build_frames_markdown(frames: list[dict[str, Any]], source_url: str) -> str:
    if not frames:
        return "（无截图）"
    lines = [
        "| # | 时间戳 | 跳转 | 原因 | 说明 | 文件 |",
        "|---:|:---:|:---:|---|---|---|",
    ]
    for idx, frame in enumerate(frames, start=1):
        ts_s = coerce_int(frame.get("timestamp_s"), 0)
        ts = format_seconds(ts_s)
        link = timestamp_link(source_url, ts_s)
        path = str(frame.get("artifact_path") or frame.get("path") or "")
        reason = str(frame.get("reason") or "key_frame").strip() or "key_frame"
        note = str(frame.get("note") or "").strip() or "-"
        lines.append(f"| {idx} | {ts} | [link]({link}) | {reason} | {note} | `{path}` |")
    return "\n".join(lines)


def build_artifact_asset_url(job_id: str, artifact_path: str) -> str:
    encoded_path = quote(artifact_path, safe="/")
    return f"/api/v1/artifacts/assets?job_id={job_id}&path={encoded_path}"


def build_frames_embedded_markdown(frames: list[dict[str, Any]], job_id: str) -> str:
    if not frames:
        return "（无可内嵌截图）"

    blocks: list[str] = []
    for idx, frame in enumerate(frames, start=1):
        artifact_path = str(frame.get("artifact_path") or "").strip()
        if not artifact_path:
            continue
        ts_s = coerce_int(frame.get("timestamp_s"), 0)
        url = build_artifact_asset_url(job_id, artifact_path)
        blocks.append(f"### {idx}. {format_seconds(ts_s)}\n\n![frame-{idx}]({url})")

    if not blocks:
        return "（截图文件不可内嵌，已回退到截图索引）"
    return "\n\n".join(blocks)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def materialize_frames_for_artifacts(
    frames: list[dict[str, Any]],
    artifacts_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not frames:
        return [], []

    frame_assets_dir = _ensure_dir(artifacts_dir / "frames")
    materialized: list[dict[str, Any]] = []
    frame_files: list[str] = []
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}

    for idx, frame in enumerate(frames, start=1):
        if not isinstance(frame, dict):
            continue

        copied = dict(frame)
        source_path = str(frame.get("path") or "").strip()
        artifact_path: str | None = None

        if source_path:
            source = Path(source_path).expanduser()
            if source.exists() and source.is_file():
                ext = source.suffix.lower() if source.suffix else ".jpg"
                if ext not in allowed_exts:
                    ext = ".jpg"
                target_name = f"frame_{idx:03d}{ext}"
                target = frame_assets_dir / target_name
                try:
                    shutil.copy2(source, target)
                    artifact_path = f"frames/{target_name}"
                    copied["path"] = str(target.resolve())
                    copied["artifact_path"] = artifact_path
                except OSError:
                    artifact_path = None

        if artifact_path:
            frame_files.append(artifact_path)
        elif source_path:
            frame_files.append(source_path)
        materialized.append(copied)

    return materialized, frame_files


def build_fallback_notes_markdown(
    digest: dict[str, Any], degradations: list[dict[str, Any]]
) -> str:
    notes = coerce_str_list(digest.get("fallback_notes"), limit=8)
    if notes:
        return "\n".join(f"- {note}" for note in notes)
    degraded_steps = []
    for item in degradations:
        if not isinstance(item, dict):
            continue
        step = str(item.get("step") or "").strip()
        reason = str(item.get("reason") or "n/a").strip()
        status = str(item.get("status") or "unknown").strip()
        if step:
            degraded_steps.append(f"- {step}: {status} ({reason})")
    return "\n".join(degraded_steps) if degraded_steps else "- none"
