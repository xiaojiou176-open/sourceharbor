from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any

from worker.pipeline.steps.llm_prompts import (
    build_digest_prompt,
    build_evidence_citations,
    build_outline_prompt,
    build_translation_prompt,
    select_supporting_frames,
)
from worker.pipeline.steps.metadata import step_fetch_metadata
from worker.pipeline.types import CommandResult


def test_step_fetch_metadata_returns_failed_when_source_url_missing() -> None:
    async def _never_called(_ctx: Any, _cmd: list[str]) -> Any:
        raise AssertionError("run_command should not be called")

    execution = asyncio.run(step_fetch_metadata(SimpleNamespace(), {}, run_command=_never_called))

    assert execution.status == "failed"
    assert execution.reason == "source_url_missing"
    assert execution.degraded is True
    assert execution.state_updates["metadata"]["source_url"] is None


def test_step_fetch_metadata_parses_yt_dlp_json_payload() -> None:
    async def _ok(_ctx: Any, cmd: list[str]) -> CommandResult:
        assert cmd[0] == "yt-dlp"
        return CommandResult(
            ok=True,
            stdout=(
                '{"extractor":"youtube","extractor_key":"Youtube","uploader":"demo",'
                '"duration":120,"language":"zh","description":"desc","tags":["a"],"thumbnail":"thumb",'
                '"webpage_url":"https://video"}'
            ),
        )

    state = {
        "source_url": "https://example.com/watch?v=1",
        "title": "Demo",
        "platform": "youtube",
        "video_uid": "vid-1",
    }
    execution = asyncio.run(step_fetch_metadata(SimpleNamespace(), state, run_command=_ok))

    assert execution.status == "succeeded"
    assert execution.degraded is False
    assert execution.output["provider"] == "yt-dlp"
    metadata = execution.state_updates["metadata"]
    assert metadata["extractor"] == "youtube"
    assert metadata["uploader"] == "demo"
    assert metadata["language"] == "zh"
    assert metadata["webpage_url"] == "https://video"
    assert isinstance(metadata["fetched_at"], str)


def test_step_fetch_metadata_enriches_bilibili_metadata_and_danmaku() -> None:
    async def _ok(_ctx: Any, cmd: list[str]) -> CommandResult:
        assert "--add-header" in cmd
        assert "Cookie: SESSDATA=demo" in cmd
        return CommandResult(
            ok=True,
            stdout=(
                '{"extractor":"bilibili","extractor_key":"BiliBili","uploader":"demo-up",'
                '"duration":120,"language":"zh","description":"desc","tags":["a"],'
                '"thumbnail":"thumb","webpage_url":"https://www.bilibili.com/video/BV1demo"}'
            ),
        )

    async def _fake_bilibili_rich_evidence(
        *,
        source_url: str,
        video_uid: str,
        request_timeout_seconds: float,
        cookie: str | None,
    ) -> dict[str, Any]:
        assert source_url == "https://www.bilibili.com/video/BV1demo"
        assert video_uid == "BV1demo"
        assert request_timeout_seconds == 13.0
        assert cookie == "SESSDATA=demo"
        return {
            "metadata": {
                "uploader_mid": "12345",
                "uploader_url": "https://space.bilibili.com/12345",
                "view_count": 999,
                "like_count": 88,
                "comment_count": 12,
                "category": "Science",
                "chapters": [{"cid": 11, "title": "Part 1", "duration": 30}],
                "site_objects": {"owner": {"mid": "12345"}, "stat": {"view": 999}},
            },
            "danmaku": {
                "status": "available",
                "cid": 11,
                "entry_count": 1,
                "entries": [{"progress_s": 12.3, "content": "hello"}],
            },
        }

    state = {
        "source_url": "https://www.bilibili.com/video/BV1demo",
        "title": "Demo",
        "platform": "bilibili",
        "video_uid": "BV1demo",
    }
    ctx = SimpleNamespace(
        settings=SimpleNamespace(
            bilibili_cookie="SESSDATA=demo",
            request_timeout_seconds=13.0,
        )
    )

    execution = asyncio.run(
        step_fetch_metadata(
            ctx,
            state,
            run_command=_ok,
            fetch_bilibili_rich_evidence=_fake_bilibili_rich_evidence,
        )
    )

    assert execution.status == "succeeded"
    assert execution.degraded is False
    metadata = execution.state_updates["metadata"]
    assert metadata["uploader_mid"] == "12345"
    assert metadata["uploader_url"] == "https://space.bilibili.com/12345"
    assert metadata["view_count"] == 999
    assert metadata["like_count"] == 88
    assert metadata["comment_count"] == 12
    assert metadata["category"] == "Science"
    assert metadata["chapters"][0]["title"] == "Part 1"
    assert metadata["site_objects"]["owner"]["mid"] == "12345"
    danmaku = execution.state_updates["danmaku"]
    assert danmaku["status"] == "available"
    assert danmaku["entry_count"] == 1
    assert danmaku["entries"][0]["content"] == "hello"


