from __future__ import annotations

import asyncio
import hashlib
import sys
import types
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app.errors import ApiTimeoutError
from apps.api.app.routers.subscriptions import _to_subscription_response
from apps.api.app.services.videos import (
    VideosService,
    _build_process_idempotency_key,
    _extract_video_uid,
    _normalize_mode,
    _url_hash,
)

pytestmark = pytest.mark.allow_unauth_write


@dataclass
class _JobRow:
    id: uuid.UUID
    status: str
    idempotency_key: str
    mode: str


@dataclass
class _VideoRow:
    id: uuid.UUID


class _RepoStub:
    def __init__(self, *, should_dispatch: bool = True) -> None:
        self.should_dispatch = should_dispatch
        self.created_calls: list[dict[str, Any]] = []
        self.mark_failed_calls: list[dict[str, Any]] = []
        self.job = _JobRow(
            id=uuid.uuid4(),
            status="queued",
            idempotency_key="idem-1",
            mode="full",
        )

    def create_or_reuse(self, **kwargs: Any) -> tuple[_JobRow, bool]:
        self.created_calls.append(dict(kwargs))
        return self.job, self.should_dispatch

    def mark_dispatch_failed(
        self, *, job_id: uuid.UUID, error_message: str, reason: str = "dispatch_failed"
    ) -> _JobRow:
        self.mark_failed_calls.append(
            {
                "job_id": job_id,
                "error_message": error_message,
                "reason": reason,
            }
        )
        self.job.status = "failed"
        return self.job


class _VideoRepoStub:
    def __init__(self) -> None:
        self.video = _VideoRow(id=uuid.uuid4())

    def upsert_for_processing(self, **_: Any) -> _VideoRow:
        return self.video


