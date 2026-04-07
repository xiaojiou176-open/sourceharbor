from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_watchlists_routes(monkeypatch) -> None:
    from apps.api.app.db import get_db
    from apps.api.app.routers import watchlists as watchlists_router

    class StubWatchlistsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def list_watchlists(self):
            return [
                {
                    "id": "wl-1",
                    "name": "Retry policy",
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                }
            ]

        def get_watchlist_trend(self, *, watchlist_id, limit_runs=3, limit_cards=18):  # noqa: ANN001, ARG002
            return {
                "watchlist": self.list_watchlists()[0] | {"id": watchlist_id},
                "summary": {
                    "recent_runs": 2,
                    "matched_cards": 4,
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                },
                "timeline": [],
                "merged_stories": [
                    {
                        "id": "story-1",
                        "story_key": "topic:retry-policy",
                        "headline": "Retry Policy",
                        "topic_key": "retry-policy",
                        "topic_label": "Retry Policy",
                        "latest_created_at": "2026-04-01T11:00:00Z",
                        "matched_card_count": 2,
                        "platforms": ["youtube", "rss"],
                        "claim_kinds": ["recommendation"],
                        "source_urls": ["https://example.com/2"],
                        "run_ids": ["job-2"],
                        "cards": [],
                    }
                ],
            }

        def upsert_watchlist(self, **kwargs):  # noqa: ANN003
            return {
                "id": str(kwargs["watchlist_id"] or "wl-created"),
                "name": kwargs["name"],
                "matcher_type": kwargs["matcher_type"],
                "matcher_value": kwargs["matcher_value"],
                "delivery_channel": kwargs["delivery_channel"],
                "enabled": kwargs["enabled"],
                "created_at": "2026-03-31T10:00:00Z",
                "updated_at": "2026-04-01T12:00:00Z",
            }

        def delete_watchlist(self, *, watchlist_id: str) -> bool:
            return watchlist_id == "wl-1"

        def get_watchlist_briefing_page(
            self,
            *,
            watchlist_id,
            story_id=None,
            limit_runs=4,
            limit_cards=18,
            limit_stories=4,
            limit_evidence_per_story=3,
            query=None,
        ):  # noqa: ANN001, ARG002
            briefing = {
                "watchlist": self.list_watchlists()[0] | {"id": watchlist_id},
                "summary": {
                    "overview": "Retry policy currently converges across recent sources.",
                    "source_count": 3,
                    "run_count": 2,
                    "story_count": 1,
                    "matched_cards": 4,
                    "primary_story_headline": "Retry Policy",
                    "signals": [
                        {
                            "story_key": "topic:retry-policy",
                            "headline": "Retry Policy",
                            "matched_card_count": 2,
                            "latest_run_job_id": "job-2",
                            "reason": "Appears in the latest matched run.",
                        }
                    ],
                },
                "differences": {
                    "latest_job_id": "job-2",
                    "previous_job_id": "job-1",
                    "added_topics": ["retry-policy"],
                    "removed_topics": [],
                    "added_claim_kinds": ["recommendation"],
                    "removed_claim_kinds": [],
                    "new_story_keys": ["topic:retry-policy"],
                    "removed_story_keys": [],
                    "compare": {
                        "job_id": "job-2",
                        "has_previous": True,
                        "previous_job_id": "job-1",
                        "changed": True,
                        "added_lines": 3,
                        "removed_lines": 1,
                        "diff_excerpt": "--- old\n+++ new",
                        "compare_route": "/jobs?job_id=job-2",
                    },
                },
                "evidence": {
                    "suggested_story_id": "story-1",
                    "stories": [
                        {
                            "story_id": "story-1",
                            "story_key": "topic:retry-policy",
                            "headline": "Retry Policy",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry Policy",
                            "source_count": 3,
                            "run_count": 2,
                            "matched_card_count": 2,
                            "platforms": ["youtube", "rss"],
                            "claim_kinds": ["recommendation"],
                            "source_urls": ["https://example.com/2"],
                            "latest_run_job_id": "job-2",
                            "evidence_cards": [],
                            "routes": {
                                "watchlist_trend": f"/trends?watchlist_id={watchlist_id}",
                                "job_compare": "/jobs?job_id=job-2",
                                "job_bundle": "/api/v1/jobs/job-2/bundle",
                                "job_knowledge_cards": "/knowledge?job_id=job-2",
                            },
                        }
                    ],
                    "featured_runs": [
                        {
                            "job_id": "job-2",
                            "video_id": "video-2",
                            "platform": "rss",
                            "title": "RSS Digest",
                            "source_url": "https://example.com/2",
                            "created_at": "2026-04-01T11:00:00Z",
                            "matched_card_count": 2,
                            "routes": {
                                "watchlist_trend": f"/trends?watchlist_id={watchlist_id}",
                                "job_compare": "/jobs?job_id=job-2",
                                "job_bundle": "/api/v1/jobs/job-2/bundle",
                                "job_knowledge_cards": "/knowledge?job_id=job-2",
                            },
                        }
                    ],
                },
                "context": {
                    "watchlist_id": watchlist_id,
                    "watchlist_name": "Retry policy",
                    "story_id": story_id,
                    "selected_story_id": "story-1",
                    "story_headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "selection_basis": "suggested_story_id",
                    "question_seed": "Retry Policy",
                },
                "selected_story": {
                    "story_id": "story-1",
                    "story_key": "topic:retry-policy",
                    "headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "source_count": 3,
                    "run_count": 2,
                    "matched_card_count": 2,
                    "platforms": ["youtube", "rss"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/2"],
                    "latest_run_job_id": "job-2",
                    "evidence_cards": [],
                    "routes": {
                        "watchlist_trend": f"/trends?watchlist_id={watchlist_id}",
                        "briefing": f"/briefings?watchlist_id={watchlist_id}&story_id=story-1",
                        "ask": (
                            f"/ask?watchlist_id={watchlist_id}"
                            "&question=Retry+Policy&story_id=story-1&topic_key=retry-policy"
                        ),
                        "job_compare": "/jobs?job_id=job-2",
                        "job_bundle": "/api/v1/jobs/job-2/bundle",
                        "job_knowledge_cards": "/knowledge?job_id=job-2",
                    },
                },
                "routes": {
                    "watchlist_trend": f"/trends?watchlist_id={watchlist_id}",
                    "briefing": f"/briefings?watchlist_id={watchlist_id}&story_id=story-1",
                    "ask": (
                        f"/ask?watchlist_id={watchlist_id}"
                        "&question=Retry+Policy&story_id=story-1&topic_key=retry-policy"
                    ),
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
            }
            return {
                "context": {
                    "watchlist_id": watchlist_id,
                    "watchlist_name": "Retry policy",
                    "story_id": story_id,
                    "selected_story_id": "story-1",
                    "story_headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "selection_basis": "suggested_story_id",
                    "question_seed": "Retry Policy",
                },
                "briefing": {
                    **briefing,
                    "selection": {
                        "selected_story_id": "story-1",
                        "selection_basis": "suggested_story_id",
                        "story": None,
                    },
                },
                "selected_story": briefing["evidence"]["stories"][0],
                "story_change_summary": '"Retry Policy" is newly surfaced in the latest briefing.',
                "citations": [],
                "routes": {
                    "watchlist_trend": f"/trends?watchlist_id={watchlist_id}",
                    "briefing": f"/briefings?watchlist_id={watchlist_id}&story_id=story-1",
                    "ask": (
                        f"/ask?watchlist_id={watchlist_id}"
                        "&question=Retry+Policy&story_id=story-1&topic_key=retry-policy"
                    ),
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
                "ask_route": (
                    f"/ask?watchlist_id={watchlist_id}"
                    "&question=Retry+Policy&story_id=story-1&topic_key=retry-policy"
                ),
                "compare_route": "/jobs?job_id=job-2",
                "fallback_reason": None,
                "fallback_next_step": None,
                "fallback_actions": [],
            }

        def get_watchlist_briefing(
            self,
            *,
            watchlist_id,
            limit_runs=4,
            limit_cards=18,
            limit_stories=4,
            limit_evidence_per_story=3,
        ):  # noqa: ANN001, ARG002
            payload = self.get_watchlist_briefing_page(
                watchlist_id=watchlist_id,
                story_id=None,
                limit_runs=limit_runs,
                limit_cards=limit_cards,
                limit_stories=limit_stories,
                limit_evidence_per_story=limit_evidence_per_story,
                query=None,
            )
            return {
                "watchlist": payload["briefing"]["watchlist"],
                "summary": payload["briefing"]["summary"],
                "differences": payload["briefing"]["differences"],
                "evidence": payload["briefing"]["evidence"],
            }

    def _fake_db():
        return object()

    def _allow_write():
        return None

    app = FastAPI()
    app.include_router(watchlists_router.router)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[watchlists_router.require_write_access] = _allow_write
    monkeypatch.setattr(watchlists_router, "WatchlistsService", StubWatchlistsService)

    client = TestClient(app)
    list_response = client.get("/api/v1/watchlists")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "wl-1"

    upsert_response = client.post(
        "/api/v1/watchlists",
        json={
            "id": "wl-1",
            "name": "Retry policy",
            "matcher_type": "topic_key",
            "matcher_value": "retry-policy",
            "delivery_channel": "dashboard",
            "enabled": True,
        },
    )
    assert upsert_response.status_code == 200
    assert upsert_response.json()["id"] == "wl-1"

    delete_response = client.delete("/api/v1/watchlists/wl-1")
    assert delete_response.status_code == 204

    trend_response = client.get("/api/v1/watchlists/wl-1/trend")
    assert trend_response.status_code == 200
    assert trend_response.json()["merged_stories"][0]["story_key"] == "topic:retry-policy"

    briefing_response = client.get("/api/v1/watchlists/wl-1/briefing")
    assert briefing_response.status_code == 200
    payload = briefing_response.json()
    assert payload["summary"]["primary_story_headline"] == "Retry Policy"
    assert payload["differences"]["compare"]["job_id"] == "job-2"
    assert payload["differences"]["compare"]["compare_route"] == "/jobs?job_id=job-2"
    assert payload["evidence"]["stories"][0]["routes"]["job_bundle"] == "/api/v1/jobs/job-2/bundle"
    assert (
        payload["evidence"]["stories"][0]["routes"]["job_knowledge_cards"]
        == "/knowledge?job_id=job-2"
    )

    briefing_page_response = client.get("/api/v1/watchlists/wl-1/briefing/page")
    assert briefing_page_response.status_code == 200
    page_payload = briefing_page_response.json()
    assert page_payload["context"]["selection_basis"] == "suggested_story_id"
    assert page_payload["selected_story"]["story_id"] == "story-1"
    assert page_payload["routes"]["ask"].endswith("story_id=story-1&topic_key=retry-policy")


def test_watchlists_upsert_maps_value_error_to_400(monkeypatch) -> None:
    from apps.api.app.db import get_db
    from apps.api.app.routers import watchlists as watchlists_router

    class StubWatchlistsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def upsert_watchlist(self, **kwargs):  # noqa: ANN003
            raise ValueError("invalid matcher_type")

    def _fake_db():
        return object()

    def _allow_write():
        return None

    app = FastAPI()
    app.include_router(watchlists_router.router)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[watchlists_router.require_write_access] = _allow_write
    monkeypatch.setattr(watchlists_router, "WatchlistsService", StubWatchlistsService)

    client = TestClient(app)
    response = client.post(
        "/api/v1/watchlists",
        json={
            "name": "Retry policy",
            "matcher_type": "topic_key",
            "matcher_value": "retry-policy",
            "delivery_channel": "dashboard",
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid matcher_type"


def test_watchlists_upsert_and_delete_success_paths(monkeypatch) -> None:
    from apps.api.app.db import get_db
    from apps.api.app.routers import watchlists as watchlists_router

    class StubWatchlistsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def upsert_watchlist(self, **kwargs):  # noqa: ANN003
            return {
                "id": kwargs["watchlist_id"] or "wl-1",
                "name": kwargs["name"],
                "matcher_type": kwargs["matcher_type"],
                "matcher_value": kwargs["matcher_value"],
                "delivery_channel": kwargs["delivery_channel"],
                "enabled": kwargs["enabled"],
                "created_at": "2026-03-31T10:00:00Z",
                "updated_at": "2026-03-31T10:00:00Z",
            }

        def delete_watchlist(self, *, watchlist_id: str) -> bool:
            return watchlist_id == "wl-1"

    def _fake_db():
        return object()

    def _allow_write():
        return None

    app = FastAPI()
    app.include_router(watchlists_router.router)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[watchlists_router.require_write_access] = _allow_write
    monkeypatch.setattr(watchlists_router, "WatchlistsService", StubWatchlistsService)

    client = TestClient(app)
    upsert_response = client.post(
        "/api/v1/watchlists",
        json={
            "id": "wl-1",
            "name": "Retry policy",
            "matcher_type": "topic_key",
            "matcher_value": "retry-policy",
            "delivery_channel": "dashboard",
            "enabled": True,
        },
    )

    assert upsert_response.status_code == 200
    assert upsert_response.json()["id"] == "wl-1"

    delete_response = client.delete("/api/v1/watchlists/wl-1")
    assert delete_response.status_code == 204
    assert delete_response.content == b""


def test_watchlists_delete_trend_and_briefing_return_404_when_missing(monkeypatch) -> None:
    from apps.api.app.db import get_db
    from apps.api.app.routers import watchlists as watchlists_router

    class StubWatchlistsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def delete_watchlist(self, *, watchlist_id: str) -> bool:
            return False

        def get_watchlist_trend(self, *, watchlist_id, limit_runs=3, limit_cards=18):  # noqa: ANN001, ARG002
            return None

        def get_watchlist_briefing_page(
            self,
            *,
            watchlist_id,
            story_id=None,
            limit_runs=4,
            limit_cards=18,
            limit_stories=4,
            limit_evidence_per_story=3,
            query=None,
        ):  # noqa: ANN001, ARG002
            return None

        def get_watchlist_briefing(
            self,
            *,
            watchlist_id,
            limit_runs=4,
            limit_cards=18,
            limit_stories=4,
            limit_evidence_per_story=3,
        ):  # noqa: ANN001, ARG002
            return None

    def _fake_db():
        return object()

    def _allow_write():
        return None

    app = FastAPI()
    app.include_router(watchlists_router.router)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[watchlists_router.require_write_access] = _allow_write
    monkeypatch.setattr(watchlists_router, "WatchlistsService", StubWatchlistsService)

    client = TestClient(app)

    delete_response = client.delete("/api/v1/watchlists/wl-missing")
    assert delete_response.status_code == 404

    trend_response = client.get("/api/v1/watchlists/wl-missing/trend")
    assert trend_response.status_code == 404

    briefing_response = client.get("/api/v1/watchlists/wl-missing/briefing")
    assert briefing_response.status_code == 404

    briefing_page_response = client.get("/api/v1/watchlists/wl-missing/briefing/page")
    assert briefing_page_response.status_code == 404
