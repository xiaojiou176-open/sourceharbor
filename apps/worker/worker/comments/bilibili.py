from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from integrations.providers.bilibili_comments import (
    BILIBILI_VIDEO_TYPE,
    create_bilibili_client,
    extract_aid_from_url,
    extract_bvid,
    request_bilibili_json,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def empty_comments_payload(*, sort: str = "like") -> dict[str, Any]:
    return {
        "sort": sort,
        "top_comments": [],
        "replies": {},
        "fetched_at": _utc_now_iso(),
    }


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ts_to_iso(ts: Any) -> str | None:
    ts_int = _to_int(ts, default=-1)
    if ts_int < 0:
        return None
    return datetime.fromtimestamp(ts_int, tz=UTC).replace(microsecond=0).isoformat()


def _extract_bvid(text: str) -> str | None:
    return extract_bvid(text)


class BilibiliCommentCollector:
    def __init__(
        self,
        *,
        top_n: int = 10,
        replies_per_comment: int = 10,
        request_timeout_seconds: float = 10.0,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 0.5,
        min_request_interval_seconds: float = 0.2,
        cookie: str | None = None,
    ) -> None:
        self._top_n = max(1, int(top_n))
        self._replies_per_comment = max(1, int(replies_per_comment))
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._retry_attempts = max(0, int(retry_attempts))
        self._retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._min_request_interval_seconds = max(0.0, float(min_request_interval_seconds))
        self._cookie = str(cookie or "").strip()
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def collect(
        self,
        *,
        source_url: str | None,
        video_uid: str | None,
    ) -> dict[str, Any]:
        self._log_trace_id = uuid4().hex
        self._log_user = "bilibili_comment_collector"
        logger.info(
            "bilibili_comment_collect_started",
            extra={
                "trace_id": self._log_trace_id,
                "user": self._log_user,
                "source_url_present": bool(str(source_url or "").strip()),
                "video_uid_present": bool(str(video_uid or "").strip()),
            },
        )
        async with create_bilibili_client(
            request_timeout_seconds=self._request_timeout_seconds,
            cookie=self._cookie,
            async_client_cls=httpx.AsyncClient,
        ) as client:
            aid = await self._resolve_aid(client=client, source_url=source_url, video_uid=video_uid)
            if aid <= 0:
                raise ValueError("bilibili_aid_not_resolved")

            top_comments = await self._fetch_top_comments(client=client, aid=aid)
            replies_index: dict[str, list[dict[str, Any]]] = {}
            for item in top_comments:
                root_id = _to_int(item.get("comment_id"), default=0)
                replies = await self._fetch_replies(client=client, aid=aid, root_id=root_id)
                item["replies"] = replies
                replies_index[str(item.get("comment_id") or "")] = replies

        payload = {
            "sort": "like",
            "top_comments": top_comments,
            "replies": replies_index,
            "fetched_at": _utc_now_iso(),
        }
        logger.info(
            "bilibili_comment_collect_succeeded",
            extra={
                "trace_id": self._log_trace_id,
                "user": self._log_user,
                "top_comment_count": len(top_comments),
                "reply_bucket_count": len(replies_index),
            },
        )
        return payload

    async def _throttle(self) -> None:
        if self._min_request_interval_seconds <= 0:
            return
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            elapsed = now - self._last_request_at
            if elapsed < self._min_request_interval_seconds:
                await asyncio.sleep(self._min_request_interval_seconds - elapsed)
                now = loop.time()
            self._last_request_at = now

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        return await request_bilibili_json(
            client,
            path,
            params=params,
            retry_attempts=self._retry_attempts,
            retry_backoff_seconds=self._retry_backoff_seconds,
            throttle=self._throttle,
            logger_obj=logger,
            trace_id=str(getattr(self, "_log_trace_id", "missing_trace")),
            user=str(getattr(self, "_log_user", "bilibili_comment_collector")),
            to_int=_to_int,
        )

    def _extract_aid_from_url(self, source_url: str | None) -> int | None:
        return extract_aid_from_url(source_url, to_int=_to_int)

    async def _resolve_aid(
        self,
        *,
        client: httpx.AsyncClient,
        source_url: str | None,
        video_uid: str | None,
    ) -> int:
        uid = str(video_uid or "").strip()
        if uid.isdigit():
            return int(uid)
        if uid.lower().startswith("av") and uid[2:].isdigit():
            return int(uid[2:])

        aid_from_url = self._extract_aid_from_url(source_url)
        if aid_from_url:
            return aid_from_url

        bvid = _extract_bvid(uid) if uid else None
        if not bvid and source_url:
            bvid = _extract_bvid(source_url)
        if not bvid:
            return 0

        data = await self._request_json(client, "/x/web-interface/view", params={"bvid": bvid})
        return _to_int(data.get("aid"), default=0)

    def _normalize_comment(self, item: dict[str, Any]) -> dict[str, Any]:
        member = item.get("member") or {}
        content = item.get("content") or {}
        return {
            "comment_id": str(item.get("rpid") or ""),
            "author": str(member.get("uname") or "unknown"),
            "author_mid": str(member.get("mid") or ""),
            "content": str(content.get("message") or "").strip(),
            "like_count": _to_int(item.get("like"), default=0),
            "published_at": _ts_to_iso(item.get("ctime")),
            "replies": [],
        }

    async def _fetch_top_comments(
        self,
        *,
        client: httpx.AsyncClient,
        aid: int,
    ) -> list[dict[str, Any]]:
        data = await self._request_json(
            client,
            "/x/v2/reply/main",
            params={
                "type": BILIBILI_VIDEO_TYPE,
                "oid": aid,
                "mode": 3,
                "next": 0,
                "ps": self._top_n,
            },
        )
        comments = data.get("replies") or []
        if not isinstance(comments, list):
            return []

        normalized = [self._normalize_comment(item) for item in comments if isinstance(item, dict)]
        normalized.sort(key=lambda item: _to_int(item.get("like_count"), default=0), reverse=True)
        return normalized[: self._top_n]

    async def _fetch_replies(
        self,
        *,
        client: httpx.AsyncClient,
        aid: int,
        root_id: int,
    ) -> list[dict[str, Any]]:
        if root_id <= 0:
            return []
        data = await self._request_json(
            client,
            "/x/v2/reply/reply",
            params={
                "type": BILIBILI_VIDEO_TYPE,
                "oid": aid,
                "root": root_id,
                "on": 1,
                "ps": self._replies_per_comment,
            },
        )
        replies = data.get("replies") or []
        if not isinstance(replies, list):
            return []

        normalized: list[dict[str, Any]] = []
        for reply in replies:
            if not isinstance(reply, dict):
                continue
            item = self._normalize_comment(reply)
            item["replies"] = []
            normalized.append(item)
        normalized.sort(key=lambda item: _to_int(item.get("like_count"), default=0), reverse=True)
        return normalized[: self._replies_per_comment]
