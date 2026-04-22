from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from integrations.providers.bilibili_comments import (
    build_bilibili_headers,
    create_bilibili_client,
    extract_aid_from_url,
    extract_bvid,
    request_bilibili_json,
)

logger = logging.getLogger(__name__)

_DANMAKU_BASE = "https://comment.bilibili.com"


def _to_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _official_title(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return _clean(payload.get("title") or payload.get("desc"))


def _normalize_pages(pages: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(pages, list):
        return normalized
    for item in pages:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("part") or item.get("title"))
        normalized.append(
            {
                "cid": _to_int(item.get("cid"), default=0),
                "page": _to_int(item.get("page"), default=0),
                "title": title or "Untitled segment",
                "duration": _to_int(item.get("duration"), default=0),
            }
        )
    return normalized


def build_bilibili_rich_metadata(
    view_payload: dict[str, Any],
    *,
    creator_profile: dict[str, Any] | None = None,
    creator_relation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    owner = view_payload.get("owner") if isinstance(view_payload.get("owner"), dict) else {}
    stat = view_payload.get("stat") if isinstance(view_payload.get("stat"), dict) else {}
    pages = _normalize_pages(view_payload.get("pages"))
    creator_profile = creator_profile if isinstance(creator_profile, dict) else {}
    creator_relation = creator_relation if isinstance(creator_relation, dict) else {}
    uploader_mid = _clean(owner.get("mid"))
    uploader_url = f"https://space.bilibili.com/{uploader_mid}" if uploader_mid else ""
    uploader_sign = _clean(creator_profile.get("sign")) or None
    uploader_level = _to_int(creator_profile.get("level"), default=0) or None
    uploader_follower_count = _to_int(creator_relation.get("follower"), default=0)
    uploader_following_count = _to_int(creator_relation.get("following"), default=0)
    uploader_verified_label = _official_title(creator_profile.get("official")) or None
    metadata: dict[str, Any] = {
        "bilibili_aid": _to_int(view_payload.get("aid"), default=0) or None,
        "bilibili_bvid": _clean(view_payload.get("bvid")) or None,
        "bilibili_cid": _to_int(view_payload.get("cid"), default=0) or None,
        "uploader_mid": uploader_mid or None,
        "uploader_url": uploader_url or None,
        "uploader_avatar": _clean(owner.get("face")) or None,
        "uploader_sign": uploader_sign,
        "uploader_level": uploader_level,
        "uploader_follower_count": uploader_follower_count or None,
        "uploader_following_count": uploader_following_count or None,
        "uploader_verified_label": uploader_verified_label,
        "view_count": _to_int(stat.get("view"), default=0),
        "like_count": _to_int(stat.get("like"), default=0),
        "comment_count": _to_int(stat.get("reply"), default=0),
        "danmaku_count": _to_int(stat.get("danmaku"), default=0),
        "coin_count": _to_int(stat.get("coin"), default=0),
        "favorite_count": _to_int(stat.get("favorite"), default=0),
        "share_count": _to_int(stat.get("share"), default=0),
        "category": _clean(view_payload.get("tname")) or None,
        "category_id": _to_int(view_payload.get("tid"), default=0) or None,
        "thumbnail": _clean(view_payload.get("pic")) or None,
        "chapters": pages,
        "site_objects": {
            "owner": {
                "mid": uploader_mid or None,
                "name": _clean(owner.get("name") or owner.get("uname")) or None,
                "avatar_url": _clean(owner.get("face")) or None,
            },
            "creator_profile": {
                "sign": uploader_sign,
                "level": uploader_level,
                "official_title": uploader_verified_label,
            },
            "creator_relation": {
                "follower": uploader_follower_count,
                "following": uploader_following_count,
            },
            "stat": {
                "view": _to_int(stat.get("view"), default=0),
                "like": _to_int(stat.get("like"), default=0),
                "reply": _to_int(stat.get("reply"), default=0),
                "danmaku": _to_int(stat.get("danmaku"), default=0),
                "coin": _to_int(stat.get("coin"), default=0),
                "favorite": _to_int(stat.get("favorite"), default=0),
                "share": _to_int(stat.get("share"), default=0),
            },
            "pages": pages,
        },
    }
    if not metadata["thumbnail"]:
        metadata.pop("thumbnail")
    return metadata


def parse_bilibili_danmaku_xml(xml_text: str, *, limit: int = 80) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    entries: list[dict[str, Any]] = []
    total_count = 0
    for node in root.findall("d"):
        total_count += 1
        if len(entries) >= max(1, limit):
            continue
        params = str(node.attrib.get("p") or "").split(",")
        entries.append(
            {
                "progress_s": round(_to_float(params[0] if len(params) > 0 else 0.0), 3),
                "mode": _to_int(params[1] if len(params) > 1 else 0),
                "font_size": _to_int(params[2] if len(params) > 2 else 0),
                "color": _to_int(params[3] if len(params) > 3 else 0),
                "sent_at": _to_int(params[4] if len(params) > 4 else 0),
                "pool": _to_int(params[5] if len(params) > 5 else 0),
                "user_hash": params[6] if len(params) > 6 else "",
                "row_id": params[7] if len(params) > 7 else "",
                "content": _clean(node.text),
            }
        )
    return {
        "status": "available" if total_count else "empty",
        "entry_count": len(entries),
        "total_count": total_count,
        "sampled": total_count > len(entries),
        "entries": entries,
    }


async def fetch_bilibili_rich_evidence(
    *,
    source_url: str,
    video_uid: str,
    request_timeout_seconds: float,
    cookie: str | None,
    async_client_cls: Any = httpx.AsyncClient,
) -> dict[str, Any]:
    identifier = _clean(video_uid)
    bvid = extract_bvid(identifier) or extract_bvid(source_url)
    aid = extract_aid_from_url(source_url, to_int=lambda value, default=0: _to_int(value, default=default))
    if aid is None and identifier.isdigit():
        aid = _to_int(identifier, default=0) or None

    params: dict[str, Any] = {}
    if bvid:
        params["bvid"] = bvid
    elif aid:
        params["aid"] = aid
    else:
        return {
            "metadata": {},
            "danmaku": {"status": "unavailable", "entry_count": 0, "entries": []},
        }

    async with create_bilibili_client(
        request_timeout_seconds=request_timeout_seconds,
        cookie=cookie,
        async_client_cls=async_client_cls,
    ) as client:
        async def _noop_throttle() -> None:
            return None

        view_payload = await request_bilibili_json(
            client,
            "/x/web-interface/view",
            params=params,
            retry_attempts=2,
            retry_backoff_seconds=0.5,
            throttle=_noop_throttle,
            logger_obj=logger,
            trace_id="bilibili_rich_evidence",
            user="bilibili_rich_evidence",
            to_int=lambda value, default=0: _to_int(value, default=default),
        )

    metadata = build_bilibili_rich_metadata(view_payload)
    uploader_mid = _clean(metadata.get("uploader_mid") or "")
    creator_profile: dict[str, Any] = {}
    creator_relation: dict[str, Any] = {}
    if uploader_mid:
        try:
            async with create_bilibili_client(
                request_timeout_seconds=request_timeout_seconds,
                cookie=cookie,
                async_client_cls=async_client_cls,
            ) as client:
                async def _noop_throttle() -> None:
                    return None

                creator_profile = await request_bilibili_json(
                    client,
                    "/x/space/acc/info",
                    params={"mid": uploader_mid},
                    retry_attempts=1,
                    retry_backoff_seconds=0.5,
                    throttle=_noop_throttle,
                    logger_obj=logger,
                    trace_id="bilibili_rich_evidence",
                    user="bilibili_creator_profile",
                    to_int=lambda value, default=0: _to_int(value, default=default),
                )
                creator_relation = await request_bilibili_json(
                    client,
                    "/x/relation/stat",
                    params={"vmid": uploader_mid},
                    retry_attempts=1,
                    retry_backoff_seconds=0.5,
                    throttle=_noop_throttle,
                    logger_obj=logger,
                    trace_id="bilibili_rich_evidence",
                    user="bilibili_creator_relation",
                    to_int=lambda value, default=0: _to_int(value, default=default),
                )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "bilibili_creator_profile_unavailable",
                extra={
                    "trace_id": "bilibili_rich_evidence",
                    "user": "bilibili_rich_evidence",
                    "error": str(exc),
                },
            )
    metadata = build_bilibili_rich_metadata(
        view_payload,
        creator_profile=creator_profile,
        creator_relation=creator_relation,
    )
    cid = _to_int(metadata.get("bilibili_cid"), default=0)
    danmaku = {"status": "unavailable", "entry_count": 0, "entries": []}
    if cid > 0:
        try:
            async with async_client_cls(
                timeout=httpx.Timeout(request_timeout_seconds),
                headers=build_bilibili_headers(cookie=cookie),
                follow_redirects=True,
            ) as client:
                response = await client.get(f"{_DANMAKU_BASE}/{cid}.xml")
                response.raise_for_status()
                danmaku = parse_bilibili_danmaku_xml(response.text)
                danmaku["cid"] = cid
                danmaku["source_url"] = f"{_DANMAKU_BASE}/{cid}.xml"
        except (httpx.HTTPError, ET.ParseError, UnicodeDecodeError, ValueError) as exc:
            danmaku = {
                "status": "unavailable",
                "cid": cid,
                "entry_count": 0,
                "entries": [],
                "reason": _clean(exc)[:240] or "danmaku_fetch_failed",
            }

    return {"metadata": metadata, "danmaku": danmaku}
