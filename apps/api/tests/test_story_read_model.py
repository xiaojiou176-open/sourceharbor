from __future__ import annotations

from typing import Any

from apps.api.app.services.retrieval import RetrievalService
from apps.api.app.services.story_read_model import (
    _build_route,
    _with_query_param,
    build_briefing_page_payload,
    build_story_question_seed,
    select_story_from_briefing,
)


class _FakeDB:
    def rollback(self) -> None:
        return None


def _make_story(story_id: str, *, headline: str = "Retry Policy") -> dict[str, Any]:
    return {
        "story_id": story_id,
        "story_key": f"topic:{story_id}",
        "headline": headline,
        "topic_key": "retry-policy",
        "topic_label": "Retry Policy",
        "source_count": 2,
        "run_count": 2,
        "matched_card_count": 2,
        "claim_kinds": ["recommendation"],
        "evidence_cards": [
            {
                "card_title": "Retry Policy",
                "card_body": "Retry policy is now explicit.",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "claim_kind": "recommendation",
            }
        ],
        "routes": {
            "watchlist_trend": "/trends?watchlist_id=wl-1",
            "briefing": f"/briefings?watchlist_id=wl-1&story_id={story_id}",
            "ask": f"/ask?watchlist_id=wl-1&story_id={story_id}&topic_key=retry-policy",
            "job_compare": "/jobs?job_id=job-2",
            "job_bundle": "/api/v1/jobs/job-2/bundle",
            "job_knowledge_cards": "/knowledge?job_id=job-2",
        },
        "latest_run_job_id": "job-2",
    }


def _make_briefing(*stories: Any, suggested_story_id: str | None = None) -> dict[str, Any]:
    return {
        "watchlist": {"id": "wl-1", "name": "Retry policy", "matcher_value": "retry-policy"},
        "summary": {"primary_story_headline": "Retry Policy"},
        "differences": {
            "compare": {"compare_route": "/jobs?job_id=job-2", "diff_excerpt": "@@ latest diff @@"}
        },
        "evidence": {
            "suggested_story_id": suggested_story_id,
            "stories": list(stories),
            "featured_runs": [],
        },
    }


def test_select_story_from_briefing_handles_missing_shapes_and_invalid_entries() -> None:
    assert select_story_from_briefing(None, story_id=None, query="retry") == (None, "none")
    assert select_story_from_briefing({}, story_id=None, query="retry") == (None, "none")
    assert select_story_from_briefing(
        {"evidence": {"stories": "bad"}}, story_id=None, query="retry"
    ) == (None, "none")
    assert select_story_from_briefing(
        _make_briefing("bad", 123, suggested_story_id=None),
        story_id=None,
        query="retry",
    ) == (None, "none")


def test_select_story_from_briefing_skips_invalid_rows_and_uses_requested_or_suggested() -> None:
    requested_story = _make_story("story-2", headline="Incident Timeline")
    briefing = _make_briefing("bad", requested_story, suggested_story_id="story-2")

    selected, basis = select_story_from_briefing(briefing, story_id="story-2", query="")

    assert basis == "requested_story_id"
    assert selected == requested_story

    suggested_story = _make_story("story-3")
    briefing = _make_briefing("bad", suggested_story, suggested_story_id="story-3")

    selected, basis = select_story_from_briefing(briefing, story_id=None, query="")

    assert basis == "suggested_story_id"
    assert selected == suggested_story


def test_select_story_from_briefing_uses_query_match_then_first_story_fallback() -> None:
    matching_story = _make_story("story-1", headline="Retries became the default posture")
    unmatched_story = _make_story("story-2", headline="Delivery timeline")
    briefing = _make_briefing("bad", matching_story, unmatched_story, suggested_story_id=None)

    selected, basis = select_story_from_briefing(
        briefing,
        story_id=None,
        query="default posture retry",
    )

    assert basis == "query_match"
    assert selected == matching_story

    selected, basis = select_story_from_briefing(
        _make_briefing("bad", unmatched_story, suggested_story_id=None),
        story_id=None,
        query="",
    )

    assert basis == "first_story"
    assert selected == unmatched_story


def test_build_story_question_seed_prefers_explicit_and_can_return_none() -> None:
    assert (
        build_story_question_seed(
            story=None,
            briefing=None,
            explicit_question="What changed in retry policy?",
        )
        == "What changed in retry policy?"
    )
    assert build_story_question_seed(story=None, briefing={"summary": {}}, watchlist={}) is None


def test_build_briefing_page_payload_uses_watchlist_fallback_and_preserves_existing_question() -> (
    None
):
    selected_story = _make_story("story-1")
    briefing = _make_briefing(selected_story, suggested_story_id="story-1")

    payload = build_briefing_page_payload(
        briefing=briefing,
        story_id="story-1",
        selection_query="retry policy",
        ask_question="What changed in retry policy?",
    )

    assert payload["selection"]["question_seed"] == "What changed in retry policy?"
    assert payload["routes"]["watchlist_trend"] == "/trends?watchlist_id=wl-1"
    assert payload["routes"]["briefing"] == "/briefings?watchlist_id=wl-1&story_id=story-1"
    assert payload["routes"]["ask"] == (
        "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy&"
        "question=What+changed+in+retry+policy%3F"
    )


