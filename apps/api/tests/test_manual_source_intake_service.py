from __future__ import annotations

import asyncio
import types
import uuid

from apps.api.app.services.manual_source_intake import ManualSourceIntakeService


class _SubscriptionsStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def upsert_subscription(self, **kwargs):
        self.calls.append(dict(kwargs))
        source_value = str(kwargs["source_value"])
        created = not source_value.startswith("@existing")
        row = types.SimpleNamespace(
            id=uuid.uuid4(),
            platform=kwargs["platform"],
            source_type=kwargs["source_type"],
            source_value=source_value,
            source_url=kwargs["source_url"],
            rsshub_route=kwargs["rsshub_route"],
        )
        return row, created


class _VideosStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def process_video(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "job_id": str(uuid.uuid4()),
            "reused": kwargs["url"].endswith("reused"),
        }


def _build_service() -> ManualSourceIntakeService:
    return ManualSourceIntakeService(
        subscriptions_service=_SubscriptionsStub(),
        videos_service=_VideosStub(),
    )


def test_manual_source_plan_covers_creator_pages_video_urls_and_feeds() -> None:
    service = _build_service()

    youtube_handle = service.plan("https://www.youtube.com/@MindAmend")
    assert youtube_handle.recommended_action == "save_subscription"
    assert youtube_handle.source_type == "youtube_user"
    assert youtube_handle.rsshub_route == "/youtube/user/@MindAmend"

    bilibili_space = service.plan("https://space.bilibili.com/13416784")
    assert bilibili_space.recommended_action == "save_subscription"
    assert bilibili_space.source_type == "bilibili_uid"
    assert bilibili_space.source_value == "13416784"

    youtube_video = service.plan("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert youtube_video.recommended_action == "add_to_today"
    assert youtube_video.platform == "youtube"

    rsshub_route = service.plan("/36kr/newsflashes")
    assert rsshub_route.recommended_action == "save_subscription"
    assert rsshub_route.source_type == "rsshub_route"

    feed_url = service.plan("https://example.com/feed.xml")
    assert feed_url.recommended_action == "save_subscription"
    assert feed_url.adapter_type == "rss_generic"

    article_url = service.plan("https://example.com/posts/sourceharbor")
    assert article_url.recommended_action == "unsupported"
    assert article_url.target_kind == "unsupported"


def test_manual_source_submit_supports_partial_success_and_counts() -> None:
    service = _build_service()

    result = asyncio.run(
        service.submit(
            raw_input=(
                "https://space.bilibili.com/13416784\n"
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
                "https://example.com/feed.xml\n"
                "https://example.com/posts/sourceharbor"
            ),
            category="creator",
            tags=["ai", "daily"],
            priority=50,
            enabled=True,
        )
    )

    assert result["processed_count"] == 4
    assert result["created_subscriptions"] == 2
    assert result["updated_subscriptions"] == 0
    assert result["queued_manual_items"] == 1
    assert result["reused_manual_items"] == 0
    assert result["rejected_count"] == 1
    statuses = [item["status"] for item in result["results"]]
    assert statuses == ["created", "queued", "created", "rejected"]


def test_manual_source_plan_handles_empty_invalid_and_unsupported_urls() -> None:
    service = _build_service()

    empty_plan = service.plan("   ")
    assert empty_plan.recommended_action == "unsupported"
    assert empty_plan.message == "Empty line."

    ftp_plan = service.plan("ftp://example.com/feed.xml")
    assert ftp_plan.recommended_action == "unsupported"
    assert "Unsupported input" in ftp_plan.message

    youtube_plan = service.plan("https://www.youtube.com/playlist?list=abc")
    assert youtube_plan.recommended_action == "unsupported"
    assert "Unsupported YouTube URL" in youtube_plan.message

    bilibili_plan = service.plan("https://space.bilibili.com/not-a-uid")
    assert bilibili_plan.recommended_action == "unsupported"
    assert "Unsupported Bilibili URL" in bilibili_plan.message


def test_manual_source_submit_tracks_updates_and_reused_items() -> None:
    service = _build_service()

    result = asyncio.run(
        service.submit(
            raw_input="@existing-channel\nhttps://www.youtube.com/watch?v=reused",
            category="creator",
            tags=[],
            priority=10,
            enabled=False,
        )
    )

    assert result["created_subscriptions"] == 0
    assert result["updated_subscriptions"] == 1
    assert result["queued_manual_items"] == 0
    assert result["reused_manual_items"] == 1
    assert [item["status"] for item in result["results"]] == ["updated", "reused"]
