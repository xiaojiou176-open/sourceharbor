from __future__ import annotations

from pathlib import Path

from worker.config import Settings
from worker.pipeline.runner_rendering import (
    build_artifact_asset_url,
    build_chapters_markdown,
    build_chapters_toc_markdown,
    build_code_blocks_markdown,
    build_comments_markdown,
    build_comments_prompt_context,
    build_fallback_notes_markdown,
    build_frames_embedded_markdown,
    build_frames_markdown,
    build_timestamp_refs_markdown,
    estimate_duration_seconds,
    extract_code_snippets,
    format_seconds,
    materialize_frames_for_artifacts,
    parse_duration_seconds,
    render_template,
    should_include_frame_prompt,
    timestamp_link,
)


def test_should_include_frame_prompt_reads_settings_flag() -> None:
    assert should_include_frame_prompt(Settings(pipeline_llm_include_frames=True)) is True
    assert should_include_frame_prompt(Settings(pipeline_llm_include_frames=False)) is False


def test_parse_and_estimate_duration_seconds() -> None:
    assert parse_duration_seconds(12.8) == 12
    assert parse_duration_seconds("03:10") == 190
    assert parse_duration_seconds("01:02:03") == 3723
    assert parse_duration_seconds("bad") == 0
    assert parse_duration_seconds("01:xx") == 0
    assert estimate_duration_seconds({"duration_s": "120"}, [], 0) == 120
    assert estimate_duration_seconds({}, [{"timestamp_s": 90}], 0) == 105
    assert estimate_duration_seconds({}, [], 3) == 270


def test_timestamp_and_format_helpers() -> None:
    yt = timestamp_link("https://www.youtube.com/watch?v=x", 65)
    assert "t=65s" in yt
    bili = timestamp_link("https://www.bilibili.com/video/BV1", 65)
    assert "t=65" in bili
    assert format_seconds(3723) == "01:02:03"
    assert timestamp_link("", 10) == ""


def test_chapter_and_timestamp_markdown_builders() -> None:
    outline = {
        "chapters": [
            {"chapter_no": 1, "title": "Intro", "start_s": 0, "end_s": 10, "bullets": ["a"]},
            {"chapter_no": 2, "title": "Body", "start_s": 11, "end_s": 30, "summary": "ok"},
        ],
        "timestamp_references": [{"ts_s": 5, "label": "hook", "reason": "important"}],
    }
    toc = build_chapters_toc_markdown(outline, "https://youtu.be/x")
    detail = build_chapters_markdown(outline, "https://youtu.be/x")
    refs = build_timestamp_refs_markdown(outline, {}, "https://youtu.be/x")
    assert "Intro" in toc and "Body" in toc
    assert "### 1. Intro" in detail
    assert "核心结论" in detail
    assert "hook - important" in refs


def test_comments_markdown_with_replies_and_fallback() -> None:
    comments = {
        "top_comments": [
            {
                "author": "alice",
                "content": "great video",
                "like_count": 10,
                "replies": [{"author": "bob", "content": "agree", "like_count": 2}],
            }
        ]
    }
    text = build_comments_markdown(comments)
    assert "alice" in text
    assert "bob" in text
    assert "（未采集到评论" in build_comments_markdown({})


def test_comments_prompt_context_renders_top_comments_and_reply_lines() -> None:
    comments = {
        "top_comments": [
            {
                "author": "alice",
                "content": "great video",
                "like_count": 10,
                "replies": [{"author": "bob", "content": "agree", "like_count": 2}],
            }
        ]
    }
    text = build_comments_prompt_context(comments, top_n=2)
    assert "alice (likes=10)" in text
    assert "Reply from bob (likes=2)" in text
    assert build_comments_prompt_context({}) == "No comment data available."


def test_code_block_collection_and_rendering() -> None:
    outline = {
        "chapters": [{"code_snippets": [{"title": "C1", "language": "py", "snippet": "print(1)"}]}]
    }
    digest = {"code_blocks": [{"title": "D1", "language": "ts", "snippet": "console.log(1)"}]}
    rendered = build_code_blocks_markdown(outline, digest, "https://youtu.be/x")
    assert "D1" in rendered
    assert "C1" in rendered
    assert build_code_blocks_markdown({}, {}, "https://youtu.be/x") == "（无代码片段）"


def test_extract_code_snippets_and_template_rendering() -> None:
    transcript = "```py\nprint(1)\n```\ntext\n```ts\nconsole.log(1)\n```"
    snippets = extract_code_snippets(transcript, limit=1)
    assert len(snippets) == 1
    assert snippets[0]["language"] == "py"
    rendered = render_template("hello {{ name }}", {"name": "world"})
    assert rendered == "hello world"


def test_frames_markdown_and_embedded_blocks() -> None:
    frames = [{"timestamp_s": 5, "reason": "key", "note": "n", "artifact_path": "frames/a.jpg"}]
    table = build_frames_markdown(frames, "https://youtu.be/x")
    embedded = build_frames_embedded_markdown(frames, "job-1")
    assert "| 1 | 00:00:05 |" in table
    assert "![frame-1]" in embedded
    assert build_frames_markdown([], "https://youtu.be/x") == "（无截图）"
    assert build_frames_embedded_markdown([], "job-1") == "（无可内嵌截图）"
    assert "assets?job_id=job-1" in build_artifact_asset_url("job-1", "frames/a b.jpg")


def test_materialize_frames_for_artifacts_and_fallback_notes(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    source = tmp_path / "frame.png"
    source.write_bytes(b"png")
    frames = [{"timestamp_s": 3, "path": str(source), "reason": "k"}]
    materialized, files = materialize_frames_for_artifacts(frames, artifacts_dir)
    assert materialized[0]["artifact_path"].startswith("frames/")
    assert files[0].startswith("frames/")

    notes = build_fallback_notes_markdown({"fallback_notes": ["a", "b"]}, [])
    assert notes == "- a\n- b"
    degraded = build_fallback_notes_markdown(
        {}, [{"step": "llm", "status": "degraded", "reason": "timeout"}]
    )
    assert "llm: degraded (timeout)" in degraded
