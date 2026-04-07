from __future__ import annotations

import asyncio

from worker.config import Settings
from worker.rss.adapters import get_adapter, poll_subscription_entries, resolve_feed_url


def _settings() -> Settings:
    return Settings(
        sqlite_path=":memory:",
        database_url="sqlite+pysqlite:///:memory:",
        temporal_target_host="127.0.0.1:7233",
        temporal_namespace="default",
        temporal_task_queue="sourceharbor-worker",
        rsshub_base_url="https://rsshub.app",
    )


def test_resolve_feed_url_rsshub_route_adapter() -> None:
    settings = _settings()
    subscription = {"adapter_type": "rsshub_route", "rsshub_route": "/youtube/channel/demo"}
    assert resolve_feed_url(settings, subscription) == "https://rsshub.app/youtube/channel/demo"


def test_resolve_feed_url_rss_generic_adapter() -> None:
    settings = _settings()
    subscription = {"adapter_type": "rss_generic", "source_url": "https://example.com/feed.xml"}
    assert resolve_feed_url(settings, subscription) == "https://example.com/feed.xml"


def test_adapter_normalize_returns_structured_source() -> None:
    settings = _settings()
    subscription = {
        "adapter_type": "rsshub_route",
        "rsshub_route": "/youtube/channel/demo",
        "platform": "youtube",
        "source_type": "youtube_channel_id",
        "source_value": "demo",
    }
    adapter = get_adapter(subscription)
    source = adapter.normalize(settings=settings, subscription=subscription)

    assert source.adapter_type == "rsshub_route"
    assert source.feed_url == "https://rsshub.app/youtube/channel/demo"
    assert source.platform == "youtube"


def test_adapter_fetch_and_parse_flow() -> None:
    settings = _settings()
    subscription = {
        "adapter_type": "rss_generic",
        "source_url": "https://example.com/feed.xml",
        "platform": "rss_generic",
        "source_type": "url",
        "source_value": "https://example.com/feed.xml",
    }

    class _Fetcher:
        async def fetch_many(self, urls):
            assert list(urls) == ["https://example.com/feed.xml"]
            return {
                "https://example.com/feed.xml": [
                    {
                        "title": "Example",
                        "link": "https://example.com/p/1",
                        "guid": "g-1",
                        "published_at": "2026-02-23T10:00:00Z",
                    }
                ]
            }

    source, entries = asyncio.run(
        poll_subscription_entries(
            settings=settings,
            fetcher=_Fetcher(),  # type: ignore[arg-type]
            subscription=subscription,
        )
    )
    assert source.adapter_type == "rss_generic"
    assert len(entries) == 1
    assert entries[0]["video_platform"] == "rss_generic"
    assert entries[0]["entry_hash"]
