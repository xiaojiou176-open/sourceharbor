from __future__ import annotations

import ipaddress
import uuid
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..repositories import SubscriptionsRepository

_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.google.internal.",
    "100.100.100.200",
    "169.254.169.254",
}
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
_STRONG_VIDEO_SOURCES = {
    ("youtube", "youtube_channel_id"),
    ("youtube", "youtube_user"),
    ("bilibili", "bilibili_uid"),
}


def normalize_subscription_platform(raw: str) -> str:
    return str(raw or "").strip().lower() or "generic"


def normalize_subscription_source_type(raw: str) -> str:
    return str(raw or "").strip().lower() or "rsshub_route"


def is_strong_video_subscription(*, platform: str, source_type: str) -> bool:
    normalized_platform = normalize_subscription_platform(platform)
    normalized_source_type = normalize_subscription_source_type(source_type)
    return (normalized_platform, normalized_source_type) in _STRONG_VIDEO_SOURCES


def resolve_subscription_support_tier(*, platform: str, source_type: str) -> str:
    if is_strong_video_subscription(platform=platform, source_type=source_type):
        return "strong_supported"
    return "generic_supported"


def resolve_subscription_content_profile(
    *,
    platform: str,
    source_type: str,
    adapter_type: str | None,
) -> str:
    normalized_adapter = str(adapter_type or "").strip().lower()
    if normalized_adapter == "rss_generic":
        return "article"
    if is_strong_video_subscription(platform=platform, source_type=source_type):
        return "video"
    return "article"


def _validate_subscription_source_url(raw_url: str, *, field_name: str) -> str:
    value = str(raw_url or "").strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")

    parsed = urlparse(value)
    scheme = str(parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"{field_name} must use http or https")

    host = str(parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError(f"{field_name} host is required")

    if host in _BLOCKED_HOSTS or any(host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES):
        raise ValueError(f"{field_name} points to a blocked internal host")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return value

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise ValueError(f"{field_name} points to a blocked internal address")
    return value


def _derive_rsshub_route(platform: str, source_type: str, source_value: str) -> str:
    platform = normalize_subscription_platform(platform)
    source_type = normalize_subscription_source_type(source_type)
    if source_type == "url":
        return source_value
    if platform == "youtube" and source_type == "youtube_user":
        return f"/youtube/user/{source_value}"
    if platform == "bilibili" and source_type == "bilibili_uid":
        return f"/bilibili/user/video/{source_value}"
    if platform == "youtube" and source_type == "youtube_channel_id":
        return f"/youtube/channel/{source_value}"
    return source_value


def _resolve_adapter(
    *,
    platform: str,
    adapter_type: str | None,
    source_type: str,
    source_value: str,
    source_url: str | None,
    rsshub_route: str | None,
) -> tuple[str, str | None, str]:
    normalized_adapter = str(adapter_type or "").strip().lower() or "rsshub_route"
    normalized_source_url = str(source_url or "").strip() or None
    if normalized_source_url is not None:
        normalized_source_url = _validate_subscription_source_url(
            normalized_source_url,
            field_name="source_url",
        )

    if normalized_adapter == "rss_generic":
        resolved_source_url = normalized_source_url or source_value
        if not str(resolved_source_url or "").strip():
            raise ValueError("source_url is required for adapter_type=rss_generic")
        validated_source_url = _validate_subscription_source_url(
            str(resolved_source_url),
            field_name="source_url",
        )
        return "rss_generic", validated_source_url, validated_source_url

    if normalized_adapter != "rsshub_route":
        raise ValueError("adapter_type must be one of: rsshub_route, rss_generic")

    resolved_route = rsshub_route or _derive_rsshub_route(platform, source_type, source_value)
    return "rsshub_route", normalized_source_url, resolved_route


class SubscriptionsService:
    def __init__(self, db: Session | None, repo: SubscriptionsRepository | None = None) -> None:
        if repo is not None:
            self.repo = repo
            return
        if db is None:
            raise ValueError("db is required when repo is not provided")
        self.repo = SubscriptionsRepository(db)

    def list_subscriptions(
        self,
        *,
        platform: str | None = None,
        category: str | None = None,
        enabled_only: bool = False,
    ):
        return self.repo.list(platform=platform, category=category, enabled_only=enabled_only)

    def upsert_subscription(
        self,
        *,
        platform: str,
        source_type: str,
        source_value: str,
        adapter_type: str | None,
        source_url: str | None,
        rsshub_route: str | None,
        category: str | None,
        tags: list[str] | None,
        priority: int | None,
        enabled: bool,
    ):
        normalized_platform = normalize_subscription_platform(platform)
        normalized_source_type = normalize_subscription_source_type(source_type)
        if normalized_source_type == "url":
            _validate_subscription_source_url(source_value, field_name="source_value")
        resolved_adapter_type, resolved_source_url, resolved_route = _resolve_adapter(
            adapter_type=adapter_type,
            source_type=normalized_source_type,
            source_value=source_value,
            source_url=source_url,
            rsshub_route=rsshub_route,
            platform=normalized_platform,
        )
        resolved_category = (category or "misc").strip().lower()
        resolved_tags = [str(item).strip() for item in (tags or []) if str(item).strip()]
        resolved_priority = int(priority if priority is not None else 50)
        if resolved_priority < 0 or resolved_priority > 100:
            raise ValueError("priority must be in [0, 100]")
        return self.repo.upsert(
            platform=normalized_platform,
            source_type=normalized_source_type,
            source_value=source_value,
            adapter_type=resolved_adapter_type,
            source_url=resolved_source_url,
            rsshub_route=resolved_route,
            category=resolved_category,
            tags=resolved_tags,
            priority=resolved_priority,
            enabled=enabled,
        )

    def batch_update_category(
        self,
        *,
        ids: list[uuid.UUID],
        category: str,
    ) -> int:
        resolved_category = (category or "").strip().lower()
        if not resolved_category:
            raise ValueError("category is required")
        return self.repo.batch_update_category(ids=ids, category=resolved_category)

    def delete_subscription(self, subscription_id: uuid.UUID) -> bool:
        return self.repo.delete(subscription_id)
