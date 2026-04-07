from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from worker.comments import youtube
from worker.comments.youtube import YouTubeCommentCollector


def test_youtube_comment_helpers_extract_and_normalize() -> None:
    assert youtube._to_int("12") == 12
    assert youtube._to_int("bad", default=7) == 7
    assert youtube._ts_to_iso("2024-01-01T00:00:00Z") == "2024-01-01T00:00:00+00:00"
    assert youtube._ts_to_iso("2024-01-01T00:00:00+08:00") == "2024-01-01T00:00:00+08:00"
    assert youtube._ts_to_iso("") is None

    assert youtube._extract_video_id("https://youtu.be/abc123", "") == "abc123"
    assert youtube._extract_video_id("https://www.youtube.com/watch?v=demo", "") == "demo"
    assert youtube._extract_video_id("https://www.youtube.com/shorts/short-id", "") == "short-id"
    assert youtube._extract_video_id("https://example.com/watch?v=invalid", "") == ""

    collector = YouTubeCommentCollector(api_key="k", top_n=1, replies_per_comment=1)
    top = collector._normalize_top_comment({"id": "thread-id", "snippet": {}})
    reply = collector._normalize_reply({"snippet": {}})
    assert top["comment_id"] == "thread-id"
    assert reply["reply_id"].startswith("youtube_reply_")


def test_request_json_retries_and_returns_payload(monkeypatch: Any) -> None:
    collector = YouTubeCommentCollector(
        api_key="test-key",
        top_n=1,
        replies_per_comment=0,
        retry_attempts=1,
        retry_backoff_seconds=0.0,
    )

    class _FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def get(self, path: str, *, params: dict[str, Any]) -> httpx.Response:
            self.calls += 1
            assert path == "/commentThreads"
            assert params["videoId"] == "vid-1"
            if self.calls == 1:
                raise httpx.TimeoutException("timeout")
            request = httpx.Request("GET", "https://unit.test/commentThreads")
            return httpx.Response(status_code=200, json={"items": []}, request=request)

    async def _run() -> dict[str, Any]:
        return await collector._request_json(
            _FakeClient(),  # type: ignore[arg-type]
            "/commentThreads",
            params={"videoId": "vid-1"},
        )

    payload = asyncio.run(_run())
    assert payload == {"items": []}


def test_request_json_raises_after_exhausting_retries() -> None:
    collector = YouTubeCommentCollector(
        api_key="test-key",
        top_n=1,
        replies_per_comment=0,
        retry_attempts=1,
        retry_backoff_seconds=0.0,
    )

    class _ErrorClient:
        async def get(self, _path: str, *, params: dict[str, Any]) -> httpx.Response:
            request = httpx.Request("GET", "https://unit.test/commentThreads", params=params)
            return httpx.Response(status_code=500, json={"error": "boom"}, request=request)

    async def _run() -> dict[str, Any]:
        return await collector._request_json(
            _ErrorClient(),  # type: ignore[arg-type]
            "/commentThreads",
            params={"videoId": "vid-1"},
        )

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(_run())


def test_collect_replies_by_parent_id_handles_dedup_and_paging(monkeypatch: Any) -> None:
    collector = YouTubeCommentCollector(api_key="test-key", top_n=1, replies_per_comment=5)
    payloads = [
        {
            "items": [
                {"id": "reply-1", "snippet": {"textDisplay": "dup"}},
                {"id": "reply-2", "snippet": {"textDisplay": "ok-2"}},
            ],
            "nextPageToken": "next-1",
        },
        {
            "items": [
                {"id": "reply-3", "snippet": {"textDisplay": "ok-3"}},
            ]
        },
    ]

    async def _fake_request_json(
        _client: Any, path: str, *, params: dict[str, Any]
    ) -> dict[str, Any]:
        assert path == "/comments"
        assert params["parentId"] == "parent-1"
        return payloads.pop(0)

    monkeypatch.setattr(collector, "_request_json", _fake_request_json)

    async def _run() -> list[dict[str, Any]]:
        return await collector._collect_replies_by_parent_id(
            client=object(),  # type: ignore[arg-type]
            parent_id="parent-1",
            remaining_limit=2,
            existing_reply_ids={"reply-1"},
        )

    replies = asyncio.run(_run())
    assert [item["reply_id"] for item in replies] == ["reply-2", "reply-3"]


def test_collect_sorts_likes_and_limits_top_n(monkeypatch: Any) -> None:
    collector = YouTubeCommentCollector(
        api_key="test-key",
        top_n=2,
        replies_per_comment=0,
        retry_attempts=0,
    )

    async def _fake_request_json(_: Any, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        assert path == "/commentThreads"
        assert params["videoId"] == "abc123xyz09"
        return {
            "items": [
                {"id": "thread-1", "snippet": {"topLevelComment": {"snippet": {"likeCount": 1}}}},
                {"id": "thread-2", "snippet": {"topLevelComment": {"snippet": {"likeCount": 9}}}},
                "invalid-item",
            ]
        }

    monkeypatch.setattr(collector, "_request_json", _fake_request_json)
    payload = asyncio.run(
        collector.collect(
            source_url="https://www.youtube.com/watch?v=abc123xyz09",
            video_uid="",
        )
    )

    assert payload["top_n"] == 2
    assert len(payload["top_comments"]) == 2
    assert payload["top_comments"][0]["comment_id"] == "thread-2"
    assert payload["top_comments"][1]["comment_id"] == "thread-1"


def test_collect_validates_api_key_and_video_id() -> None:
    missing_key_collector = YouTubeCommentCollector(api_key="", top_n=1, replies_per_comment=0)
    with pytest.raises(ValueError, match="youtube_api_key_missing"):
        asyncio.run(missing_key_collector.collect(source_url="https://youtu.be/a", video_uid=""))

    collector = YouTubeCommentCollector(api_key="ok", top_n=1, replies_per_comment=0)
    with pytest.raises(ValueError, match="youtube_video_id_not_resolved"):
        asyncio.run(collector.collect(source_url="https://example.com/nope", video_uid=""))
