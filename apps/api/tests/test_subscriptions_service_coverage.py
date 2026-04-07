from __future__ import annotations

import uuid
from typing import Any

import pytest

from apps.api.app.services.subscription_templates import load_subscription_template_catalog
from apps.api.app.services.subscriptions import (
    SubscriptionsService,
    _derive_rsshub_route,
    _resolve_adapter,
    _validate_subscription_source_url,
    resolve_subscription_content_profile,
    resolve_subscription_support_tier,
)


class _RepoStub:
    def __init__(self) -> None:
        self.last_upsert: dict[str, Any] | None = None
        self.last_batch_update: dict[str, Any] | None = None
        self.last_deleted_id: uuid.UUID | None = None

    def list(self, **kwargs: Any) -> list[str]:
        return [f"listed:{kwargs['platform']}:{kwargs['category']}:{kwargs['enabled_only']}"]

    def upsert(self, **kwargs: Any) -> tuple[dict[str, Any], bool]:
        self.last_upsert = dict(kwargs)
        return kwargs, True

    def batch_update_category(self, *, ids: list[uuid.UUID], category: str) -> int:
        self.last_batch_update = {"ids": list(ids), "category": category}
        return len(ids) if category else 0

    def delete(self, _subscription_id: uuid.UUID) -> bool:
        self.last_deleted_id = _subscription_id
        return True


@pytest.mark.parametrize(
    ("url", "field", "message"),
    [
        ("", "source_url", "must not be empty"),
        ("ftp://example.com/feed", "source_url", "must use http or https"),
        ("https:///feed", "source_url", "host is required"),
        ("https://localhost/feed", "source_url", "blocked internal host"),
        ("https://127.0.0.1/feed", "source_url", "blocked internal address"),
        ("https://service.internal/feed", "source_url", "blocked internal host"),
        ("https://0.0.0.0/feed", "source_url", "blocked internal address"),
        ("https://240.0.0.1/feed", "source_url", "blocked internal address"),
    ],
)
def test_validate_subscription_source_url_rejects_invalid_inputs(
    url: str, field: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _validate_subscription_source_url(url, field_name=field)


def test_validate_subscription_source_url_rejects_ftp_scheme() -> None:
    with pytest.raises(ValueError, match=r"^source_url must use http or https$"):
        _validate_subscription_source_url("ftp://example.com/feed", field_name="source_url")


def test_validate_subscription_source_url_accepts_public_domain() -> None:
    assert (
        _validate_subscription_source_url(" https://example.com/feed.xml ", field_name="source_url")
        == "https://example.com/feed.xml"
    )


def test_validate_subscription_source_url_accepts_http_scheme() -> None:
    assert (
        _validate_subscription_source_url("http://example.com/feed.xml", field_name="source_url")
        == "http://example.com/feed.xml"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://224.0.0.1/feed.xml",
        "http://169.254.10.20/feed.xml",
        "http://10.0.0.8/feed.xml",
    ],
)
def test_validate_subscription_source_url_rejects_ip_class_specific_addresses(url: str) -> None:
    with pytest.raises(ValueError, match=r"^source_url points to a blocked internal address$"):
        _validate_subscription_source_url(url, field_name="source_url")


def test_derive_rsshub_route_supports_known_platforms_and_fallback() -> None:
    assert (
        _derive_rsshub_route("youtube", "youtube_channel_id", "UC123") == "/youtube/channel/UC123"
    )
    assert _derive_rsshub_route("bilibili", "bilibili_uid", "777") == "/bilibili/user/video/777"
    assert _derive_rsshub_route("x", "url", "https://x.com/feed") == "https://x.com/feed"
    assert _derive_rsshub_route("x", "other", "value") == "value"


def test_resolve_adapter_covers_generic_route_and_errors() -> None:
    assert _resolve_adapter(
        platform="youtube",
        adapter_type="rss_generic",
        source_type="url",
        source_value="https://example.com/feed.xml",
        source_url=None,
        rsshub_route=None,
    ) == (
        "rss_generic",
        "https://example.com/feed.xml",
        "https://example.com/feed.xml",
    )

    assert _resolve_adapter(
        platform="youtube",
        adapter_type="rsshub_route",
        source_type="youtube_channel_id",
        source_value="UC999",
        source_url="https://example.com/f.xml",
        rsshub_route=None,
    ) == ("rsshub_route", "https://example.com/f.xml", "/youtube/channel/UC999")

    with pytest.raises(ValueError, match=r"^source_url must use http or https$"):
        _resolve_adapter(
            platform="youtube",
            adapter_type="rsshub_route",
            source_type="youtube_channel_id",
            source_value="UC999",
            source_url="ftp://example.com/f.xml",
            rsshub_route=None,
        )

    with pytest.raises(ValueError, match=r"^source_url is required for adapter_type=rss_generic$"):
        _resolve_adapter(
            platform="youtube",
            adapter_type="rss_generic",
            source_type="url",
            source_value="",
            source_url=None,
            rsshub_route=None,
        )

    with pytest.raises(ValueError, match=r"^source_url must use http or https$"):
        _resolve_adapter(
            platform="youtube",
            adapter_type="rss_generic",
            source_type="url",
            source_value="ftp://example.com/feed.xml",
            source_url=None,
            rsshub_route=None,
        )

    with pytest.raises(
        ValueError, match=r"^adapter_type must be one of: rsshub_route, rss_generic$"
    ):
        _resolve_adapter(
            platform="youtube",
            adapter_type="bad_adapter",
            source_type="url",
            source_value="https://example.com/feed.xml",
            source_url=None,
            rsshub_route=None,
        )


