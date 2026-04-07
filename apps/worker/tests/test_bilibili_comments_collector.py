from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
from worker.comments.bilibili import (
    BilibiliCommentCollector,
    _extract_bvid,
    _to_int,
    _ts_to_iso,
    empty_comments_payload,
)


def test_basic_helpers_cover_edge_inputs() -> None:
    payload = empty_comments_payload(sort="hot")
    assert payload["sort"] == "hot"
    assert payload["top_comments"] == []
    assert payload["replies"] == {}
    assert "T" in payload["fetched_at"]

    assert _to_int("12") == 12
    assert _to_int("x", default=7) == 7
    assert _ts_to_iso(-1) is None
    assert _extract_bvid("https://www.bilibili.com/video/BV1xx411c7mD") == "BV1xx411c7mD"
    assert _extract_bvid("https://example.com/no-bv") is None


def test_extract_aid_from_url_and_uid_resolution_paths() -> None:
    collector = BilibiliCommentCollector()
    assert collector._extract_aid_from_url("https://www.bilibili.com/video/av12345") == 12345
    assert collector._extract_aid_from_url("https://www.bilibili.com/video/BV1xx?aid=678") == 678
    assert collector._extract_aid_from_url("https://example.com/video/av1") is None

    async def _run() -> None:
        assert (
            await collector._resolve_aid(client=SimpleNamespace(), source_url=None, video_uid="123")
            == 123
        )
        assert (
            await collector._resolve_aid(
                client=SimpleNamespace(), source_url=None, video_uid="av456"
            )
            == 456
        )
        assert (
            await collector._resolve_aid(
                client=SimpleNamespace(),
                source_url="https://www.bilibili.com/video/av789",
                video_uid=None,
            )
            == 789
        )

        async def _fake_request_json(_client, _path, *, params):
            assert params == {"bvid": "BV1xx411c7mD"}
            return {"aid": 9527}

        collector._request_json = _fake_request_json  # type: ignore[method-assign]
        assert (
            await collector._resolve_aid(
                client=SimpleNamespace(),
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
                video_uid=None,
            )
            == 9527
        )

    asyncio.run(_run())


def test_top_comments_and_replies_are_sorted_and_limited() -> None:
    collector = BilibiliCommentCollector(top_n=2, replies_per_comment=1)

    async def _run() -> None:
        async def _fake_request_json(_client, path, *, params):
            if path.endswith("/main"):
                assert params["ps"] == 2
                return {
                    "replies": [
                        {
                            "rpid": 1,
                            "member": {"uname": "a", "mid": "1"},
                            "content": {"message": "m1"},
                            "like": 2,
                            "ctime": 100,
                        },
                        {
                            "rpid": 2,
                            "member": {"uname": "b", "mid": "2"},
                            "content": {"message": "m2"},
                            "like": 9,
                            "ctime": 101,
                        },
                        {
                            "rpid": 3,
                            "member": {"uname": "c", "mid": "3"},
                            "content": {"message": "m3"},
                            "like": 1,
                            "ctime": 102,
                        },
                    ]
                }
            assert path.endswith("/reply")
            return {
                "replies": [
                    {
                        "rpid": 11,
                        "member": {"uname": "x", "mid": "9"},
                        "content": {"message": "rx"},
                        "like": 3,
                        "ctime": 200,
                    },
                    {
                        "rpid": 12,
                        "member": {"uname": "y", "mid": "8"},
                        "content": {"message": "ry"},
                        "like": 7,
                        "ctime": 201,
                    },
                ]
            }

        collector._request_json = _fake_request_json  # type: ignore[method-assign]
        top = await collector._fetch_top_comments(client=SimpleNamespace(), aid=1)
        assert [item["comment_id"] for item in top] == ["2", "1"]

        replies = await collector._fetch_replies(client=SimpleNamespace(), aid=1, root_id=2)
        assert [item["comment_id"] for item in replies] == ["12"]
        assert await collector._fetch_replies(client=SimpleNamespace(), aid=1, root_id=0) == []

    asyncio.run(_run())


def test_request_json_retries_then_succeeds() -> None:
    collector = BilibiliCommentCollector(retry_attempts=1, retry_backoff_seconds=0.0)

    class _Client:
        def __init__(self):
            self.calls = 0

        async def get(self, _path, params=None):
            self.calls += 1
            if self.calls == 1:
                request = httpx.Request("GET", "https://api.bilibili.com/x/v2/reply/main")
                response = httpx.Response(429, request=request)
                raise httpx.HTTPStatusError("rate limited", request=request, response=response)
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"code": 0, "data": {"ok": True, "params": params}},
                raise_for_status=lambda: None,
            )

    async def _run() -> None:
        client = _Client()
        data = await collector._request_json(client, "/x/v2/reply/main", params={"oid": 1})
        assert data["ok"] is True
        assert client.calls == 2

    asyncio.run(_run())
