from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"}


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_hash_part(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean_text(value)).strip().lower()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _url_hash(url: str) -> str:
    return _sha256(_normalize_hash_part(url))


def _parse_published_at(value: str) -> datetime | None:
    raw = _clean_text(value)
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(raw)
    except Exception:
        return None


def extract_video_identity(url: str) -> tuple[str | None, str]:
    if not url:
        return None, _url_hash("missing-url")

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or ""
    query = parse_qs(parsed.query)

    if host in YOUTUBE_HOSTS:
        if query.get("v"):
            return "youtube", _clean_text(query["v"][0])

        if host == "youtu.be":
            candidate = _clean_text(path.strip("/").split("/")[0])
            if candidate:
                return "youtube", candidate

        return "youtube", _url_hash(url)

    if host in BILIBILI_HOSTS:
        bv_match = re.search(r"(BV[0-9A-Za-z]+)", path)
        if bv_match:
            return "bilibili", bv_match.group(1)
        return "bilibili", _url_hash(url)

    return None, _url_hash(url)


def make_entry_hash(
    *,
    feed_guid: str,
    feed_link: str,
    title: str,
    published_at: str,
) -> str:
    payload = "|".join(
        [
            _normalize_hash_part(feed_guid),
            _normalize_hash_part(feed_link),
            _normalize_hash_part(title),
            _normalize_hash_part(published_at),
        ]
    )
    return _sha256(payload)


def make_job_idempotency_key(platform: str, video_uid: str) -> str:
    return _sha256(f"{platform}:{video_uid}:video_digest_v1")


def make_article_idempotency_key(entry_hash: str) -> str:
    return _sha256(f"article:{_normalize_hash_part(entry_hash)}:rss_entry_v1")


def normalize_entry(raw_entry: Mapping[str, Any], feed_url: str) -> dict[str, Any]:
    title = _clean_text(raw_entry.get("title"))
    link = _clean_text(raw_entry.get("link"))
    guid = _clean_text(raw_entry.get("guid")) or link or title
    published_at_text = _clean_text(raw_entry.get("published_at"))
    summary = _clean_text(raw_entry.get("summary"))
    content = _clean_text(raw_entry.get("content"))

    video_platform, video_uid = extract_video_identity(link)
    entry_hash = make_entry_hash(
        feed_guid=guid,
        feed_link=link,
        title=title,
        published_at=published_at_text,
    )
    idempotency_key = make_job_idempotency_key(video_platform or "unknown", video_uid)
    content_type = "video" if video_platform else "article"

    return {
        "phase": "phase2",
        "source": {
            "feed_url": feed_url,
        },
        "title": title or None,
        "link": link,
        "guid": guid,
        "published_at": _parse_published_at(published_at_text),
        "summary": summary or None,
        "content": content or None,
        "video_platform": video_platform,
        "video_uid": video_uid,
        "entry_hash": entry_hash,
        "idempotency_key": idempotency_key,
        "content_type": content_type,
        "normalized_at": _utc_now_iso(),
        "raw": dict(raw_entry),
    }
