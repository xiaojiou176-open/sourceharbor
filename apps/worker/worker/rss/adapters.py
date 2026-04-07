from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from worker.config import Settings
from worker.rss.fetcher import RSSHubFetcher
from worker.rss.normalizer import normalize_entry


@dataclass(frozen=True)
class NormalizedSource:
    adapter_type: str
    feed_url: str
    platform: str
    source_type: str
    source_value: str


class SourceAdapter(Protocol):
    adapter_type: str

    def normalize(
        self, *, settings: Settings, subscription: dict[str, Any]
    ) -> NormalizedSource: ...

    async def fetch(
        self,
        *,
        fetcher: RSSHubFetcher,
        source: NormalizedSource,
    ) -> list[dict[str, Any]]: ...

    def parse(
        self,
        *,
        source: NormalizedSource,
        entry: dict[str, Any],
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class _BaseAdapter:
    adapter_type: str

    async def fetch(
        self,
        *,
        fetcher: RSSHubFetcher,
        source: NormalizedSource,
    ) -> list[dict[str, Any]]:
        fetched = await fetcher.fetch_many([source.feed_url])
        return list(fetched.get(source.feed_url, []))

    def parse(
        self,
        *,
        source: NormalizedSource,
        entry: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_entry(entry, source.feed_url)
        if not normalized.get("video_platform"):
            normalized["video_platform"] = source.platform or "generic"
        return normalized


@dataclass(frozen=True)
class RSSHubRouteAdapter(_BaseAdapter):
    adapter_type: str = "rsshub_route"

    def normalize(self, *, settings: Settings, subscription: dict[str, Any]) -> NormalizedSource:
        route = str(subscription.get("rsshub_route") or "").strip()
        if route.startswith(("http://", "https://")):
            feed_url = route
        else:
            base = settings.rsshub_base_url.rstrip("/")
            path = route if route.startswith("/") else f"/{route}"
            feed_url = f"{base}{path}"
        return NormalizedSource(
            adapter_type=self.adapter_type,
            feed_url=feed_url,
            platform=str(subscription.get("platform") or "").strip().lower() or "generic",
            source_type=str(subscription.get("source_type") or "").strip(),
            source_value=str(subscription.get("source_value") or "").strip(),
        )


@dataclass(frozen=True)
class RSSGenericAdapter(_BaseAdapter):
    adapter_type: str = "rss_generic"

    def normalize(self, *, settings: Settings, subscription: dict[str, Any]) -> NormalizedSource:
        del settings
        source_url = str(subscription.get("source_url") or "").strip()
        if not source_url.startswith(("http://", "https://")):
            raise ValueError("source_url is required when adapter_type=rss_generic")
        return NormalizedSource(
            adapter_type=self.adapter_type,
            feed_url=source_url,
            platform=str(subscription.get("platform") or "").strip().lower() or "generic",
            source_type=str(subscription.get("source_type") or "").strip(),
            source_value=str(subscription.get("source_value") or "").strip(),
        )


_ADAPTERS: dict[str, SourceAdapter] = {
    "rsshub_route": RSSHubRouteAdapter(),
    "rss_generic": RSSGenericAdapter(),
}


def get_adapter(subscription: dict[str, Any]) -> SourceAdapter:
    adapter_type = str(subscription.get("adapter_type") or "").strip().lower() or "rsshub_route"
    adapter = _ADAPTERS.get(adapter_type)
    if adapter is None:
        raise ValueError(f"unsupported adapter_type: {adapter_type}")
    return adapter


def resolve_feed_url(settings: Settings, subscription: dict[str, Any]) -> str:
    adapter = get_adapter(subscription)
    source = adapter.normalize(settings=settings, subscription=subscription)
    return source.feed_url


async def poll_subscription_entries(
    *,
    settings: Settings,
    fetcher: RSSHubFetcher,
    subscription: dict[str, Any],
) -> tuple[NormalizedSource, list[dict[str, Any]]]:
    adapter = get_adapter(subscription)
    source = adapter.normalize(settings=settings, subscription=subscription)
    raw_entries = await adapter.fetch(fetcher=fetcher, source=source)
    normalized_entries = [adapter.parse(source=source, entry=entry) for entry in raw_entries]
    return source, normalized_entries
