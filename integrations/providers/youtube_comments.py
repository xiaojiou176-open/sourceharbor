from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
}


def create_youtube_client(
    *,
    request_timeout_seconds: float,
    async_client_cls: Any = httpx.AsyncClient,
) -> httpx.AsyncClient:
    timeout = httpx.Timeout(request_timeout_seconds)
    return async_client_cls(base_url=YOUTUBE_API_BASE, timeout=timeout)


def extract_video_id(source_url: str | None, video_uid: str | None) -> str:
    uid = str(video_uid or "").strip()
    if uid:
        return uid

    url = str(source_url or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        return ""

    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0]

    query = parse_qs(parsed.query)
    values = query.get("v") or []
    if values:
        return str(values[0]).strip()

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "shorts":
        return parts[1]
    return ""


async def request_youtube_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, Any],
    retry_attempts: int,
    retry_backoff_seconds: float,
    logger_obj: logging.Logger,
    trace_id: str,
    user: str,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retry_attempts + 1):
        try:
            response = await client.get(path, params=params)
            if response.status_code >= 400:
                response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {}
        except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_error = exc
            logger_obj.warning(
                "youtube_api_request_retry",
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
            "youtube_api_request_failed",
            extra={"trace_id": trace_id, "user": user, "path": path, "error": str(last_error)},
        )
        raise last_error
    raise RuntimeError("youtube_request_failed")
