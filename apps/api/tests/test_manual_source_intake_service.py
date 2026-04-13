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
        self.matches: dict[str, dict[str, str]] = {}
        self.source_matches: dict[str, dict[str, str]] = {}
        self.reader_bridges: dict[str, dict[str, str | bool]] = {}

    async def process_article(self, **kwargs):
        job_suffix = kwargs["url"].replace("https://", "").replace("/", "-")
        video_db_id = str(uuid.uuid5(uuid.NAMESPACE_URL, kwargs["url"]))
        self.calls.append({"kind": "article", **dict(kwargs)})
        return {
            "job_id": job_suffix,
            "video_db_id": video_db_id,
            "reused": kwargs["url"].endswith("reused"),
        }

    async def process_video(self, **kwargs):
        job_suffix = kwargs["url"].replace("https://", "").replace("/", "-")
        video_db_id = str(uuid.uuid5(uuid.NAMESPACE_URL, kwargs["url"]))
        self.calls.append({"kind": "video", **dict(kwargs)})
        return {
            "job_id": job_suffix,
            "video_db_id": video_db_id,
            "reused": kwargs["url"].endswith("reused"),
        }

    def get_subscription_match_for_video(self, *, video_db_id: uuid.UUID):
        return self.matches.get(str(video_db_id))

    def infer_subscription_match_for_source(self, *, platform: str, source_url: str):
        del platform
        return self.source_matches.get(str(source_url))

    def get_reader_bridge_for_job(self, *, job_id: str):
        return self.reader_bridges.get(str(job_id))


def _build_service() -> ManualSourceIntakeService:
    return ManualSourceIntakeService(
        subscriptions_service=_SubscriptionsStub(),
        videos_service=_VideosStub(),
    )


class _DbStub:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = 0
        self.commits = 0

    def add(self, obj: object) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed += 1
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self) -> None:
        self.commits += 1


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
    assert article_url.recommended_action == "add_to_today"
    assert article_url.target_kind == "manual_source_item"
    assert article_url.content_profile == "article"


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
    assert result["queued_manual_items"] == 2
    assert result["reused_manual_items"] == 0
    assert result["rejected_count"] == 0
    statuses = [item["status"] for item in result["results"]]
    assert statuses == ["created", "queued", "created", "queued"]
    assert result["results"][0]["relation_kind"] == "new_source_universe"
    assert result["results"][1]["relation_kind"] == "manual_one_off"
    assert result["results"][3]["relation_kind"] == "manual_one_off"
    assert result["results"][1]["thumbnail_url"]
    assert result["results"][0]["avatar_label"]


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


def test_manual_source_plan_covers_raw_ids_short_urls_and_helper_paths() -> None:
    service = _build_service()

    assert service.iter_non_empty_lines(" \nalpha\n\n beta \n") == [(2, "alpha"), (4, "beta")]

    channel_id_plan = service.plan("UCabc12345")
    assert channel_id_plan.recommended_action == "save_subscription"
    assert channel_id_plan.source_type == "youtube_channel_id"

    bilibili_uid_plan = service.plan("13416784")
    assert bilibili_uid_plan.recommended_action == "save_subscription"
    assert bilibili_uid_plan.source_type == "bilibili_uid"

    youtube_short_url = service.plan("https://youtu.be/demo123")
    assert youtube_short_url.recommended_action == "add_to_today"

    youtube_shorts_url = service.plan("https://www.youtube.com/shorts/demo123")
    assert youtube_shorts_url.recommended_action == "add_to_today"

    youtube_channel_url = service.plan("https://www.youtube.com/channel/UCabc12345")
    assert youtube_channel_url.recommended_action == "save_subscription"
    assert youtube_channel_url.source_type == "youtube_channel_id"

    youtube_user_url = service.plan("https://www.youtube.com/user/sourceharbor")
    assert youtube_user_url.recommended_action == "save_subscription"
    assert youtube_user_url.source_value == "sourceharbor"

    bilibili_short_url = service.plan("https://b23.tv/demo123")
    assert bilibili_short_url.recommended_action == "add_to_today"

    bilibili_video_url = service.plan("https://www.bilibili.com/video/BV1xx411c7mD")
    assert bilibili_video_url.recommended_action == "add_to_today"

    assert service._creator_handle(source_type="youtube_user", source_value="sourceharbor") == (
        "sourceharbor"
    )
    assert service._match_basis(
        source_type="", source_url="https://example.com", rsshub_route=None
    ) == ("source_url")
    assert service._match_basis(source_type="", source_url=None, rsshub_route=None) == (
        "source_value"
    )


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
    assert result["results"][0]["relation_kind"] == "matched_subscription"
    assert result["results"][0]["matched_subscription_id"]
    assert result["results"][0]["matched_subscription_name"] == "@existing-channel"