def test_resolve_adapter_defaults_to_rsshub_route_when_adapter_type_is_none() -> None:
    assert _resolve_adapter(
        platform="youtube",
        adapter_type=None,
        source_type="youtube_channel_id",
        source_value="UC-DEFAULT",
        source_url="https://example.com/default.xml",
        rsshub_route="/custom/youtube/UC-DEFAULT",
    ) == (
        "rsshub_route",
        "https://example.com/default.xml",
        "/custom/youtube/UC-DEFAULT",
    )


def test_subscription_support_profile_distinguishes_strong_video_from_generic_routes() -> None:
    assert (
        resolve_subscription_support_tier(platform="youtube", source_type="youtube_channel_id")
        == "strong_supported"
    )
    assert (
        resolve_subscription_content_profile(
            platform="youtube",
            source_type="youtube_channel_id",
            adapter_type="rsshub_route",
        )
        == "video"
    )
    assert (
        resolve_subscription_support_tier(platform="rsshub", source_type="rsshub_route")
        == "generic_supported"
    )
    assert (
        resolve_subscription_content_profile(
            platform="rsshub",
            source_type="rsshub_route",
            adapter_type="rsshub_route",
        )
        == "article"
    )


def test_subscription_template_catalog_exposes_strong_and_generic_templates() -> None:
    payload = load_subscription_template_catalog()

    assert {item["id"] for item in payload["support_tiers"]} == {
        "strong_supported",
        "generic_supported",
    }
    template_ids = {item["id"] for item in payload["templates"]}
    assert "youtube_channel" in template_ids
    assert "generic_rsshub_route" in template_ids
    generic_feed_template = next(
        item for item in payload["templates"] if item["id"] == "generic_rss_feed"
    )
    assert generic_feed_template["source_value_placeholder"] == "https://example.com/feed.xml"
    assert generic_feed_template["source_url_placeholder"] == "https://example.com/feed.xml"
    assert generic_feed_template["source_url_required"] is False


def test_subscription_template_catalog_returns_fresh_containers_per_call() -> None:
    first_payload = load_subscription_template_catalog()
    first_payload["support_tiers"].clear()
    first_payload["templates"].clear()

    second_payload = load_subscription_template_catalog()

    assert {item["id"] for item in second_payload["support_tiers"]} == {
        "strong_supported",
        "generic_supported",
    }
    assert {item["id"] for item in second_payload["templates"]} >= {
        "youtube_channel",
        "generic_rsshub_route",
        "generic_rss_feed",
    }


def test_subscriptions_service_requires_db_when_repo_missing() -> None:
    with pytest.raises(ValueError, match=r"^db is required when repo is not provided$"):
        SubscriptionsService(db=None, repo=None)