def test_route_helpers_cover_filtered_and_empty_paths() -> None:
    assert _build_route("/briefings", watchlist_id="wl-1", story_id="story-1") == (
        "/briefings?watchlist_id=wl-1&story_id=story-1"
    )
    assert _build_route("/briefings", watchlist_id=None) == "/briefings"
    assert _build_route("", watchlist_id=None) is None
    assert _with_query_param("/ask?watchlist_id=wl-1", key="question", value="retry policy") == (
        "/ask?watchlist_id=wl-1&question=retry+policy"
    )
    assert _with_query_param("/ask?question=retry+policy", key="question", value="other") == (
        "/ask?question=retry+policy"
    )
    assert _with_query_param(None, key="question", value="retry policy") is None


def test_retrieval_extract_selected_story_uses_briefing_fallback_from_selection_story() -> None:
    service = RetrievalService(_FakeDB())  # type: ignore[arg-type]
    selected_story = _make_story("story-2")
    briefing = _make_briefing(selected_story, suggested_story_id="story-2")
    payload = {"selection": {"story": {"story_id": "story-2"}}}

    result = service._extract_selected_story(
        payload,
        briefing_payload=briefing,
        story_id="story-2",
        query="retry policy",
    )

    assert result == selected_story


def test_retrieval_extract_selected_story_prefers_complete_selected_story_payload() -> None:
    service = RetrievalService(_FakeDB())  # type: ignore[arg-type]
    selected_story = _make_story("story-1")

    result = service._extract_selected_story(
        {"selected_story": selected_story},
        briefing_payload=_make_briefing(selected_story, suggested_story_id="story-1"),
        story_id="story-1",
        query="retry policy",
    )

    assert result == selected_story


def test_retrieval_ensure_story_page_payload_normalizes_existing_page_payload() -> None:
    service = RetrievalService(_FakeDB())  # type: ignore[arg-type]
    selected_story = _make_story("story-1")
    payload = {
        "context": {"watchlist_id": "wl-1"},
        "briefing": {
            **_make_briefing(selected_story, suggested_story_id="story-1"),
            "selection": {
                "selected_story_id": "story-1",
                "selection_basis": "requested_story_id",
                "story": selected_story,
            },
        },
        "selected_story": {"story_id": "story-1"},
        "story_focus": {"headline": "stale"},
    }

    normalized = service._ensure_story_page_payload(
        payload,
        watchlist_id="wl-1",
        story_id="story-1",
        query="retry policy",
    )

    assert normalized is not None
    assert normalized["selected_story"]["story_id"] == "story-1"
    assert normalized["briefing"]["selection"]["story"] is None
    assert "story_focus" not in normalized


def test_retrieval_ensure_story_page_payload_builds_page_from_raw_briefing() -> None:
    service = RetrievalService(_FakeDB())  # type: ignore[arg-type]
    selected_story = _make_story("story-1")
    briefing = _make_briefing(selected_story, suggested_story_id="story-1")

    page = service._ensure_story_page_payload(
        briefing,
        watchlist_id="wl-1",
        story_id="story-1",
        query="retry policy",
    )

    assert page is not None
    assert page["context"]["selected_story_id"] == "story-1"
    assert page["context"]["question_seed"] == "Retry Policy"
    assert page["selected_story"]["story_id"] == "story-1"
    assert page["routes"]["ask"].startswith("/ask?watchlist_id=wl-1")
    assert page["ask_route"] == page["routes"]["ask"]
    assert page["briefing"]["selection"]["story"] is None
    assert page["story_change_summary"] is None
    assert page["fallback_actions"] == []


def test_retrieval_load_watchlist_briefing_page_returns_none_without_watchlist() -> None:
    service = RetrievalService(_FakeDB())  # type: ignore[arg-type]

    assert (
        service._load_watchlist_briefing_page(watchlist_id=None, story_id="story-1", query="retry")
        is None
    )


def test_retrieval_load_watchlist_briefing_page_delegates_when_watchlist_present(
    monkeypatch,
) -> None:
    service = RetrievalService(_FakeDB())  # type: ignore[arg-type]
    expected = {"context": {"watchlist_id": "wl-1"}}

    class StubWatchlistsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def get_watchlist_briefing_page(self, *, watchlist_id, story_id, query):  # noqa: ANN001
            assert watchlist_id == "wl-1"
            assert story_id == "story-1"
            assert query == "retry policy"
            return expected

    monkeypatch.setattr(
        "apps.api.app.services.watchlists.WatchlistsService",
        StubWatchlistsService,
    )

    payload = service._load_watchlist_briefing_page(
        watchlist_id="wl-1",
        story_id="story-1",
        query="retry policy",
    )

    assert payload == expected
