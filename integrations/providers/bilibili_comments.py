from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

BILIBILI_API_BASE = "https://api.bilibili.com"
BILIBILI_VIDEO_TYPE = 1
BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"}
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}


def build_bilibili_headers(*, cookie: str | None = None) -> dict[str, str]:
    headers = dict(DEFAULT_HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    return headers


def create_bilibili_client(
    *,
    request_timeout_seconds: float,
    cookie: str | None = None,
    async_client_cls: Any = httpx.AsyncClient,
) -> httpx.AsyncClient:
    timeout = httpx.Timeout(request_timeout_seconds)
    headers = build_bilibili_headers(cookie=cookie)
    return async_client_cls(
        base_url=BILIBILI_API_BASE,
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    )


def extract_bvid(text: str) -> str | None:
    match = re.search(r"(BV[0-9A-Za-z]+)", text)
    if not match:
        return None
    return match.group(1)


def extract_aid_from_url(source_url: str | None, *, to_int: Any) -> int | None:
    if not source_url:
        return None
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    if host not in BILIBILI_HOSTS:
        return None

    aid_match = re.search(r"/video/av(\d+)", parsed.path)
    if aid_match:
        return to_int(aid_match.group(1), default=0) or None

    query = parse_qs(parsed.query)
    aid_values = query.get("aid") or []
    if aid_values:
        aid = to_int(aid_values[0], default=0)
        if aid > 0:
            return aid
    return None


async def request_bilibili_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, Any],
    retry_attempts: int,
    retry_backoff_seconds: float,
    throttle: Any,
    logger_obj: logging.Logger,
    trace_id: str,
    user: str,
    to_int: Any,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retry_attempts + 1):
        await throttle()
        try:
            response = await client.get(path, params=params)
            if response.status_code in {412, 429}:
                raise httpx.HTTPStatusError(
                    f"rate_limited:{response.status_code}",
                    request=response.request,
                    response=response,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            if response.status_code >= 400:
                response.raise_for_status()
            payload = response.json()
            code = to_int(payload.get("code"), default=0)
            if code != 0:
                raise ValueError(
                    f"bilibili_api_error:{code}:{str(payload.get('message') or payload.get('msg') or '').strip()}"
                )
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return {}
        except (
            httpx.TimeoutException,
            httpx.RequestError,
            httpx.HTTPStatusError,
            ValueError,
        ) as exc:
            last_error = exc
            logger_obj.warning(
                "bilibili_api_request_retry",
                extra={
                    "trace_id": trace_id,
                    "user": user,
                    "path": path,
                    "attempt": attempt + 1,
                    "max_attempts": retry_attempts + 1,
                    "error": str(exc),
                },
            )
            if attempt >= retry_attempts:
                break
            await asyncio.sleep(retry_backoff_seconds * float(2**attempt))

    if last_error is not None:
        logger_obj.error(
            "bilibili_api_request_failed",
            extra={"trace_id": trace_id, "user": user, "path": path, "error": str(last_error)},
        )
        raise last_error
    raise RuntimeError("bilibili_request_failed")