class _FakeClient:
    async def start_workflow(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _install_temporal_modules(monkeypatch: pytest.MonkeyPatch, *, client: _FakeClient) -> None:
    temporalio_mod = types.ModuleType("temporalio")
    temporal_client_mod = types.ModuleType("temporalio.client")
    temporal_common_mod = types.ModuleType("temporalio.common")

    class _WorkflowIDReusePolicy:
        REJECT_DUPLICATE = "reject_duplicate"

    class _WorkflowIDConflictPolicy:
        USE_EXISTING = "use_existing"

    class _Client:
        @staticmethod
        async def connect(_target_host: str, *, namespace: str):
            assert namespace == "default"
            return client

    temporal_client_mod.Client = _Client
    temporal_common_mod.WorkflowIDReusePolicy = _WorkflowIDReusePolicy
    temporal_common_mod.WorkflowIDConflictPolicy = _WorkflowIDConflictPolicy

    monkeypatch.setitem(sys.modules, "temporalio", temporalio_mod)
    monkeypatch.setitem(sys.modules, "temporalio.client", temporal_client_mod)
    monkeypatch.setitem(sys.modules, "temporalio.common", temporal_common_mod)


async def _run_process(service: VideosService) -> dict[str, Any]:
    return await service.process_video(
        platform="youtube",
        url="https://www.youtube.com/watch?v=abc123",
        video_id=None,
        mode="full",
        overrides={"lang": "en"},
        force=False,
    )


def test_videos_helpers_cover_hash_uid_mode_and_serialization_guards() -> None:
    assert (
        _url_hash(" https://youtu.be/abc123 ")
        == hashlib.sha256(b"https://youtu.be/abc123").hexdigest()
    )

    assert (
        _extract_video_uid(platform="youtube", url="https://youtu.be/")
        == hashlib.sha256(b"https://youtu.be/").hexdigest()
    )
    assert (
        _extract_video_uid(platform="youtube", url="https://youtu.be")
        == hashlib.sha256(b"https://youtu.be").hexdigest()
    )
    assert (
        _extract_video_uid(platform="bilibili", url="https://www.bilibili.com/video/not-bv")
        == hashlib.sha256(b"https://www.bilibili.com/video/not-bv").hexdigest()
    )
    assert _extract_video_uid(
        platform="youtube", url="https://www.bilibili.com/video/BV1xx411c7mD"
    ) == _url_hash("https://www.bilibili.com/video/BV1xx411c7mD")
    assert (
        _extract_video_uid(platform="other", url="https://www.youtube.com/watch?v=abc123")
        == hashlib.sha256(b"https://www.youtube.com/watch?v=abc123").hexdigest()
    )
    assert (
        _extract_video_uid(platform="other", url="https://example.com/v")
        == hashlib.sha256(b"https://example.com/v").hexdigest()
    )

    assert _normalize_mode(" FULL ") == "full"
    assert _normalize_mode(" refresh-comments ") == "refresh_comments"
    with pytest.raises(ValueError, match="unsupported mode"):
        _normalize_mode("invalid")

    with pytest.raises(ValueError, match=r"^overrides must be JSON-serializable$"):
        _build_process_idempotency_key(
            platform="youtube",
            video_uid="abc",
            mode="full",
            overrides={"bad": {1, 2}},
        )


def test_process_video_maps_temporal_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    _install_temporal_modules(monkeypatch, client=_FakeClient())

    async def _timeout_wait_for(awaitable: Any, *, timeout: float):
        del timeout
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError

    monkeypatch.setattr("apps.api.app.services.videos.asyncio.wait_for", _timeout_wait_for)

    with pytest.raises(ApiTimeoutError, match="temporal connect timed out") as exc_info:
        asyncio.run(_run_process(service))

    assert exc_info.value.error_code == "TEMPORAL_CONNECT_TIMEOUT"


def test_process_video_maps_temporal_start_timeout_and_marks_dispatch_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _RepoStub(should_dispatch=True)
    service = VideosService(db=object())
    service.video_repo = _VideoRepoStub()  # type: ignore[assignment]
    service.jobs_repo = repo  # type: ignore[assignment]

    _install_temporal_modules(monkeypatch, client=_FakeClient())

    state = {"call": 0}

    async def _wait_for(awaitable: Any, *, timeout: float):
        del timeout
        state["call"] += 1
        if state["call"] == 1:
            return await awaitable
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise TimeoutError

    monkeypatch.setattr("apps.api.app.services.videos.asyncio.wait_for", _wait_for)

    with pytest.raises(ApiTimeoutError, match="temporal workflow start timed out") as exc_info:
        asyncio.run(_run_process(service))

    assert exc_info.value.error_code == "TEMPORAL_WORKFLOW_START_TIMEOUT"
    assert len(repo.mark_failed_calls) == 1
    assert repo.mark_failed_calls[0]["reason"] == "dispatch_timeout"


def test_videos_router_list_endpoint_serializes_service_rows(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    video_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.videos.VideosService.list_videos",
        lambda self, *, platform, status, limit: [
            {
                "id": video_id,
                "platform": platform or "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo video",
                "published_at": now,
                "first_seen_at": now,
                "last_seen_at": now,
                "latest_job_status": status or "queued",
                "latest_job_id": job_id,
            }
        ],
    )

    response = api_client.get("/api/v1/videos?platform=youtube&status=queued&limit=3")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(video_id),
            "platform": "youtube",
            "video_uid": "abc123",
            "source_url": "https://www.youtube.com/watch?v=abc123",
            "title": "Demo video",
            "published_at": now.isoformat().replace("+00:00", "Z"),
            "first_seen_at": now.isoformat().replace("+00:00", "Z"),
            "last_seen_at": now.isoformat().replace("+00:00", "Z"),
            "status": "queued",
            "last_job_id": str(job_id),
        }
    ]


