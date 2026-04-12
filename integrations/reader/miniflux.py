from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib import error, parse, request

DEFAULT_IMPORT_FEED_URL = "https://miniflux.app/feed.xml"
DEFAULT_SYNC_LIMIT = 20


def env(
    name: str, environ_get: Callable[[str, str | None], str | None], default: str | None = None
) -> str:
    value = environ_get(name, default)
    if value is None:
        raise RuntimeError(f"Missing env: {name}")
    return value


def build_headers(
    *,
    environ_get: Callable[[str, str], str],
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "sourceharbor/1.0",
    }
    token = environ_get("MINIFLUX_API_TOKEN", "").strip()
    if token:
        headers["X-Auth-Token"] = token
        return headers

    user = environ_get("MINIFLUX_ADMIN_USERNAME", "admin").strip()
    password = environ_get("MINIFLUX_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("MINIFLUX_API_TOKEN missing and MINIFLUX_ADMIN_PASSWORD empty")
    basic = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    headers["Authorization"] = f"Basic {basic}"
    return headers


def http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> Any:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=20) as resp:  # nosec B310
            body = resp.read().decode("utf-8")
            if not body:
                return None
            return json.loads(body)
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {body[:500]}") from exc


def is_duplicate_entry_error(exc: Exception) -> bool:
    message = str(exc)
    lowered = message.lower()
    return (
        "entries_feed_id_hash_key" in message
        or "duplicate key value violates unique constraint" in lowered
        or "already exists" in lowered
    )


def ensure_category_and_feed(base: str, headers: dict[str, str]) -> int:
    return ensure_category_and_feed_with_http_json(base, headers, http_json_fn=http_json)


def ensure_category_and_feed_with_http_json(
    base: str,
    headers: dict[str, str],
    *,
    http_json_fn: Callable[..., Any],
) -> int:
    seed_feed_url = DEFAULT_IMPORT_FEED_URL
    categories = http_json_fn("GET", f"{base}/v1/categories", headers) or []
    category_id = None
    for c in categories:
        if str(c.get("title", "")).strip().lower() == "clipsieve":
            category_id = int(c["id"])
            break
    if category_id is None:
        created = (
            http_json_fn("POST", f"{base}/v1/categories", headers, {"title": "SourceHarbor"}) or {}
        )
        category_id = int(created.get("id"))

    feeds = http_json_fn("GET", f"{base}/v1/feeds", headers) or []
    for f in feeds:
        if str(f.get("feed_url", "")).strip() == seed_feed_url:
            return int(f["id"])

    created_feed = (
        http_json_fn(
            "POST",
            f"{base}/v1/feeds",
            headers,
            {
                "feed_url": seed_feed_url,
                "category_id": category_id,
                "crawler": True,
                "disabled": False,
            },
        )
        or {}
    )
    feed_id = created_feed.get("feed_id", created_feed.get("id"))
    if feed_id is not None:
        return int(feed_id)

    feeds = http_json_fn("GET", f"{base}/v1/feeds", headers) or []
    for f in feeds:
        if str(f.get("feed_url", "")).strip() == seed_feed_url:
            return int(f["id"])
    raise RuntimeError("failed to resolve feed id after feed creation")


def get_feed_items(api_base: str, limit: int) -> list[dict[str, Any]]:
    query = parse.urlencode({"limit": limit})
    with request.urlopen(f"{api_base}/api/v1/feed/digests?{query}", timeout=20) as resp:  # nosec B310
        payload = json.loads(resp.read().decode("utf-8"))
    return list(payload.get("items", []))


def to_unix(ts: str) -> int:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.now(UTC)
    return int(dt.timestamp())


def import_entries(
    base: str,
    headers: dict[str, str],
    feed_id: int,
    items: list[dict[str, Any]],
) -> int:
    return import_entries_with_http_json(
        base,
        headers,
        feed_id,
        items,
        http_json_fn=http_json,
    )


def import_entries_with_http_json(
    base: str,
    headers: dict[str, str],
    feed_id: int,
    items: list[dict[str, Any]],
    *,
    http_json_fn: Callable[..., Any],
) -> int:
    imported = 0
    for item in items:
        job_id = str(item.get("job_id") or "").strip()
        title = (
            str(item.get("title") or "").strip()
            or f"AI Digest {job_id or int(datetime.now(UTC).timestamp())}"
        )
        summary = str(item.get("summary_md") or "").strip()
        url = (
            str(item.get("video_url") or "").strip() or f"https://local.sourceharbor/jobs/{job_id}"
        )
        if not summary:
            continue
        payload = {
            "title": title,
            "url": url,
            "content": summary,
            "author": "SourceHarbor",
            "status": "unread",
            "external_id": f"sourceharbor:{job_id}",
            "published_at": to_unix(str(item.get("published_at") or "")),
        }
        try:
            http_json_fn("POST", f"{base}/v1/feeds/{feed_id}/entries/import", headers, payload)
        except RuntimeError as exc:
            if is_duplicate_entry_error(exc):
                continue
            raise
        imported += 1
    return imported
