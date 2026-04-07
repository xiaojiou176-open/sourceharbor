from __future__ import annotations

import asyncio

import pytest
from worker.rss.fetcher import RSSHubFetcher, parse_feed


def test_parse_rss_feed_extracts_title_link_and_guid() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>demo</title>
        <item>
          <title>Video A</title>
          <link>https://www.youtube.com/watch?v=abc123</link>
          <guid>guid-1</guid>
          <pubDate>Mon, 19 Feb 2024 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    entries = parse_feed(xml)

    assert len(entries) == 1
    assert entries[0]["title"] == "Video A"
    assert entries[0]["link"] == "https://www.youtube.com/watch?v=abc123"
    assert entries[0]["guid"] == "guid-1"


def test_parse_atom_feed_extracts_link_href() -> None:
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Atom</title>
      <entry>
        <title>Video B</title>
        <id>tag:example.com,2024:2</id>
        <link href="https://www.bilibili.com/video/BV1xx411c7mD"/>
        <updated>2024-02-20T12:00:00Z</updated>
      </entry>
    </feed>
    """

    entries = parse_feed(xml)

    assert len(entries) == 1
    assert entries[0]["title"] == "Video B"
    assert entries[0]["link"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert entries[0]["guid"] == "tag:example.com,2024:2"


def test_fetch_many_propagates_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = RSSHubFetcher(retry_attempts=0)

    async def _fake_fetch_one(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(fetcher, "_fetch_one", _fake_fetch_one)

    async def _run() -> None:
        await fetcher.fetch_many(["https://rss.example.com/feed.xml"])

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run())
