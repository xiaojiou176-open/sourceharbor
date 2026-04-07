from __future__ import annotations

import asyncio
from types import SimpleNamespace, TracebackType
from typing import Any, Self

import httpx
import pytest
from worker.comments.bilibili import BilibiliCommentCollector


class _FakeAsyncClient:
    last_kwargs: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    async def __aenter__(self) -> Self:
        _FakeAsyncClient.last_kwargs = dict(self._kwargs)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class _JSONResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: dict[str, Any],
        request_url: str = "https://api.bilibili.com/x/v2/reply/main",
        raise_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.request = httpx.Request("GET", request_url)
        self._payload = payload
        self._raise_error = raise_error

    def raise_for_status(self) -> None:
        if self._raise_error is not None:
            raise self._raise_error

    def json(self) -> dict[str, Any]:
        return self._payload


def test_collect_covers_cookie_and_reply_index(monkeypatch: Any) -> None:
    collector = BilibiliCommentCollector(cookie="SESSDATA=demo")

    monkeypatch.setattr("worker.comments.bilibili.httpx.AsyncClient", _FakeAsyncClient)

    async def _fake_resolve_aid(**_: Any) -> int:
        return 42

    async def _fake_top_comments(**_: Any) -> list[dict[str, Any]]:
        return [{"comment_id": "100", "content": "hello", "replies": []}]

    async def _fake_replies(**_: Any) -> list[dict[str, Any]]:
        return [{"comment_id": "101", "content": "reply", "replies": []}]

    collector._resolve_aid = _fake_resolve_aid  # type: ignore[method-assign]
    collector._fetch_top_comments = _fake_top_comments  # type: ignore[method-assign]
    collector._fetch_replies = _fake_replies  # type: ignore[method-assign]

    payload = asyncio.run(
        collector.collect(
            source_url="https://www.bilibili.com/video/BV1xx411c7mD",
            video_uid=None,
        )
    )

    assert payload["sort"] == "like"
    assert payload["top_comments"][0]["replies"][0]["comment_id"] == "101"
    assert payload["replies"]["100"][0]["content"] == "reply"
    assert _FakeAsyncClient.last_kwargs is not None
    assert _FakeAsyncClient.last_kwargs["headers"]["Cookie"] == "SESSDATA=demo"


def test_collect_raises_when_aid_not_resolved(monkeypatch: Any) -> None:
    collector = BilibiliCommentCollector()
    monkeypatch.setattr("worker.comments.bilibili.httpx.AsyncClient", _FakeAsyncClient)

    async def _fake_resolve_aid(**_: Any) -> int:
        return 0

    collector._resolve_aid = _fake_resolve_aid  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="bilibili_aid_not_resolved"):
        asyncio.run(
            collector.collect(
                source_url="https://www.bilibili.com/video/BV1xx411c7mD",
                video_uid=None,
            )
        )


def test_throttle_returns_immediately_when_interval_non_positive() -> None:
    collector = BilibiliCommentCollector(min_request_interval_seconds=0.0)
    before = collector._last_request_at
    asyncio.run(collector._throttle())
    assert collector._last_request_at == before


def test_request_json_rate_limit_exhaustion_raises_http_status_error() -> None:
    collector = BilibiliCommentCollector(retry_attempts=0, retry_backoff_seconds=0.0)

    class _Client:
        async def get(self, _path: str, params: dict[str, Any] | None = None) -> _JSONResponse:
            return _JSONResponse(status_code=429, payload={"code": 0, "data": {}})

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(collector._request_json(_Client(), "/x/v2/reply/main", params={"oid": 1}))


def test_request_json_handles_http_error_paths_and_api_code() -> None:
    collector = BilibiliCommentCollector(retry_attempts=0, retry_backoff_seconds=0.0)

    class _ServerErrClient:
        async def get(self, _path: str, params: dict[str, Any] | None = None) -> _JSONResponse:
            request = httpx.Request("GET", "https://api.bilibili.com/x/v2/reply/main")
            err = httpx.HTTPStatusError(
                "server_error", request=request, response=httpx.Response(500, request=request)
            )
            return _JSONResponse(status_code=500, payload={"code": 0}, raise_error=err)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            collector._request_json(_ServerErrClient(), "/x/v2/reply/main", params={"oid": 1})
        )

    class _ClientErrClient:
        async def get(self, _path: str, params: dict[str, Any] | None = None) -> _JSONResponse:
            request = httpx.Request("GET", "https://api.bilibili.com/x/v2/reply/main")
            err = httpx.HTTPStatusError(
                "client_error", request=request, response=httpx.Response(404, request=request)
            )
            return _JSONResponse(status_code=404, payload={"code": 0}, raise_error=err)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(
            collector._request_json(_ClientErrClient(), "/x/v2/reply/main", params={"oid": 1})
        )

    class _ApiCodeErrorClient:
        async def get(self, _path: str, params: dict[str, Any] | None = None) -> _JSONResponse:
            return _JSONResponse(status_code=200, payload={"code": -1, "message": "boom"})

    with pytest.raises(ValueError, match="bilibili_api_error"):
        asyncio.run(
            collector._request_json(_ApiCodeErrorClient(), "/x/v2/reply/main", params={"oid": 1})
        )


def test_request_json_returns_empty_dict_when_data_is_not_dict() -> None:
    collector = BilibiliCommentCollector(retry_attempts=0)

    class _Client:
        async def get(self, _path: str, params: dict[str, Any] | None = None) -> _JSONResponse:
            return _JSONResponse(status_code=200, payload={"code": 0, "data": ["not-dict"]})

    result = asyncio.run(collector._request_json(_Client(), "/x/v2/reply/main", params={"oid": 1}))
    assert result == {}


def test_resolve_aid_returns_zero_when_no_uid_and_no_bvid() -> None:
    collector = BilibiliCommentCollector()
    aid = asyncio.run(
        collector._resolve_aid(
            client=SimpleNamespace(),
            source_url=None,
            video_uid="not_a_valid_uid",
        )
    )
    assert aid == 0


def test_fetch_top_comments_and_replies_guard_non_list_payload() -> None:
    collector = BilibiliCommentCollector(replies_per_comment=2)

    async def _top_non_list(_client: Any, _path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        return {"replies": "bad-type"}

    collector._request_json = _top_non_list  # type: ignore[method-assign]
    top = asyncio.run(collector._fetch_top_comments(client=SimpleNamespace(), aid=1))
    assert top == []

    async def _replies_mixed(_client: Any, _path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "replies": [
                "skip-this",
                {
                    "rpid": 200,
                    "member": {"uname": "author", "mid": "1"},
                    "content": {"message": "hello"},
                    "like": 2,
                    "ctime": 100,
                },
            ]
        }

    collector._request_json = _replies_mixed  # type: ignore[method-assign]
    replies = asyncio.run(collector._fetch_replies(client=SimpleNamespace(), aid=1, root_id=1))
    assert len(replies) == 1
    assert replies[0]["comment_id"] == "200"

    async def _replies_non_list(
        _client: Any, _path: str, *, params: dict[str, Any]
    ) -> dict[str, Any]:
        return {"replies": "bad-type"}

    collector._request_json = _replies_non_list  # type: ignore[method-assign]
    empty = asyncio.run(collector._fetch_replies(client=SimpleNamespace(), aid=1, root_id=1))
    assert empty == []