def test_subscriptions_service_builds_repository_from_db(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _RepoFactory:
        def __init__(self, db: object) -> None:
            captured["db"] = db

    monkeypatch.setitem(
        SubscriptionsService.__init__.__globals__, "SubscriptionsRepository", _RepoFactory
    )

    db_obj = object()
    service = SubscriptionsService(db=db_obj, repo=None)

    assert isinstance(service.repo, _RepoFactory)
    assert captured["db"] is db_obj


def test_subscriptions_service_normalizes_fields_and_delegates_to_repo() -> None:
    repo = _RepoStub()
    service = SubscriptionsService(db=None, repo=repo)

    listed_default = service.list_subscriptions()
    assert listed_default == ["listed:None:None:False"]

    listed = service.list_subscriptions(platform="youtube", category="Tech", enabled_only=True)
    assert listed == ["listed:youtube:Tech:True"]

    payload, created = service.upsert_subscription(
        platform="youtube",
        source_type="url",
        source_value="https://example.com/feed.xml",
        adapter_type="rss_generic",
        source_url=None,
        rsshub_route=None,
        category="  News ",
        tags=[" A ", "", "B"],
        priority=None,
        enabled=True,
    )

    assert created is True
    assert payload["category"] == "news"
    assert payload["tags"] == ["A", "B"]
    assert payload["priority"] == 50
    assert repo.last_upsert == {
        "platform": "youtube",
        "source_type": "url",
        "source_value": "https://example.com/feed.xml",
        "adapter_type": "rss_generic",
        "source_url": "https://example.com/feed.xml",
        "rsshub_route": "https://example.com/feed.xml",
        "category": "news",
        "tags": ["A", "B"],
        "priority": 50,
        "enabled": True,
    }

    payload2, created2 = service.upsert_subscription(
        platform="youtube",
        source_type="youtube_channel_id",
        source_value="UC-DERIVE-001",
        adapter_type=None,
        source_url="https://example.com/route.xml",
        rsshub_route=None,
        category=None,
        tags=[],
        priority=0,
        enabled=False,
    )

    assert created2 is True
    assert payload2["adapter_type"] == "rsshub_route"
    assert payload2["source_url"] == "https://example.com/route.xml"
    assert payload2["rsshub_route"] == "/youtube/channel/UC-DERIVE-001"
    assert payload2["category"] == "misc"

    payload3, created3 = service.upsert_subscription(
        platform=" RSSHub ",
        source_type=" RSSHUB_ROUTE ",
        source_value="/36kr/newsflashes",
        adapter_type="rsshub_route",
        source_url=None,
        rsshub_route=None,
        category=" misc ",
        tags=[" generic "],
        priority=80,
        enabled=True,
    )

    assert created3 is True
    assert payload3["platform"] == "rsshub"
    assert payload3["source_type"] == "rsshub_route"
    assert payload3["rsshub_route"] == "/36kr/newsflashes"
    assert payload2["priority"] == 0

    payload3, created3 = service.upsert_subscription(
        platform="youtube",
        source_type="youtube_channel_id",
        source_value="UC-CUSTOM-001",
        adapter_type="rsshub_route",
        source_url="https://example.com/custom.xml",
        rsshub_route="/custom/channel/UC-CUSTOM-001",
        category="misc",
        tags=[],
        priority=50,
        enabled=True,
    )

    assert created3 is True
    assert payload3["rsshub_route"] == "/custom/channel/UC-CUSTOM-001"
    assert payload3["source_url"] == "https://example.com/custom.xml"

    deleted_id = uuid.uuid4()
    deleted = service.delete_subscription(deleted_id)
    assert deleted is True
    assert repo.last_deleted_id == deleted_id


def test_subscriptions_service_rejects_out_of_range_priority_and_empty_batch_category() -> None:
    repo = _RepoStub()
    service = SubscriptionsService(db=None, repo=repo)

    with pytest.raises(ValueError, match=r"^priority must be in \[0, 100\]$"):
        service.upsert_subscription(
            platform="youtube",
            source_type="youtube_channel_id",
            source_value="UC123",
            adapter_type="rsshub_route",
            source_url=None,
            rsshub_route=None,
            category="misc",
            tags=[],
            priority=101,
            enabled=True,
        )

    with pytest.raises(ValueError, match=r"^source_value must use http or https$"):
        service.upsert_subscription(
            platform="youtube",
            source_type="url",
            source_value="ftp://example.com/feed.xml",
            adapter_type="rsshub_route",
            source_url=None,
            rsshub_route=None,
            category="misc",
            tags=[],
            priority=50,
            enabled=True,
        )

    with pytest.raises(ValueError, match=r"^category is required$"):
        service.batch_update_category(ids=[uuid.uuid4()], category="   ")
    with pytest.raises(ValueError, match=r"^category is required$"):
        service.batch_update_category(ids=[uuid.uuid4()], category=None)  # type: ignore[arg-type]

    updated = service.batch_update_category(ids=[uuid.uuid4(), uuid.uuid4()], category="  SPORTS ")
    assert updated == 2
    assert repo.last_batch_update is not None
    assert repo.last_batch_update["category"] == "sports"
    assert len(repo.last_batch_update["ids"]) == 2


@pytest.mark.parametrize("priority", [0, 100])
def test_subscriptions_service_accepts_priority_boundaries(priority: int) -> None:
    service = SubscriptionsService(db=None, repo=_RepoStub())

    payload, created = service.upsert_subscription(
        platform="youtube",
        source_type="youtube_channel_id",
        source_value="UC123",
        adapter_type="rsshub_route",
        source_url=None,
        rsshub_route=None,
        category="misc",
        tags=[],
        priority=priority,
        enabled=True,
    )

    assert created is True
    assert payload["priority"] == priority