def test_subscriptions_router_maps_service_value_errors_to_400(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.upsert_subscription",
        lambda self, **kwargs: (_ for _ in ()).throw(ValueError("invalid source")),
    )

    response = api_client.post(
        "/api/v1/subscriptions",
        json={
            "platform": "youtube",
            "source_type": "url",
            "source_value": "https://youtube.com/@demo",
            "adapter_type": "rsshub_route",
            "rsshub_route": "/youtube/channel/demo",
            "category": "misc",
            "tags": [],
            "priority": 50,
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid source"

    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.batch_update_category",
        lambda self, **kwargs: (_ for _ in ()).throw(ValueError("bad category")),
    )
    response2 = api_client.post(
        "/api/v1/subscriptions/batch-update-category",
        json={"ids": [str(uuid.uuid4())], "category": "bad"},
    )
    assert response2.status_code == 400
    assert response2.json()["detail"] == "bad category"


def test_subscriptions_router_delete_returns_404_when_missing(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.delete_subscription",
        lambda self, _id: False,
    )

    response = api_client.delete(f"/api/v1/subscriptions/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "subscription not found"


def test_to_subscription_response_applies_defaults_for_missing_optional_fields() -> None:
    source_value = "UNMAPPED-SOURCE-VALUE-98765"
    row = types.SimpleNamespace(
        id=uuid.uuid4(),
        platform="youtube",
        source_type="youtube_channel_id",
        source_value=source_value,
        rsshub_route="/youtube/channel/UC999",
        enabled=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    payload = _to_subscription_response(row)

    assert payload.source_type == "youtube_channel_id"
    assert payload.source_value == source_value
    assert payload.source_name == source_value
    assert payload.support_tier == "strong_supported"
    assert payload.content_profile == "video"
    assert payload.adapter_type == "rsshub_route"
    assert payload.source_url is None
    assert payload.category == "misc"
    assert payload.tags == []
    assert payload.priority == 50


def test_to_subscription_response_handles_missing_or_none_source_fields_and_keeps_zero_priority() -> (
    None
):
    created_at = datetime(2026, 1, 3, tzinfo=UTC)
    updated_at = datetime(2026, 1, 4, tzinfo=UTC)

    missing_row = types.SimpleNamespace(
        id=uuid.uuid4(),
        platform="youtube",
        rsshub_route="/youtube/channel/fallback",
        enabled=True,
        created_at=created_at,
        updated_at=updated_at,
    )
    missing_payload = _to_subscription_response(missing_row)
    assert missing_payload.source_type == ""
    assert missing_payload.source_value == ""
    assert missing_payload.source_name == "Unknown"
    assert missing_payload.support_tier == "generic_supported"
    assert missing_payload.content_profile == "article"

    none_row = types.SimpleNamespace(
        id=uuid.uuid4(),
        platform="youtube",
        source_type=None,
        source_value=None,
        rsshub_route="/youtube/channel/fallback-none",
        tags=("tag-a", "tag-b"),
        priority=0,
        enabled=False,
        created_at=created_at,
        updated_at=updated_at,
    )
    none_payload = _to_subscription_response(none_row)
    assert none_payload.source_type == ""
    assert none_payload.source_value == ""
    assert none_payload.source_name == "Unknown"
    assert none_payload.support_tier == "generic_supported"
    assert none_payload.content_profile == "article"
    assert none_payload.tags == ["tag-a", "tag-b"]
    assert none_payload.priority == 0


def test_subscriptions_router_list_and_upsert_success_paths(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created_at = datetime(2026, 2, 1, tzinfo=UTC)
    updated_at = datetime(2026, 2, 2, tzinfo=UTC)
    list_row = types.SimpleNamespace(
        id=uuid.uuid4(),
        platform="youtube",
        source_type="youtube_channel_id",
        source_value="UC-LIST-001",
        rsshub_route="/youtube/channel/UC-LIST-001",
        enabled=True,
        created_at=created_at,
        updated_at=updated_at,
    )
    upsert_row = types.SimpleNamespace(
        id=uuid.uuid4(),
        platform="youtube",
        source_type="url",
        source_value="https://example.com/feed.xml",
        rsshub_route="https://example.com/feed.xml",
        adapter_type="rss_generic",
        source_url="https://example.com/feed.xml",
        category="news",
        tags=["a", "b"],
        priority=100,
        enabled=False,
        created_at=created_at,
        updated_at=updated_at,
    )
    captured_list_kwargs: dict[str, Any] = {}

    def _list_subscriptions(self, **kwargs: Any) -> list[Any]:
        captured_list_kwargs.update(kwargs)
        return [list_row]

    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.list_subscriptions",
        _list_subscriptions,
    )
    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.upsert_subscription",
        lambda self, **kwargs: (upsert_row, False),
    )
    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.batch_update_category",
        lambda self, **kwargs: 3,
    )

    list_response = api_client.get(
        "/api/v1/subscriptions",
        params={"platform": "youtube", "category": "news", "enabled_only": "true"},
    )
    assert list_response.status_code == 200
    assert captured_list_kwargs == {"platform": "youtube", "category": "news", "enabled_only": True}
    assert list_response.json()[0]["source_type"] == "youtube_channel_id"
    assert list_response.json()[0]["adapter_type"] == "rsshub_route"
    assert list_response.json()[0]["support_tier"] == "strong_supported"
    assert list_response.json()[0]["priority"] == 50

    upsert_response = api_client.post(
        "/api/v1/subscriptions",
        json={
            "platform": "youtube",
            "source_type": "url",
            "source_value": "https://example.com/feed.xml",
            "adapter_type": "rss_generic",
            "source_url": "https://example.com/feed.xml",
            "rsshub_route": "https://example.com/feed.xml",
            "category": "news",
            "tags": ["a", "b"],
            "priority": 100,
            "enabled": False,
        },
    )
    assert upsert_response.status_code == 200
    assert upsert_response.json()["created"] is False
    assert upsert_response.json()["subscription"]["adapter_type"] == "rss_generic"
    assert upsert_response.json()["subscription"]["content_profile"] == "article"
    assert upsert_response.json()["subscription"]["priority"] == 100
    assert upsert_response.json()["subscription"]["enabled"] is False

    templates_response = api_client.get("/api/v1/subscriptions/templates")
    assert templates_response.status_code == 200
    payload = templates_response.json()
    assert {item["id"] for item in payload["support_tiers"]} == {
        "strong_supported",
        "generic_supported",
    }
    assert any(item["id"] == "generic_rsshub_route" for item in payload["templates"])
    assert any(
        item["id"] == "generic_rss_feed"
        and item["source_value_placeholder"] == "https://example.com/feed.xml"
        and item["source_url_placeholder"] == "https://example.com/feed.xml"
        and item["source_url_required"] is False
        for item in payload["templates"]
    )

    batch_response = api_client.post(
        "/api/v1/subscriptions/batch-update-category",
        json={"ids": [str(uuid.uuid4())], "category": "fresh"},
    )
    assert batch_response.status_code == 200
    assert batch_response.json() == {"updated": 3}


def test_subscriptions_manual_intake_success_and_error_paths(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _submit_success(self, **kwargs: Any):
        assert kwargs["raw_input"] == "https://www.youtube.com/@demo"
        return {
            "processed_count": 1,
            "created_subscriptions": 1,
            "updated_subscriptions": 0,
            "queued_manual_items": 0,
            "reused_manual_items": 0,
            "rejected_count": 0,
            "results": [
                {
                    "line_number": 1,
                    "raw_input": "https://www.youtube.com/@demo",
                    "target_kind": "subscription_source",
                    "recommended_action": "save_subscription",
                    "applied_action": "save_subscription",
                    "status": "created",
                    "platform": "youtube",
                    "source_type": "youtube_user",
                    "source_value": "@demo",
                    "source_url": "https://www.youtube.com/@demo",
                    "rsshub_route": "/youtube/user/@demo",
                    "adapter_type": "rsshub_route",
                    "content_profile": "video",
                    "support_tier": "strong_supported",
                    "display_name": "@demo",
                    "published_document_id": "reader-doc-1",
                    "published_document_title": "Reader edition one",
                    "published_document_publish_status": "published",
                    "reader_route": "/reader/reader-doc-1",
                    "message": "Saved as a new subscription source.",
                    "subscription_id": str(uuid.uuid4()),
                    "job_id": None,
                }
            ],
        }

    monkeypatch.setattr(
        "apps.api.app.routers.subscriptions.ManualSourceIntakeService.submit",
        _submit_success,
    )
    response = api_client.post(
        "/api/v1/subscriptions/manual-intake",
        json={"raw_input": "https://www.youtube.com/@demo"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created_subscriptions"] == 1
    assert payload["results"][0]["source_type"] == "youtube_user"
    assert payload["results"][0]["reader_route"] == "/reader/reader-doc-1"
    assert payload["results"][0]["published_document_title"] == "Reader edition one"

    async def _submit_error(self, **kwargs: Any):
        raise ValueError("bad manual intake")

    monkeypatch.setattr(
        "apps.api.app.routers.subscriptions.ManualSourceIntakeService.submit",
        _submit_error,
    )
    response2 = api_client.post(
        "/api/v1/subscriptions/manual-intake",
        json={"raw_input": "bad"},
    )
    assert response2.status_code == 400
    assert response2.json()["detail"] == "bad manual intake"