def test_manual_source_submit_matches_manual_video_back_to_existing_subscription() -> None:
    service = _build_service()
    match_video_url = "https://www.youtube.com/watch?v=matchme"
    video_db_id = str(uuid.uuid5(uuid.NAMESPACE_URL, match_video_url))
    service.videos_service.matches[video_db_id] = {
        "subscription_id": "sub-existing-1",
        "platform": "youtube",
        "source_type": "youtube_user",
        "source_value": "@existing-channel",
        "source_url": "https://www.youtube.com/@existing-channel",
        "rsshub_route": "/youtube/user/@existing-channel",
        "display_name": "@existing-channel",
        "creator_handle": "@existing-channel",
    }
    job_id = match_video_url.replace("https://", "").replace("/", "-")
    service.videos_service.reader_bridges[job_id] = {
        "id": "reader-doc-1",
        "title": "Reader edition one",
        "publish_status": "published",
        "reader_route": "/reader/reader-doc-1",
        "published_with_gap": False,
    }

    result = asyncio.run(
        service.submit(
            raw_input=match_video_url,
            category="creator",
            tags=[],
            priority=10,
            enabled=True,
        )
    )

    item = result["results"][0]
    assert item["relation_kind"] == "matched_subscription"
    assert item["matched_subscription_id"] == "sub-existing-1"
    assert item["matched_subscription_name"] == "@existing-channel"
    assert item["match_confidence"] == "inferred_from_existing_ingest_event"
    assert item["published_document_id"] == "reader-doc-1"
    assert item["published_document_title"] == "Reader edition one"
    assert item["published_document_publish_status"] == "published"
    assert item["reader_route"] == "/reader/reader-doc-1"


def test_manual_source_submit_can_match_manual_video_back_by_source_identity() -> None:
    service = _build_service()
    source_url = "https://www.youtube.com/watch?v=freshmatch"
    service.videos_service.source_matches[source_url] = {
        "subscription_id": "sub-youtube-1",
        "platform": "youtube",
        "source_type": "youtube_channel_id",
        "source_value": "UCfresh123",
        "source_url": "https://www.youtube.com/channel/UCfresh123",
        "rsshub_route": "/youtube/channel/UCfresh123",
        "display_name": "Fresh Channel",
        "creator_handle": "",
    }

    result = asyncio.run(
        service.submit(
            raw_input=source_url,
            category="creator",
            tags=[],
            priority=10,
            enabled=True,
        )
    )

    item = result["results"][0]
    assert item["relation_kind"] == "matched_subscription"
    assert item["matched_subscription_id"] == "sub-youtube-1"
    assert item["matched_subscription_name"] == "Fresh Channel"
    assert item["match_confidence"] == "inferred_from_source_identity"


def test_persist_manual_source_item_writes_formal_object_world() -> None:
    service = _build_service()
    db = _DbStub()
    service.videos_service.db = db  # type: ignore[attr-defined]

    run = service._persist_manual_source_item(
        manual_run=None,
        payload={
            "job_id": str(uuid.uuid4()),
            "video_db_id": str(uuid.uuid4()),
            "video_uid": "manual-uid",
            "mode": "text_only",
        },
        platform="generic",
        source_url="https://example.com/article",
        title="Article",
        content_profile="article",
        matched_subscription_id=None,
    )

    assert run is not None
    assert db.flushed >= 1
    assert any(getattr(obj, "content_type", None) == "article" for obj in db.added)


def test_manual_source_submit_accepts_uuid_video_db_id_matches() -> None:
    service = _build_service()
    match_video_url = "https://www.youtube.com/watch?v=uuidmatch"
    video_db_id = uuid.uuid5(uuid.NAMESPACE_URL, match_video_url)
    service.videos_service.matches[str(video_db_id)] = {
        "subscription_id": "sub-existing-uuid",
        "platform": "youtube",
        "source_type": "youtube_user",
        "source_value": "@uuid-channel",
        "source_url": "https://www.youtube.com/@uuid-channel",
        "rsshub_route": "/youtube/user/@uuid-channel",
        "display_name": "@uuid-channel",
        "creator_handle": "@uuid-channel",
    }

    async def process_video_with_uuid(**kwargs):
        return {
            "job_id": "uuid-job",
            "video_db_id": video_db_id,
            "reused": False,
        }

    service.videos_service.process_video = process_video_with_uuid

    result = asyncio.run(
        service.submit(
            raw_input=match_video_url,
            category="creator",
            tags=[],
            priority=10,
            enabled=True,
        )
    )

    item = result["results"][0]
    assert item["relation_kind"] == "matched_subscription"
    assert item["matched_subscription_id"] == "sub-existing-uuid"
    assert item["matched_subscription_name"] == "@uuid-channel"
    assert result["queued_manual_items"] == 1


def test_manual_source_submit_rejects_value_and_runtime_errors() -> None:
    service = _build_service()

    async def process_video_with_errors(**kwargs):
        url = kwargs["url"]
        if url.endswith("value-error"):
            raise ValueError("value boom")
        raise RuntimeError("runtime boom")

    service.videos_service.process_video = process_video_with_errors

    result = asyncio.run(
        service.submit(
            raw_input="https://youtu.be/value-error\nhttps://youtu.be/runtime-error",
            category="creator",
            tags=[],
            priority=10,
            enabled=True,
        )
    )

    assert result["rejected_count"] == 2
    assert [item["message"] for item in result["results"]] == ["value boom", "runtime boom"]
