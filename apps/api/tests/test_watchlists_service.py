from __future__ import annotations

import importlib
import os
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DBAPIError


def _load_watchlists_module():
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/sourceharbor-watchlists-test.db")
    os.environ.setdefault("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
    os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
    os.environ.setdefault("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
    os.environ.setdefault("SQLITE_STATE_PATH", "/tmp/sourceharbor-watchlists-test-state.db")
    module = importlib.import_module("apps.api.app.services.watchlists")
    return importlib.reload(module)


class FakeDb:
    def commit(self) -> None:
        return None

    def refresh(self, _obj) -> None:
        return None


def test_upsert_and_delete_watchlist_on_notification_config(monkeypatch) -> None:
    module = _load_watchlists_module()
    config = SimpleNamespace(category_rules={})
    monkeypatch.setattr(module, "get_notification_config", lambda db: config)

    service = module.WatchlistsService(FakeDb())
    created = service.upsert_watchlist(
        watchlist_id=None,
        name="Retry policy",
        matcher_type="topic_key",
        matcher_value="retry-policy",
        delivery_channel="dashboard",
        enabled=True,
    )

    assert created["name"] == "Retry policy"
    assert service.list_watchlists()[0]["matcher_value"] == "retry-policy"
    assert service.delete_watchlist(watchlist_id=created["id"]) is True
    assert service.list_watchlists() == []


def test_upsert_watchlist_updates_existing_entry_and_missing_delete_returns_false(
    monkeypatch,
) -> None:
    module = _load_watchlists_module()
    config = SimpleNamespace(
        category_rules={
            "watchlists": [
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
        }
    )
    monkeypatch.setattr(module, "get_notification_config", lambda db: config)

    service = module.WatchlistsService(FakeDb())
    updated = service.upsert_watchlist(
        watchlist_id="wl-1",
        name="Reliability policy",
        matcher_type="claim_kind",
        matcher_value="recommendation",
        delivery_channel="email",
        enabled=False,
    )

    assert updated["id"] == "wl-1"
    assert updated["name"] == "Reliability policy"
    assert updated["matcher_type"] == "claim_kind"
    assert updated["matcher_value"] == "recommendation"
    assert updated["delivery_channel"] == "email"
    assert updated["enabled"] is False
    assert service.list_watchlists() == [updated]
    assert service.delete_watchlist(watchlist_id="wl-missing") is False


def test_list_watchlists_normalizes_root_and_skips_invalid_items(monkeypatch) -> None:
    module = _load_watchlists_module()
    config = SimpleNamespace(
        category_rules={
            "watchlists": [
                {
                    "id": "wl-1",
                    "name": "Retry policy",
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
                {
                    "id": "",
                    "name": "Broken",
                    "matcher_type": "topic_key",
                    "matcher_value": "broken",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
            ],
            "youtube": {"channel": "UC123"},
        }
    )
    monkeypatch.setattr(module, "get_notification_config", lambda db: config)

    service = module.WatchlistsService(FakeDb())
    items = service.list_watchlists()

    assert items == [
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


def test_get_watchlist_trend_groups_cards_and_tracks_added_removed(monkeypatch) -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    watchlist = {
        "id": "wl-1",
        "name": "Retry policy",
        "matcher_type": "topic_key",
        "matcher_value": "retry-policy",
        "delivery_channel": "dashboard",
        "enabled": True,
        "created_at": "2026-03-31T10:00:00Z",
        "updated_at": "2026-03-31T10:00:00Z",
    }
    monkeypatch.setattr(service, "list_watchlists", lambda: [watchlist])
    monkeypatch.setattr(
        service,
        "_load_matching_cards",
        lambda matcher_type, matcher_value, limit_cards: [
            {
                "card_id": "card-1",
                "job_id": "job-2",
                "video_id": "video-2",
                "platform": "youtube",
                "video_title": "Second run",
                "source_url": "https://example.com/2",
                "created_at": "2026-04-01T11:00:00Z",
                "card_type": "claim",
                "card_title": "Claim 1",
                "card_body": "Body 1",
                "source_section": "summary",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "claim_kind": "recommendation",
            },
            {
                "card_id": "card-2",
                "job_id": "job-1",
                "video_id": "video-1",
                "platform": "youtube",
                "video_title": "First run",
                "source_url": "https://example.com/1",
                "created_at": "2026-03-31T11:00:00Z",
                "card_type": "claim",
                "card_title": "Claim 2",
                "card_body": "Body 2",
                "source_section": "summary",
                "topic_key": "delivery",
                "topic_label": "Delivery",
                "claim_kind": "risk",
            },
        ],
    )

    payload = service.get_watchlist_trend(watchlist_id="wl-1", limit_runs=2, limit_cards=5)

    assert payload is not None
    assert payload["summary"]["recent_runs"] == 2
    assert payload["summary"]["matched_cards"] == 2
    assert payload["timeline"][0]["job_id"] == "job-2"
    assert payload["timeline"][0]["added_topics"] == ["retry-policy"]
    assert payload["timeline"][1]["removed_topics"] == ["retry-policy"]
    assert payload["timeline"][1]["added_claim_kinds"] == ["risk"]
    assert payload["timeline"][1]["removed_claim_kinds"] == ["recommendation"]
    assert payload["merged_stories"][0]["story_key"] == "topic:retry-policy"
    assert payload["merged_stories"][0]["headline"] == "Retry Policy"
    assert payload["merged_stories"][0]["platforms"] == ["youtube"]
    assert payload["merged_stories"][0]["run_ids"] == ["job-2"]
    assert payload["merged_stories"][1]["story_key"] == "topic:delivery"


def test_get_watchlist_trend_returns_none_when_watchlist_is_missing() -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    service.list_watchlists = list

    assert service.get_watchlist_trend(watchlist_id="missing") is None


def test_get_watchlist_briefing_builds_summary_differences_and_evidence(monkeypatch) -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    watchlist = {
        "id": "wl-1",
        "name": "Retry policy",
        "matcher_type": "topic_key",
        "matcher_value": "retry-policy",
        "delivery_channel": "dashboard",
        "enabled": True,
        "created_at": "2026-03-31T10:00:00Z",
        "updated_at": "2026-03-31T10:00:00Z",
    }
    monkeypatch.setattr(
        service,
        "get_watchlist_trend",
        lambda **_: {
            "watchlist": watchlist,
            "summary": {
                "recent_runs": 2,
                "matched_cards": 4,
                "matcher_type": "topic_key",
                "matcher_value": "retry-policy",
            },
            "timeline": [
                {
                    "job_id": "job-2",
                    "video_id": "video-2",
                    "platform": "youtube",
                    "title": "Second run",
                    "source_url": "https://example.com/2",
                    "created_at": "2026-04-01T11:00:00Z",
                    "matched_card_count": 2,
                    "cards": [],
                    "topics": ["retry-policy"],
                    "claim_kinds": ["recommendation"],
                    "added_topics": ["retry-policy"],
                    "removed_topics": [],
                    "added_claim_kinds": ["recommendation"],
                    "removed_claim_kinds": [],
                },
                {
                    "job_id": "job-1",
                    "video_id": "video-1",
                    "platform": "rss",
                    "title": "First run",
                    "source_url": "https://example.com/1",
                    "created_at": "2026-03-31T11:00:00Z",
                    "matched_card_count": 2,
                    "cards": [],
                    "topics": ["delivery"],
                    "claim_kinds": ["risk"],
                    "added_topics": [],
                    "removed_topics": ["delivery"],
                    "added_claim_kinds": [],
                    "removed_claim_kinds": ["risk"],
                },
            ],
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
                    "source_urls": ["https://example.com/1", "https://example.com/2"],
                    "run_ids": ["job-1", "job-2"],
                    "cards": [
                        {
                            "card_id": "card-1",
                            "job_id": "job-2",
                            "video_id": "video-2",
                            "platform": "youtube",
                            "video_title": "Second run",
                            "source_url": "https://example.com/2",
                            "created_at": "2026-04-01T11:00:00Z",
                            "card_type": "claim",
                            "card_title": "Retry policy claim",
                            "card_body": "Retry policy is now explicit.",
                            "source_section": "summary",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry Policy",
                            "claim_kind": "recommendation",
                        }
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(
        service,
        "_build_briefing_compare",
        lambda **_: {
            "job_id": "job-2",
            "has_previous": True,
            "previous_job_id": "job-1",
            "changed": True,
            "added_lines": 3,
            "removed_lines": 1,
            "diff_excerpt": "--- old\n+++ new",
            "compare_route": "/jobs?job_id=job-2",
        },
    )

    payload = service.get_watchlist_briefing(watchlist_id="wl-1")

    assert payload is not None
    assert "Retry policy currently converges on Retry Policy." in payload["summary"]["overview"]
    assert payload["summary"]["signals"][0]["story_key"] == "topic:retry-policy"
    assert payload["differences"]["latest_job_id"] == "job-2"
    assert payload["differences"]["new_story_keys"] == []
    assert payload["differences"]["compare"]["compare_route"] == "/jobs?job_id=job-2"
    assert payload["differences"]["compare"]["job_id"] == "job-2"
    assert payload["evidence"]["stories"][0]["routes"]["job_bundle"] == "/api/v1/jobs/job-2/bundle"
    assert (
        payload["evidence"]["stories"][0]["routes"]["job_knowledge_cards"]
        == "/knowledge?job_id=job-2"
    )
    assert (
        payload["evidence"]["featured_runs"][0]["routes"]["watchlist_trend"]
        == "/trends?watchlist_id=wl-1"
    )


def test_get_watchlist_briefing_exposes_summary_differences_and_evidence(monkeypatch) -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    watchlist = {
        "id": "wl-1",
        "name": "Retry policy",
        "matcher_type": "topic_key",
        "matcher_value": "retry-policy",
        "delivery_channel": "dashboard",
        "enabled": True,
        "created_at": "2026-03-31T10:00:00Z",
        "updated_at": "2026-03-31T10:00:00Z",
    }
    monkeypatch.setattr(service, "list_watchlists", lambda: [watchlist])
    monkeypatch.setattr(
        service,
        "_load_matching_cards",
        lambda matcher_type, matcher_value, limit_cards: [
            {
                "card_id": "card-1",
                "job_id": "00000000-0000-4000-8000-000000000002",
                "video_id": "video-2",
                "platform": "youtube",
                "video_title": "Second run",
                "source_url": "https://example.com/2",
                "created_at": "2026-04-01T11:00:00Z",
                "card_type": "claim",
                "card_title": "Claim 1",
                "card_body": "Body 1",
                "source_section": "summary",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "claim_kind": "recommendation",
            },
            {
                "card_id": "card-2",
                "job_id": "00000000-0000-4000-8000-000000000001",
                "video_id": "video-1",
                "platform": "youtube",
                "video_title": "First run",
                "source_url": "https://example.com/1",
                "created_at": "2026-03-31T11:00:00Z",
                "card_type": "claim",
                "card_title": "Claim 2",
                "card_body": "Body 2",
                "source_section": "summary",
                "topic_key": "delivery",
                "topic_label": "Delivery",
                "claim_kind": "risk",
            },
        ],
    )
    monkeypatch.setattr(
        service,
        "_build_briefing_compare",
        lambda latest_run: {
            "job_id": "00000000-0000-4000-8000-000000000002",
            "has_previous": True,
            "previous_job_id": "00000000-0000-4000-8000-000000000001",
            "changed": True,
            "added_lines": 2,
            "removed_lines": 1,
            "diff_excerpt": "@@ latest diff @@",
            "compare_route": "/jobs?job_id=00000000-0000-4000-8000-000000000002",
        },
    )

    payload = service.get_watchlist_briefing(
        watchlist_id="wl-1",
        limit_runs=2,
        limit_cards=5,
        limit_stories=2,
        limit_evidence_per_story=1,
    )

    assert payload is not None
    assert payload["summary"]["primary_story_headline"] == "Retry Policy"
    assert payload["summary"]["signals"][0]["story_key"] == "topic:retry-policy"
    assert payload["differences"]["new_story_keys"] == ["topic:retry-policy"]
    assert payload["differences"]["removed_story_keys"] == ["topic:delivery"]
    assert (
        payload["differences"]["compare"]["compare_route"]
        == "/jobs?job_id=00000000-0000-4000-8000-000000000002"
    )
    assert (
        payload["evidence"]["suggested_story_id"] == payload["evidence"]["stories"][0]["story_id"]
    )
    assert (
        payload["evidence"]["stories"][0]["routes"]["watchlist_trend"]
        == "/trends?watchlist_id=wl-1"
    )
    assert payload["evidence"]["stories"][0]["routes"]["job_bundle"].endswith("/bundle")
    assert (
        payload["evidence"]["featured_runs"][0]["routes"]["job_knowledge_cards"]
        == "/knowledge?job_id=00000000-0000-4000-8000-000000000002"
    )


def test_get_watchlist_briefing_returns_none_when_watchlist_is_missing() -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    service.list_watchlists = list

    assert service.get_watchlist_briefing(watchlist_id="missing") is None


def test_get_watchlist_briefing_page_adds_selected_story_and_routes(monkeypatch) -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    briefing_payload = {
        "watchlist": {
            "id": "wl-1",
            "name": "Retry policy",
            "matcher_type": "topic_key",
            "matcher_value": "retry-policy",
            "delivery_channel": "dashboard",
            "enabled": True,
            "created_at": "2026-03-31T10:00:00Z",
            "updated_at": "2026-03-31T10:00:00Z",
        },
        "summary": {
            "overview": "Retry policy currently converges across recent sources.",
            "source_count": 2,
            "run_count": 2,
            "story_count": 1,
            "matched_cards": 2,
            "primary_story_headline": "Retry Policy",
            "signals": [],
        },
        "differences": {
            "compare": {
                "job_id": "job-2",
                "has_previous": True,
                "previous_job_id": "job-1",
                "changed": True,
                "added_lines": 2,
                "removed_lines": 1,
                "diff_excerpt": "@@ latest diff @@",
                "compare_route": "/jobs?job_id=job-2",
            }
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
                    "source_count": 2,
                    "run_count": 2,
                    "matched_card_count": 1,
                    "platforms": ["youtube"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/retry"],
                    "latest_run_job_id": "job-2",
                    "evidence_cards": [],
                    "routes": {
                        "watchlist_trend": "/trends?watchlist_id=wl-1",
                        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                        "ask": "/ask?watchlist_id=wl-1&question=Retry+Policy&story_id=story-1&topic_key=retry-policy",
                        "job_compare": "/jobs?job_id=job-2",
                        "job_bundle": "/api/v1/jobs/job-2/bundle",
                        "job_knowledge_cards": "/knowledge?job_id=job-2",
                    },
                }
            ],
            "featured_runs": [],
        },
    }
    monkeypatch.setattr(service, "get_watchlist_briefing", lambda **_: briefing_payload)

    payload = service.get_watchlist_briefing_page(watchlist_id="wl-1")

    assert payload is not None
    assert payload["context"]["selected_story_id"] == "story-1"
    assert payload["context"]["selection_basis"] == "suggested_story_id"
    assert payload["briefing"]["selection"]["selected_story_id"] == "story-1"
    assert payload["selected_story"]["story_id"] == "story-1"
    assert payload["compare_route"] == "/jobs?job_id=job-2"
    assert payload["ask_route"].endswith("story_id=story-1&topic_key=retry-policy")


def test_get_watchlist_briefing_page_returns_requested_story_fallback(monkeypatch) -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    watchlist = {
        "id": "wl-1",
        "name": "Retry policy",
        "matcher_type": "topic_key",
        "matcher_value": "retry-policy",
        "delivery_channel": "dashboard",
        "enabled": True,
        "created_at": "2026-03-31T10:00:00Z",
        "updated_at": "2026-03-31T10:00:00Z",
    }
    monkeypatch.setattr(
        service,
        "get_watchlist_briefing",
        lambda **_: {
            "watchlist": watchlist,
            "summary": {
                "overview": "Retry policy does not yet converge on a repeated story.",
                "source_count": 0,
                "run_count": 1,
                "story_count": 0,
                "matched_cards": 0,
                "primary_story_headline": None,
                "signals": [],
            },
            "differences": {
                "latest_job_id": None,
                "previous_job_id": None,
                "added_topics": [],
                "removed_topics": [],
                "added_claim_kinds": [],
                "removed_claim_kinds": [],
                "new_story_keys": [],
                "removed_story_keys": [],
                "compare": None,
            },
            "evidence": {
                "suggested_story_id": None,
                "stories": [],
                "featured_runs": [],
            },
        },
    )

    payload = service.get_watchlist_briefing_page(watchlist_id="wl-1", story_id="story-missing")

    assert payload is not None
    assert payload["selected_story"] is None
    assert (
        payload["fallback_reason"]
        == "The requested story_id was not found inside the current briefing context."
    )
    assert (
        payload["fallback_next_step"]
        == "Use the selected story from the current briefing or return to the watchlist overview."
    )
    assert [item["kind"] for item in payload["fallback_actions"]] == [
        "open_briefing",
        "open_trend",
    ]


def test_get_watchlist_briefing_page_returns_no_story_fallback(monkeypatch) -> None:
    module = _load_watchlists_module()
    service = module.WatchlistsService(FakeDb())
    watchlist = {
        "id": "wl-1",
        "name": "Retry policy",
        "matcher_type": "topic_key",
        "matcher_value": "retry-policy",
        "delivery_channel": "dashboard",
        "enabled": True,
        "created_at": "2026-03-31T10:00:00Z",
        "updated_at": "2026-03-31T10:00:00Z",
    }
    monkeypatch.setattr(
        service,
        "get_watchlist_briefing",
        lambda **_: {
            "watchlist": watchlist,
            "summary": {
                "overview": "Retry policy does not yet converge on a repeated story.",
                "source_count": 0,
                "run_count": 1,
                "story_count": 0,
                "matched_cards": 0,
                "primary_story_headline": None,
                "signals": [],
            },
            "differences": {
                "latest_job_id": None,
                "previous_job_id": None,
                "added_topics": [],
                "removed_topics": [],
                "added_claim_kinds": [],
                "removed_claim_kinds": [],
                "new_story_keys": [],
                "removed_story_keys": [],
                "compare": None,
            },
            "evidence": {
                "suggested_story_id": None,
                "stories": [],
                "featured_runs": [],
            },
        },
    )

    payload = service.get_watchlist_briefing_page(watchlist_id="wl-1")

    assert payload is not None
    assert payload["selected_story"] is None
    assert payload["fallback_reason"] == "This watchlist does not yet expose a selected story."
    assert (
        payload["fallback_next_step"]
        == "Open the trend timeline or wait for more matched evidence to accumulate."
    )
    assert payload["fallback_actions"] == [
        {
            "kind": "open_trend",
            "label": "Open trend timeline",
            "route": "/trends?watchlist_id=wl-1",
        }
    ]


def test_story_read_model_helpers_cover_tail_branches() -> None:
    module = importlib.import_module("apps.api.app.services.story_read_model")
    module = importlib.reload(module)

    assert module.select_story_from_briefing(None, story_id=None, query="retry") == (None, "none")
    assert module.select_story_from_briefing(
        {"evidence": None},
        story_id=None,
        query="retry",
    ) == (None, "none")
    assert module.select_story_from_briefing(
        {"evidence": {"stories": "bad"}},
        story_id=None,
        query="retry",
    ) == (None, "none")
    assert module.select_story_from_briefing(
        {"evidence": {"stories": [None, "skip-me"]}},
        story_id="story-x",
        query="retry",
    ) == (None, "none")

    suggested_story = {"story_id": "story-2", "headline": "Story Two"}
    selected_story, basis = module.select_story_from_briefing(
        {"evidence": {"suggested_story_id": "story-2", "stories": [None, suggested_story]}},
        story_id=None,
        query="",
    )
    assert selected_story == suggested_story
    assert basis == "suggested_story_id"

    score = module._score_story_match(
        story={
            "headline": "",
            "topic_key": "",
            "topic_label": "",
            "claim_kinds": ["recommendation"],
            "evidence_cards": [
                None,
                {
                    "card_title": "Retry Policy",
                    "card_body": "Use retries by default.",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "claim_kind": "recommendation",
                },
            ],
        },
        query="retry policy",
    )
    assert score >= 1

    assert (
        module.build_story_question_seed(
            story=None,
            briefing=None,
            explicit_question=" What changed? ",
        )
        == "What changed?"
    )
    assert (
        module.build_story_question_seed(
            story=None,
            briefing={"summary": {}},
            watchlist=None,
            explicit_question=None,
        )
        is None
    )
    assert module._build_route("/briefings", watchlist_id="wl-1", story_id=None) == (
        "/briefings?watchlist_id=wl-1"
    )
    assert module._build_route("/trends") == "/trends"
    assert module._build_route("") is None
    assert (
        module._with_query_param("/ask?watchlist_id=wl-1", key="question", value=None)
        == "/ask?watchlist_id=wl-1"
    )
    assert module._with_query_param(None, key="question", value="Retry Policy") is None


def test_watchlist_private_helpers_cover_compare_story_grouping_and_fallbacks(monkeypatch) -> None:
    module = _load_watchlists_module()
    jobs_module = importlib.import_module("apps.api.app.services.jobs")

    class StubJobsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def compare_with_previous(self, *, job_id):  # noqa: ANN001
            assert str(job_id) == "00000000-0000-4000-8000-000000000002"
            return {
                "has_previous": True,
                "previous_job_id": "job-1",
                "diff_markdown": "\n".join(f"line {index}" for index in range(12)),
                "stats": {"changed": True, "added_lines": 3, "removed_lines": 1},
            }

    monkeypatch.setattr(jobs_module, "JobsService", StubJobsService)
    service = module.WatchlistsService(FakeDb())

    assert service._build_briefing_compare(latest_run=None) is None
    assert service._build_briefing_compare(latest_run={"job_id": "bad"}) is None
    compare = service._build_briefing_compare(
        latest_run={"job_id": "00000000-0000-4000-8000-000000000002"}
    )
    assert compare == {
        "job_id": "00000000-0000-4000-8000-000000000002",
        "has_previous": True,
        "previous_job_id": "job-1",
        "changed": True,
        "added_lines": 3,
        "removed_lines": 1,
        "diff_excerpt": "\n".join(f"line {index}" for index in range(8)),
        "compare_route": "/jobs?job_id=00000000-0000-4000-8000-000000000002",
    }

    routes = service._build_briefing_routes(
        watchlist_id="wl-1",
        job_id="job-2",
        story_id="story-1",
        topic_key="retry-policy",
        question="Retry Policy",
    )
    assert routes["briefing"] == "/briefings?watchlist_id=wl-1&story_id=story-1"
    assert (
        routes["ask"]
        == "/ask?watchlist_id=wl-1&question=Retry+Policy&story_id=story-1&topic_key=retry-policy"
    )
    assert routes["job_bundle"] == "/api/v1/jobs/job-2/bundle"

    stories = service._build_merged_stories(
        rows=[
            {
                "source_url": "https://example.com/retry",
                "created_at": "2026-04-01T10:00:00Z",
                "platform": "youtube",
                "claim_kind": "",
                "topic_key": "",
                "topic_label": "",
                "job_id": "job-1",
                "card_title": "Retry Policy",
            },
            {
                "source_url": "https://example.com/retry",
                "created_at": "2026-04-01T11:00:00Z",
                "platform": "rss",
                "claim_kind": "recommendation",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "job_id": "job-2",
                "card_title": "Retry Policy",
            },
        ],
        limit_cards=2,
    )
    assert stories[0]["latest_created_at"] == "2026-04-01T11:00:00Z"
    assert stories[0]["topic_key"] == "retry-policy"
    assert stories[0]["topic_label"] == "Retry Policy"
    assert stories[0]["claim_kinds"] == ["recommendation"]
    assert service._story_keys_for_run(merged_stories=stories, job_id=None) == set()
    assert service._story_keys_for_run(merged_stories=stories, job_id="job-2") == {
        "topic:retry-policy"
    }
    assert service._resolve_story_key({"source_url": "https://example.com/retry"}) == (
        "source:https://example.com/retry"
    )
    assert service._resolve_story_key({"card_title": "Retry Policy"}) == "title:retry policy"
    assert service._resolve_story_key({"card_id": "card-9"}) == "card:card-9"
    assert service._resolve_story_headline({}) == "Merged story"


def test_watchlist_private_helpers_cover_matching_cards_and_rule_validation(monkeypatch) -> None:
    module = _load_watchlists_module()

    class RowsResult:
        def __init__(self, rows):
            self._rows = rows

        def mappings(self):
            return self

        def all(self):
            return self._rows

    class QueryDb(FakeDb):
        def __init__(self, rows):
            self.rows = rows
            self.rollback_calls = 0

        def execute(self, _statement, _params=None):  # noqa: ANN001
            return RowsResult(self.rows)

        def rollback(self) -> None:
            self.rollback_calls += 1

    class ErrorDb(QueryDb):
        def execute(self, _statement, _params=None):  # noqa: ANN001
            raise DBAPIError("SELECT", {}, Exception("boom"))

    service = module.WatchlistsService(
        QueryDb(
            [
                {
                    "card_id": "card-1",
                    "job_id": "job-1",
                    "video_id": "video-1",
                    "platform": "",
                    "video_title": "",
                    "source_url": "",
                    "created_at": "2026-04-01T11:00:00Z",
                    "card_type": "",
                    "card_title": "",
                    "card_body": "Body 1",
                    "source_section": "",
                    "topic_key": "",
                    "topic_label": "",
                    "claim_kind": "",
                }
            ]
        )
    )
    cards = service._load_matching_cards(
        matcher_type="source_match",
        matcher_value="retry-policy",
        limit_cards=2,
    )
    assert cards == [
        {
            "card_id": "card-1",
            "job_id": "job-1",
            "video_id": "video-1",
            "platform": "unknown",
            "video_title": None,
            "source_url": None,
            "created_at": "2026-04-01T11:00:00Z",
            "card_type": "unknown",
            "card_title": None,
            "card_body": "Body 1",
            "source_section": "",
            "topic_key": None,
            "topic_label": None,
            "claim_kind": None,
        }
    ]

    error_db = ErrorDb([])
    service = module.WatchlistsService(error_db)
    assert (
        service._load_matching_cards(
            matcher_type="platform",
            matcher_value="youtube",
            limit_cards=1,
        )
        == []
    )
    assert error_db.rollback_calls == 1

    config = SimpleNamespace(
        category_rules={
            "watchlists": [
                {
                    "id": "wl-1",
                    "name": "Retry policy",
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
                {
                    "id": "wl-2",
                    "name": "Broken matcher",
                    "matcher_type": "invalid",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
                {
                    "id": "wl-3",
                    "name": "Broken delivery",
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "sms",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
                "skip-me",
            ],
            "youtube": {"channel": "UC123"},
            "default_rule": {"delivery_channel": "dashboard"},
        }
    )
    monkeypatch.setattr(module, "get_notification_config", lambda db: config)
    service = module.WatchlistsService(FakeDb())

    assert service.list_watchlists() == [
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
    normalized_root = service._normalize_category_rules_root(config.category_rules)
    assert normalized_root["category_rules"] == {
        "youtube": {"channel": "UC123"},
        "default_rule": {"delivery_channel": "dashboard"},
    }
    assert normalized_root["default_rule"] == {"delivery_channel": "dashboard"}
    assert normalized_root["watchlists"][0]["id"] == "wl-1"
    with pytest.raises(ValueError, match="invalid matcher_type"):
        service._normalize_matcher_type("invalid")
    with pytest.raises(ValueError, match="invalid delivery_channel"):
        service._normalize_delivery_channel("sms")