def test_step_fetch_metadata_falls_back_on_invalid_json_and_command_failure() -> None:
    async def _bad_json(_ctx: Any, _cmd: list[str]) -> CommandResult:
        return CommandResult(ok=True, stdout="{not-json")

    bad_json = asyncio.run(
        step_fetch_metadata(
            SimpleNamespace(), {"source_url": "https://example.com/x"}, run_command=_bad_json
        )
    )
    assert bad_json.status == "succeeded"
    assert bad_json.degraded is True
    assert bad_json.reason == "yt_dlp_failed"
    assert bad_json.output["provider"] == "fallback"

    async def _failure(_ctx: Any, _cmd: list[str]) -> CommandResult:
        return CommandResult(ok=False, reason="binary_not_found", stderr="missing")

    failed = asyncio.run(
        step_fetch_metadata(
            SimpleNamespace(), {"source_url": "https://example.com/y"}, run_command=_failure
        )
    )
    assert failed.degraded is True
    assert failed.reason == "binary_not_found"
    assert failed.output["reason"] == "binary_not_found"


def test_prompt_builders_include_context_only_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "worker.pipeline.steps.llm_prompts.build_comments_prompt_context", lambda _: "COMMENTS"
    )
    monkeypatch.setattr(
        "worker.pipeline.steps.llm_prompts.build_frames_prompt_context", lambda *_: "FRAMES"
    )

    outline_prompt = build_outline_prompt(
        title="Demo",
        metadata={"lang": "en"},
        transcript="text",
        comments={"top_comments": []},
        frames=[{"path": "f.jpg"}],
        source_url="https://example.com",
        include_frame_context=True,
    )
    assert "COMMENTS" in outline_prompt
    assert "FRAMES" in outline_prompt

    digest_prompt = build_digest_prompt(
        metadata={"lang": "en"},
        outline={"title": "x"},
        transcript="text",
        comments={"top_comments": []},
        frames=[{"path": "f.jpg"}],
        source_url="https://example.com",
        include_frame_context=False,
    )
    assert "COMMENTS" in digest_prompt
    assert "FRAMES" not in digest_prompt


def test_translation_prompt_and_supporting_frame_selection_are_structured() -> None:
    prompt = build_translation_prompt({"title": "Hello", "count": 1}, schema_label="digest.v1")
    assert "Schema: digest.v1" in prompt
    assert '"title": "Hello"' in prompt

    selected = select_supporting_frames(
        [
            {"timestamp_s": 3, "reason": "slide", "path": "a.jpg"},
            "ignored",
            {"timestamp_s": 5, "path": "b.jpg"},
        ],
        max_items=2,
    )
    assert selected == {
        "frames": [
            {"timestamp_s": 3, "reason": "slide", "path": "a.jpg"},
            {"timestamp_s": 5, "reason": "supporting_frame", "path": "b.jpg"},
        ]
    }


def test_prompt_templates_are_english_first_while_output_contract_stays_chinese() -> None:
    outline_prompt = build_outline_prompt(
        title="Demo",
        metadata={"lang": "en"},
        transcript="hello world",
        comments={"top_comments": []},
        frames=[],
        source_url="https://example.com",
        include_frame_context=False,
    )
    digest_prompt = build_digest_prompt(
        metadata={"lang": "en"},
        outline={"title": "Demo"},
        transcript="hello world",
        comments={"top_comments": []},
        frames=[],
        source_url="https://example.com",
        include_frame_context=False,
    )

    assert "Simplified Chinese" in outline_prompt
    assert "Simplified Chinese" in digest_prompt
    assert "No comment data available." in outline_prompt
    assert "No comment data available." in digest_prompt
    assert re.search(r"[\u4e00-\u9fff]", outline_prompt) is None
    assert re.search(r"[\u4e00-\u9fff]", digest_prompt) is None


def test_build_evidence_citations_prioritizes_chapters_then_comments() -> None:
    citations = build_evidence_citations(
        chapters=[{"start_s": 12, "title": "Intro"}, {"start_s": 45, "title": "Deep Dive"}],
        comments=[{"content": "great explanation"}, {"content": ""}],
        limit=3,
    )

    assert citations["citations"] == [
        "[12s] Intro",
        "[45s] Deep Dive",
        "[comment] great explanation",
    ]
