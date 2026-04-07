from __future__ import annotations

import concurrent.futures
import importlib
import json
import types
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from apps.api.app.errors import ApiServiceError
from apps.api.app.services.retrieval import RetrievalService


class _RowsResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _RowsResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeDB:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls = 0
        self.rollback_calls = 0

    def execute(self, _statement: Any, _params: dict[str, Any] | None = None) -> _RowsResult:
        self.calls += 1
        return _RowsResult(self.rows)

    def rollback(self) -> None:
        self.rollback_calls += 1


class _ErrorDB(_FakeDB):
    def execute(self, _statement: Any, _params: dict[str, Any] | None = None) -> _RowsResult:
        raise DBAPIError("SELECT", {}, Exception("boom"))


def test_retrieval_service_search_matches_digest_and_applies_top_k(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "digest.md").write_text(
        "Provider timeout detected and retried.", encoding="utf-8"
    )
    (artifact_root / "transcript.txt").write_text("Everything is normal here.", encoding="utf-8")

    db = _FakeDB(
        [
            {
                "job_id": uuid.uuid4(),
                "video_id": uuid.uuid4(),
                "kind": "video_digest_v1",
                "mode": "full",
                "artifact_root": str(artifact_root),
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
            }
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]

    payload = service.search(
        query="timeout", top_k=1, mode="keyword", filters={"platform": "youtube"}
    )

    assert payload["query"] == "timeout"
    assert payload["top_k"] == 1
    assert payload["filters"] == {"platform": "youtube"}
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "digest"
    assert "timeout detected" in payload["items"][0]["snippet"].lower()


def test_retrieval_service_ignores_unsupported_filters(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "digest.md").write_text("quick summary", encoding="utf-8")

    db = _FakeDB(
        [
            {
                "job_id": uuid.uuid4(),
                "video_id": uuid.uuid4(),
                "kind": "video_digest_v1",
                "mode": "full",
                "artifact_root": str(artifact_root),
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
            }
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]

    payload = service.search(
        query="quick", top_k=5, mode="keyword", filters={"unknown": "x", "platform": "youtube"}
    )

    assert payload["filters"] == {"platform": "youtube"}


def test_retrieval_service_semantic_mode_uses_embedding_path(monkeypatch) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "_search_keyword", lambda **kwargs: [])  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "_search_semantic",
        lambda **kwargs: [
            {
                "job_id": "job-1",
                "video_id": "video-1",
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
                "kind": "video_digest_v1",
                "mode": "full",
                "source": "transcript",
                "snippet": "timeout due to network jitter",
                "score": 0.91,
            }
        ],
    )

    payload = service.search(
        query="timeout issue", top_k=3, mode="semantic", filters={"platform": "youtube"}
    )

    assert payload["query"] == "timeout issue"
    assert payload["top_k"] == 3
    assert payload["items"][0]["source"] == "transcript"
    assert payload["items"][0]["score"] == 0.91


def test_retrieval_service_hybrid_mode_merges_and_deduplicates(monkeypatch) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(
        service,
        "_search_keyword",
        lambda **kwargs: [
            {
                "job_id": "job-1",
                "video_id": "video-1",
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
                "kind": "video_digest_v1",
                "mode": "full",
                "source": "transcript",
                "snippet": "provider timeout in transcript chunk",
                "score": 1.2,
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "_search_semantic",
        lambda **kwargs: [
            {
                "job_id": "job-1",
                "video_id": "video-1",
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
                "kind": "video_digest_v1",
                "mode": "full",
                "source": "transcript",
                "snippet": "provider timeout in transcript chunk",
                "score": 0.82,
            },
            {
                "job_id": "job-2",
                "video_id": "video-2",
                "platform": "youtube",
                "video_uid": "def456",
                "source_url": "https://www.youtube.com/watch?v=def456",
                "title": "Demo 2",
                "kind": "video_digest_v1",
                "mode": "full",
                "source": "outline",
                "snippet": "error budget and retry policy",
                "score": 0.79,
            },
        ],
    )

    payload = service.search(
        query="timeout", top_k=5, mode="hybrid", filters={"platform": "youtube"}
    )

    assert len(payload["items"]) == 2
    assert payload["items"][0]["job_id"] == "job-1"
    assert payload["items"][0]["score"] == 1.2
    assert payload["items"][1]["job_id"] == "job-2"


def test_retrieval_service_answer_uses_briefing_context_and_returns_contract(monkeypatch) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "_load_watchlist_briefing_page",
        lambda **_: {
            "watchlist": {"id": "wl-1", "name": "Retry policy"},
            "summary": {
                "overview": "Retry policy currently converges across recent sources.",
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
                    "has_previous": True,
                    "compare_route": "/jobs?job_id=job-2",
                    "diff_excerpt": "@@ latest diff @@",
                },
            },
            "evidence": {
                "suggested_story_id": "story-1",
                "stories": [
                    {
                        "story_id": "story-1",
                        "headline": "Retry Policy",
                        "story_key": "topic:retry-policy",
                        "topic_key": "retry-policy",
                        "topic_label": "Retry Policy",
                        "latest_run_job_id": "job-2",
                        "source_count": 2,
                        "run_count": 2,
                        "matched_card_count": 2,
                        "claim_kinds": ["recommendation"],
                        "evidence_cards": [
                            {
                                "card_id": "card-1",
                                "job_id": "job-2",
                                "platform": "youtube",
                                "source_url": "https://example.com/retry",
                                "card_title": "Retry policy card",
                                "card_body": "Retry policy is now explicit.",
                                "source_section": "summary",
                            }
                        ],
                        "routes": {
                            "watchlist_trend": "/trends?watchlist_id=wl-1",
                            "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                            "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                            "job_bundle": "/api/v1/jobs/job-2/bundle",
                            "job_knowledge_cards": "/knowledge?job_id=job-2",
                        },
                    }
                ],
            },
            "context": {
                "watchlist_id": "wl-1",
                "watchlist_name": "Retry policy",
                "story_id": None,
                "selected_story_id": "story-1",
                "story_headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "selection_basis": "query_match",
                "question_seed": "retry policy",
            },
            "selected_story": {
                "story_id": "story-1",
                "headline": "Retry Policy",
                "story_key": "topic:retry-policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "latest_run_job_id": "job-2",
                "source_count": 2,
                "run_count": 2,
                "matched_card_count": 2,
                "claim_kinds": ["recommendation"],
                "routes": {
                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
            },
            "routes": {
                "watchlist_trend": "/trends?watchlist_id=wl-1",
                "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                "job_bundle": "/api/v1/jobs/job-2/bundle",
                "job_knowledge_cards": "/knowledge?job_id=job-2",
            },
        },
    )

    def fake_search(*, query, top_k, filters, mode):
        assert query == "retry policy"
        assert top_k == 3
        assert mode == "keyword"
        assert filters == {"platform": "youtube", "job_id": "job-2"}
        return {
            "query": query,
            "top_k": top_k,
            "filters": filters,
            "items": [
                {
                    "job_id": "job-2",
                    "video_id": "video-2",
                    "platform": "youtube",
                    "video_uid": "abc123",
                    "source_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Demo",
                    "kind": "video_digest_v1",
                    "mode": "full",
                    "source": "knowledge_cards",
                    "snippet": "Retry policy is now explicit and backed by the latest card.",
                    "score": 2.2,
                }
            ],
        }

    monkeypatch.setattr(service, "search", fake_search)

    payload = service.answer(
        query="retry policy",
        watchlist_id="wl-1",
        top_k=3,
        mode="keyword",
        filters={"platform": "youtube"},
    )

    assert payload["context"]["selected_story_id"] == "story-1"
    assert payload["context"]["selection_basis"] == "query_match"
    assert payload["context"]["briefing_available"] is True
    assert payload["selected_story"]["story_id"] == "story-1"
    assert (
        payload["selected_story"]["routes"]["briefing"]
        == "/briefings?watchlist_id=wl-1&story_id=story-1"
    )
    assert payload["answer"]["confidence"] == "grounded"
    assert "Retry Policy" in payload["answer"]["direct_answer"]
    assert payload["answer"]["reason"] == (
        '"Retry Policy" is newly surfaced in the latest briefing and is already backed by '
        "2 source families."
    )
    assert "Added topics: retry-policy." in payload["changes"]["summary"]
    assert payload["changes"]["story_focus_summary"] == (
        '"Retry Policy" is newly surfaced in the latest briefing and is already backed by '
        "2 source families."
    )
    assert payload["changes"]["compare_route"] == "/jobs?job_id=job-2"
    assert payload["citations"][0]["kind"] == "briefing_story"
    assert payload["citations"][0]["route"] == "/briefings?watchlist_id=wl-1&story_id=story-1"
    assert payload["citations"][0]["route_label"] == "Open briefing story"
    assert any(item["kind"] == "retrieval_hit" for item in payload["citations"])
    assert payload["evidence"]["story_cards"][0]["body"] == "Retry policy is now explicit."
    assert payload["fallback"]["status"] == "grounded"
    assert payload["fallback"]["actions"] == []


def test_retrieval_service_answer_returns_honest_fallback_when_briefing_is_missing(
    monkeypatch,
) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_load_watchlist_briefing_page", lambda **_: None)
    monkeypatch.setattr(
        service,
        "search",
        lambda **kwargs: {
            "query": kwargs["query"],
            "top_k": kwargs["top_k"],
            "filters": kwargs["filters"],
            "items": [],
        },
    )

    payload = service.answer(
        query="retry policy",
        watchlist_id="wl-missing",
        top_k=2,
        mode="keyword",
        filters={},
    )

    assert payload["context"]["briefing_available"] is False
    assert payload["citations"] == []
    assert payload["fallback"]["status"] == "briefing_unavailable"
    assert (
        payload["fallback"]["reason"]
        == "The requested watchlist does not have a briefing payload yet."
    )
    assert payload["fallback"]["actions"] == [
        {
            "kind": "open_briefing",
            "label": "Open watchlist briefing",
            "route": "/briefings?watchlist_id=wl-missing",
        }
    ]
    assert payload["answer"]["confidence"] == "limited"


def test_load_watchlist_briefing_handles_blank_and_trimmed_values(monkeypatch) -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    class _StubWatchlistsService:
        def __init__(self, db: Any) -> None:
            assert db is service.db

        def get_watchlist_briefing(self, *, watchlist_id: str) -> dict[str, Any]:
            return {"watchlist": {"id": watchlist_id}}

    monkeypatch.setattr(
        "apps.api.app.services.watchlists.WatchlistsService",
        _StubWatchlistsService,
    )

    assert service._load_watchlist_briefing(watchlist_id="   ") is None
    assert service._load_watchlist_briefing(watchlist_id=" wl-1 ") == {"watchlist": {"id": "wl-1"}}


def test_select_briefing_story_supports_suggested_and_first_story_fallbacks() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    suggested_story = {"story_id": "story-2", "headline": "Suggested story"}
    first_story = {"story_id": "story-1", "headline": "First story"}
    briefing = {
        "evidence": {
            "suggested_story_id": "story-2",
            "stories": [first_story, suggested_story],
        }
    }

    selected_story, basis = service._select_briefing_story(
        briefing=briefing,
        story_id=None,
        query="no match",
    )
    assert selected_story == suggested_story
    assert basis == "suggested_story_id"

    selected_story, basis = service._select_briefing_story(
        briefing={"evidence": {"stories": [first_story]}},
        story_id=None,
        query="still no match",
    )
    assert selected_story == first_story
    assert basis == "first_story"


def test_resolve_primary_job_id_prefers_story_then_briefing() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    assert (
        service._resolve_primary_job_id(
            briefing={"differences": {"latest_job_id": "job-2"}},
            story={"latest_run_job_id": "job-3"},
        )
        == "job-3"
    )
    assert (
        service._resolve_primary_job_id(
            briefing={"differences": {"latest_job_id": "job-2"}},
            story={},
        )
        == "job-2"
    )
    assert service._resolve_primary_job_id(briefing=None, story={}) is None


def test_build_answer_output_covers_hit_and_briefing_without_story_paths() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    payload = service._build_answer_output(
        query="retry policy",
        briefing=None,
        story=None,
        retrieval_items=[
            {
                "source": "digest",
                "platform": "youtube",
                "title": "Demo",
                "snippet": "Digest says retries are default now.",
            }
        ],
        changes={"story_focus_summary": None},
        fallback_status="limited",
    )
    assert payload["direct_answer"].startswith(
        'For "retry policy", the strongest grounded match comes from'
    )
    assert "Digest says retries are default now." in payload["summary"]
    assert "strongest grounded match" in str(payload["reason"])

    payload = service._build_answer_output(
        query="retry policy",
        briefing={"watchlist": {"name": "Retry policy"}},
        story=None,
        retrieval_items=[],
        changes={"story_focus_summary": None},
        fallback_status="limited",
    )
    assert 'does not yet surface a direct answer for "retry policy"' in payload["direct_answer"]
    assert "Retry policy" in str(payload["reason"])


def test_build_answer_changes_and_story_focus_summary_cover_remaining_branches() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    story = {
        "headline": "Retry Policy",
        "story_key": "topic:retry-policy",
        "source_count": 2,
        "run_count": 3,
        "matched_card_count": 4,
    }
    changes = service._build_answer_changes(
        briefing={
            "differences": {
                "latest_job_id": "job-2",
                "previous_job_id": "job-1",
                "added_topics": [],
                "removed_topics": ["legacy-retry"],
                "added_claim_kinds": [],
                "removed_claim_kinds": ["warning"],
                "new_story_keys": [],
                "removed_story_keys": ["topic:retry-policy"],
                "compare": {},
            }
        },
        story=story,
    )
    assert "Removed topics: legacy-retry." in changes["summary"]
    assert "Removed claim kinds: warning." in changes["summary"]
    assert "Removed story keys: topic:retry-policy." in changes["summary"]
    assert "stale context" in str(changes["story_focus_summary"])

    assert (
        service._build_story_focus_summary(
            story={
                "headline": "Retry Policy",
                "story_key": "topic:retry",
                "source_count": 0,
                "run_count": 1,
                "matched_card_count": 0,
            },
            new_story_keys=[],
            removed_story_keys=[],
            compare_excerpt="@@ diff @@",
        )
        == '"Retry Policy" remains the selected story focus, and the latest compare still shows movement around it.'
    )
    assert (
        service._build_story_focus_summary(
            story={
                "headline": "Retry Policy",
                "story_key": "topic:retry",
                "source_count": 3,
                "run_count": 1,
                "matched_card_count": 0,
            },
            new_story_keys=[],
            removed_story_keys=[],
            compare_excerpt=None,
        )
        == '"Retry Policy" remains the strongest story focus across 3 source families.'
    )
    assert (
        service._build_story_focus_summary(
            story={
                "headline": "Retry Policy",
                "story_key": "topic:retry",
                "source_count": 0,
                "run_count": 0,
                "matched_card_count": 0,
            },
            new_story_keys=[],
            removed_story_keys=[],
            compare_excerpt=None,
        )
        == '"Retry Policy" is the current story focus for this answer.'
    )


def test_build_answer_fallback_covers_limited_and_insufficient_paths() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    limited_with_hits = service._build_answer_fallback(
        watchlist_id="wl-1",
        story_id=None,
        briefing={"watchlist": {"id": "wl-1"}},
        story={"routes": {"briefing": "/briefings?watchlist_id=wl-1&story_id=story-1"}},
        retrieval_items=[{"job_id": "job-2"}],
        citations=[],
    )
    assert limited_with_hits["status"] == "limited"
    assert limited_with_hits["actions"][0]["kind"] == "open_story"
    assert limited_with_hits["actions"][1]["kind"] == "open_job"

    limited_without_hits = service._build_answer_fallback(
        watchlist_id="wl-1",
        story_id=None,
        briefing={"watchlist": {"id": "wl-1"}},
        story={"routes": {"briefing": "/briefings?watchlist_id=wl-1&story_id=story-1"}},
        retrieval_items=[],
        citations=[],
    )
    assert limited_without_hits["status"] == "limited"
    assert limited_without_hits["actions"][1]["kind"] == "open_search"

    insufficient = service._build_answer_fallback(
        watchlist_id=None,
        story_id=None,
        briefing=None,
        story=None,
        retrieval_items=[],
        citations=[],
    )
    assert insufficient["status"] == "insufficient_evidence"
    assert insufficient["actions"] == [
        {
            "kind": "open_briefing",
            "label": "Open briefings",
            "route": "/briefings",
        }
    ]


def test_render_knowledge_cards_text_and_normalize_filters_cover_guard_branches(
    tmp_path: Path,
) -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    assert service._render_knowledge_cards_text({"not": "a-list"}) == json.dumps(
        {"not": "a-list"}, ensure_ascii=False
    )
    rendered = service._render_knowledge_cards_text(
        [
            "skip-me",
            {
                "card_type": "claim",
                "title": "Retry baseline",
                "body": "Retries are now the default path.",
                "source_section": "digest",
                "metadata": {
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "claim_kind": "recommendation",
                    "confidence_label": "high",
                },
            },
        ]
    )
    assert "topic_key:retry-policy" in rendered
    assert "claim_kind:recommendation" in rendered

    assert service._normalize_filters(None) == {}
    assert service._normalize_filters(
        {"unknown": "x", "platform": " youtube ", "job_id": None}
    ) == {"platform": "youtube"}

    artifact_root = tmp_path / "artifacts"
    assert service._iter_artifact_texts(str(artifact_root)) == []
    artifact_root.mkdir(parents=True, exist_ok=True)
    bad_json = artifact_root / "meta.json"
    bad_json.write_text("{not-json}", encoding="utf-8")
    assert service._read_text(bad_json) == "{not-json}"


def test_retrieval_service_answer_page_returns_server_owned_payload(monkeypatch) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    briefing_payload = {
        "watchlist": {"id": "wl-1", "name": "Retry policy"},
        "summary": {
            "overview": "Retry policy currently converges across recent sources.",
            "primary_story_headline": "Retry Policy",
            "signals": [
                {
                    "reason": "The newest runs keep repeating the retry baseline.",
                }
            ],
        },
        "differences": {
            "compare": {"diff_excerpt": "@@ latest diff @@"},
        },
        "evidence": {
            "suggested_story_id": "story-1",
            "stories": [
                {
                    "story_id": "story-1",
                    "story_key": "topic:retry-policy",
                    "headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry policy",
                    "source_count": 2,
                    "run_count": 2,
                    "matched_card_count": 2,
                    "platforms": ["youtube"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/retry"],
                    "latest_run_job_id": "job-2",
                    "evidence_cards": [
                        {
                            "card_id": "card-1",
                            "job_id": "job-2",
                            "platform": "youtube",
                            "source_url": "https://example.com/retry",
                            "card_title": "Retry policy card",
                            "card_body": "Retry policy is now explicit.",
                            "source_section": "summary",
                        }
                    ],
                    "routes": {
                        "watchlist_trend": "/trends?watchlist_id=wl-1",
                        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                        "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                        "job_compare": "/jobs?job_id=job-2",
                        "job_bundle": "/api/v1/jobs/job-2/bundle",
                        "job_knowledge_cards": "/knowledge?job_id=job-2",
                    },
                }
            ],
            "featured_runs": [],
        },
    }
    answer_contract = {
        "query": "retry policy",
        "context": {
            "watchlist_id": "wl-1",
            "watchlist_name": "Retry policy",
            "story_id": "story-1",
            "selected_story_id": "story-1",
            "story_headline": "Retry Policy",
            "topic_key": "retry-policy",
            "topic_label": "Retry policy",
            "selection_basis": "requested_story_id",
            "mode": "keyword",
            "filters": {"job_id": "job-2"},
            "briefing_available": True,
        },
        "selected_story": {
            "story_id": "story-1",
            "story_key": "topic:retry-policy",
            "headline": "Retry Policy",
            "topic_key": "retry-policy",
            "topic_label": "Retry policy",
            "source_count": 2,
            "run_count": 2,
            "matched_card_count": 2,
            "platforms": ["youtube"],
            "claim_kinds": ["recommendation"],
            "source_urls": ["https://example.com/retry"],
            "latest_run_job_id": "job-2",
            "routes": {
                "watchlist_trend": "/trends?watchlist_id=wl-1",
                "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                "job_compare": "/jobs?job_id=job-2",
                "job_bundle": "/api/v1/jobs/job-2/bundle",
                "job_knowledge_cards": "/knowledge?job_id=job-2",
            },
        },
        "answer": {
            "direct_answer": 'For "retry policy", the current briefing most strongly points to "Retry Policy".',
            "summary": "Retry policy currently converges across recent sources.",
            "reason": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
            "confidence": "grounded",
        },
        "changes": {
            "summary": "Added topics: retry-policy.",
            "story_focus_summary": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
            "latest_job_id": "job-2",
            "previous_job_id": "job-1",
            "added_topics": ["retry-policy"],
            "removed_topics": [],
            "added_claim_kinds": ["recommendation"],
            "removed_claim_kinds": [],
            "new_story_keys": ["topic:retry-policy"],
            "removed_story_keys": [],
            "compare_excerpt": "@@ latest diff @@",
            "compare_route": "/jobs?job_id=job-2",
            "has_previous": True,
        },
        "citations": [
            {
                "kind": "briefing_story",
                "label": "Retry Policy",
                "snippet": "Supported across 2 source families.",
                "source_url": None,
                "job_id": "job-2",
                "route": "/briefings?watchlist_id=wl-1&story_id=story-1",
                "route_label": "Open briefing story",
            }
        ],
        "evidence": {
            "briefing_overview": "Retry policy currently converges across recent sources.",
            "selected_story_id": "story-1",
            "selected_story_headline": "Retry Policy",
            "latest_job_id": "job-2",
            "citation_count": 1,
            "retrieval_hit_count": 1,
            "retrieval_items": [
                {
                    "job_id": "job-2",
                    "video_id": "video-2",
                    "platform": "youtube",
                    "video_uid": "abc123",
                    "source_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Demo",
                    "kind": "video_digest_v1",
                    "mode": "full",
                    "source": "knowledge_cards",
                    "snippet": "Retry policy evidence",
                    "score": 2.2,
                }
            ],
            "story_cards": [
                {
                    "card_id": "card-1",
                    "job_id": "job-2",
                    "platform": "youtube",
                    "source_url": "https://example.com/retry",
                    "title": "Retry policy card",
                    "body": "Retry policy is now explicit.",
                    "source_section": "summary",
                }
            ],
        },
        "fallback": {
            "status": "grounded",
            "reason": None,
            "suggested_next_step": None,
            "actions": [],
        },
    }

    briefing_payload["context"] = {
        "watchlist_id": "wl-1",
        "watchlist_name": "Retry policy",
        "story_id": "story-1",
        "selected_story_id": "story-1",
        "story_headline": "Retry Policy",
        "topic_key": "retry-policy",
        "topic_label": "Retry policy",
        "selection_basis": "requested_story_id",
        "question_seed": "retry policy",
    }
    briefing_payload["selected_story"] = briefing_payload["evidence"]["stories"][0]
    briefing_payload["routes"] = {
        "watchlist_trend": "/trends?watchlist_id=wl-1",
        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
        "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
        "job_compare": "/jobs?job_id=job-2",
        "job_bundle": "/api/v1/jobs/job-2/bundle",
        "job_knowledge_cards": "/knowledge?job_id=job-2",
    }

    monkeypatch.setattr(service, "_load_watchlist_briefing_page", lambda **_: briefing_payload)
    monkeypatch.setattr(service, "answer", lambda **_: answer_contract)

    payload = service.answer_page(
        query="retry policy",
        watchlist_id="wl-1",
        story_id="story-1",
        top_k=4,
        mode="keyword",
        filters={},
    )

    assert payload["question"] == "retry policy"
    assert payload["context"]["watchlist_name"] == "Retry policy"
    assert payload["context"]["selection_basis"] == "requested_story_id"
    assert payload["answer_state"] == "briefing_grounded"
    assert payload["story_page"]["selected_story"]["story_id"] == "story-1"
    assert payload["retrieval"]["items"][0]["source"] == "knowledge_cards"
    assert payload["citations"][0]["route_label"] == "Open briefing story"
    assert payload["fallback_actions"] == []


def test_retrieval_service_answer_page_without_context_uses_raw_retrieval(monkeypatch) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(service, "_load_watchlist_briefing_page", lambda **_: None)
    monkeypatch.setattr(
        service,
        "search",
        lambda **kwargs: {
            "query": kwargs["query"],
            "top_k": kwargs["top_k"],
            "filters": kwargs["filters"],
            "items": [
                {
                    "job_id": "job-9",
                    "video_id": "video-9",
                    "platform": "rss",
                    "video_uid": "rss-9",
                    "source_url": "https://example.com/raw",
                    "title": "Raw retrieval hit",
                    "kind": "video_digest_v1",
                    "mode": "full",
                    "source": "digest",
                    "snippet": "Raw retrieval still found relevant evidence.",
                    "score": 1.1,
                }
            ],
        },
    )

    payload = service.answer_page(
        query="retry policy",
        top_k=5,
        mode="keyword",
        filters={"platform": "rss"},
    )

    assert payload["answer_state"] == "missing_context"
    assert payload["context"]["watchlist_id"] is None
    assert payload["context"]["briefing_available"] is False
    assert payload["retrieval"]["items"][0]["job_id"] == "job-9"
    assert payload["answer_headline"] is None
    assert payload["fallback_reason"] is None
    assert payload["fallback_actions"] == []


def test_retrieval_service_answer_page_marks_story_not_found_as_no_confident(monkeypatch) -> None:
    db = _FakeDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    briefing_payload = {
        "watchlist": {"id": "wl-1", "name": "Retry policy"},
        "summary": {
            "overview": "Retry policy currently converges across recent sources.",
            "primary_story_headline": "Retry Policy",
            "signals": [{"reason": "Latest runs still point at retry-policy."}],
        },
        "differences": {"compare": {"diff_excerpt": "@@ latest diff @@"}},
        "evidence": {
            "suggested_story_id": "story-1",
            "stories": [
                {
                    "story_id": "story-1",
                    "story_key": "topic:retry-policy",
                    "headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry policy",
                    "source_count": 2,
                    "run_count": 2,
                    "matched_card_count": 2,
                    "platforms": ["youtube"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/retry"],
                    "latest_run_job_id": "job-2",
                    "evidence_cards": [],
                    "routes": {
                        "watchlist_trend": "/trends?watchlist_id=wl-1",
                        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                        "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                        "job_compare": "/jobs?job_id=job-2",
                        "job_bundle": "/api/v1/jobs/job-2/bundle",
                        "job_knowledge_cards": "/knowledge?job_id=job-2",
                    },
                }
            ],
            "featured_runs": [],
        },
    }

    briefing_payload["context"] = {
        "watchlist_id": "wl-1",
        "watchlist_name": "Retry policy",
        "story_id": "story-missing",
        "selected_story_id": "story-1",
        "story_headline": "Retry Policy",
        "topic_key": "retry-policy",
        "topic_label": "Retry policy",
        "selection_basis": "suggested_story_id",
        "question_seed": "retry policy",
    }
    briefing_payload["selected_story"] = briefing_payload["evidence"]["stories"][0]
    briefing_payload["routes"] = {
        "watchlist_trend": "/trends?watchlist_id=wl-1",
        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
        "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
        "job_compare": "/jobs?job_id=job-2",
        "job_bundle": "/api/v1/jobs/job-2/bundle",
        "job_knowledge_cards": "/knowledge?job_id=job-2",
    }

    monkeypatch.setattr(service, "_load_watchlist_briefing_page", lambda **_: briefing_payload)
    monkeypatch.setattr(
        service,
        "answer",
        lambda **_: {
            "query": "retry policy",
            "context": {
                "watchlist_id": "wl-1",
                "watchlist_name": "Retry policy",
                "story_id": "story-missing",
                "selected_story_id": None,
                "story_headline": None,
                "topic_key": None,
                "topic_label": None,
                "selection_basis": "none",
                "mode": "keyword",
                "filters": {},
                "briefing_available": True,
            },
            "selected_story": None,
            "answer": {
                "direct_answer": 'There is not enough grounded briefing evidence to answer "retry policy" yet.',
                "summary": "Retry policy currently converges across recent sources.",
                "reason": None,
                "confidence": "limited",
            },
            "changes": {
                "summary": "No watchlist briefing changes are available for this answer.",
                "story_focus_summary": None,
                "latest_job_id": None,
                "previous_job_id": None,
                "added_topics": [],
                "removed_topics": [],
                "added_claim_kinds": [],
                "removed_claim_kinds": [],
                "new_story_keys": [],
                "removed_story_keys": [],
                "compare_excerpt": None,
                "compare_route": None,
                "has_previous": False,
            },
            "citations": [],
            "evidence": {
                "briefing_overview": "Retry policy currently converges across recent sources.",
                "selected_story_id": None,
                "selected_story_headline": None,
                "latest_job_id": None,
                "citation_count": 0,
                "retrieval_hit_count": 0,
                "retrieval_items": [],
                "story_cards": [],
            },
            "fallback": {
                "status": "story_not_found",
                "reason": "The requested story_id was not found inside the current briefing context.",
                "suggested_next_step": "Use the suggested story from the current briefing or pick a visible story id.",
                "actions": [
                    {
                        "kind": "open_briefing",
                        "label": "Open watchlist briefing",
                        "route": "/briefings?watchlist_id=wl-1",
                    }
                ],
            },
        },
    )

    payload = service.answer_page(
        query="retry policy",
        watchlist_id="wl-1",
        story_id="story-missing",
        top_k=4,
        mode="keyword",
        filters={},
    )

    assert payload["answer_state"] == "no_confident_answer"
    assert payload["context"]["story_id"] == "story-1"
    assert payload["context"]["selected_story_id"] == "story-1"
    assert payload["context"]["selection_basis"] == "none"
    assert payload["fallback_reason"] == (
        "The requested story_id was not found inside the current briefing context."
    )
    assert payload["fallback_actions"] == [
        {
            "kind": "open_briefing",
            "label": "Open watchlist briefing",
            "route": "/briefings?watchlist_id=wl-1",
        }
    ]


def test_retrieval_service_search_hits_three_sources(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "digest.md").write_text("alpha found in digest", encoding="utf-8")
    (artifact_root / "transcript.txt").write_text("alpha found in transcript", encoding="utf-8")
    (artifact_root / "outline.json").write_text(
        '{"summary":"alpha found in outline"}', encoding="utf-8"
    )

    db = _FakeDB(
        [
            {
                "job_id": uuid.uuid4(),
                "video_id": uuid.uuid4(),
                "kind": "video_digest_v1",
                "mode": "full",
                "artifact_root": str(artifact_root),
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
            }
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]

    payload = service.search(query="alpha", top_k=3, filters={"platform": "youtube"})
    sources = {item["source"] for item in payload["items"]}

    assert len(payload["items"]) == 3
    assert sources == {"digest", "transcript", "outline"}


def test_retrieval_service_keyword_prioritizes_structured_knowledge_cards(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "digest.md").write_text(
        "general digest about workflows and operators", encoding="utf-8"
    )
    (artifact_root / "knowledge_cards.json").write_text(
        json.dumps(
            [
                {
                    "card_type": "takeaway",
                    "title": "Workflow reliability",
                    "body": "Operator teams should prioritize workflow reliability checks.",
                    "source_section": "highlights",
                    "order_index": 0,
                    "metadata": {
                        "topic_key": "workflow-reliability",
                        "topic_label": "Workflow / Reliability",
                        "claim_kind": "takeaway",
                        "confidence_label": "high",
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    db = _FakeDB(
        [
            {
                "job_id": uuid.uuid4(),
                "video_id": uuid.uuid4(),
                "kind": "video_digest_v1",
                "mode": "full",
                "artifact_root": str(artifact_root),
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
            }
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]

    payload = service.search(query="workflow-reliability", top_k=3, filters={})

    assert payload["items"][0]["source"] == "knowledge_cards"
    assert "Workflow / Reliability" in payload["items"][0]["snippet"]


def test_retrieval_service_prioritizes_knowledge_cards_in_keyword_mode(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "digest.md").write_text("timeout fallback", encoding="utf-8")
    (artifact_root / "knowledge_cards.json").write_text(
        json.dumps(
            [
                {
                    "card_type": "claim",
                    "title": "Claim",
                    "body": "Timeout fallback needs retry policy.",
                    "source_section": "highlights",
                    "metadata": {
                        "topic_key": "timeout-fallback",
                        "topic_label": "Timeout fallback",
                        "claim_id": "claim-1",
                        "claim_kind": "takeaway",
                        "confidence_label": "high",
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    db = _FakeDB(
        [
            {
                "job_id": uuid.uuid4(),
                "video_id": uuid.uuid4(),
                "kind": "video_digest_v1",
                "mode": "full",
                "artifact_root": str(artifact_root),
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Demo",
            }
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]

    payload = service.search(query="timeout fallback", top_k=2, filters={"platform": "youtube"})

    assert payload["items"][0]["source"] == "knowledge_cards"
    assert "claim_kind:takeaway" in payload["items"][0]["snippet"]


def test_match_knowledge_cards_structured_payload_and_semantic_fallbacks(monkeypatch) -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    row = {
        "job_id": "job-1",
        "video_id": "video-1",
        "kind": "video_digest_v1",
        "mode": "full",
        "platform": "youtube",
        "video_uid": "abc123",
        "source_url": "https://www.youtube.com/watch?v=abc123",
        "title": "Demo",
    }
    content = json.dumps(
        [
            "skip-me",
            {
                "title": "Retry Policy",
                "body": "Retry policy guidance is now explicit.",
                "source_section": "summary",
                "metadata": {
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "claim_kind": "recommendation",
                    "confidence_label": "high",
                },
            },
            {
                "title": "Other topic",
                "body": "This card does not match.",
                "source_section": "summary",
                "metadata": {"topic_key": "delivery"},
            },
        ]
    )

    hits = service._match_knowledge_cards(row=row, content=content, query="retry-policy")

    assert len(hits) == 1
    assert hits[0]["source"] == "knowledge_cards"
    assert "Topic: Retry Policy" in hits[0]["snippet"]
    assert "claim_kind:recommendation" in hits[0]["snippet"]
    assert "topic_key:retry-policy" in hits[0]["snippet"]

    monkeypatch.setattr(
        service,
        "_build_query_embedding",
        lambda _query: (_ for _ in ()).throw(
            ApiServiceError(
                detail="retrieval embedding request failed",
                error_code="RETRIEVAL_EMBEDDING_REQUEST_FAILED",
            )
        ),
    )
    assert service._search_semantic(query="retry", top_k=3, filters={}, strict=False) == []

    monkeypatch.setattr(service, "_build_query_embedding", lambda _query: None)
    assert service._search_semantic(query="retry", top_k=3, filters={}, strict=False) == []


def test_normalize_mode_invalid_defaults_to_keyword() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    assert service._normalize_mode("invalid") == "keyword"
    assert service._normalize_mode(" HYBRID ") == "hybrid"


def test_search_keyword_skips_invalid_artifact_roots() -> None:
    db = _FakeDB(
        [
            {"artifact_root": None},
            {"artifact_root": "   "},
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]
    assert service._search_keyword(query="x", top_k=5, filters={}) == []


def test_search_semantic_rolls_back_on_db_error() -> None:
    db = _ErrorDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    service._build_query_embedding = lambda query: [0.1, 0.2]  # type: ignore[method-assign]

    assert service._search_semantic(query="x", top_k=3, filters={}) == []
    assert db.rollback_calls == 1


def test_search_semantic_strict_mode_raises_on_db_error(monkeypatch) -> None:
    db = _ErrorDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_build_query_embedding", lambda _query: [0.1, 0.2])

    with pytest.raises(ApiServiceError, match="semantic query failed"):
        service._search_semantic(query="x", top_k=3, filters={}, strict=True)

    assert db.rollback_calls == 1


def test_search_semantic_filters_invalid_rows(monkeypatch) -> None:
    db = _FakeDB(
        [
            {
                "job_id": "job-1",
                "video_id": "video-1",
                "kind": "video_digest_v1",
                "mode": "full",
                "platform": "youtube",
                "video_uid": "abc123",
                "source_url": "https://x",
                "title": "Demo",
                "source": "unknown",
                "snippet": "  alpha\n beta  ",
                "score": 0.7,
            },
            {
                "job_id": "job-2",
                "video_id": "video-2",
                "kind": "video_digest_v1",
                "mode": "full",
                "platform": "youtube",
                "video_uid": "def456",
                "source_url": "https://y",
                "title": "Demo2",
                "source": "outline",
                "snippet": "",
                "score": 0.8,
            },
            {
                "job_id": "job-3",
                "video_id": "video-3",
                "kind": "video_digest_v1",
                "mode": "full",
                "platform": "youtube",
                "video_uid": "ghi789",
                "source_url": "https://z",
                "title": "Demo3",
                "source": "transcript",
                "snippet": "ok",
                "score": "bad",
            },
        ]
    )
    service = RetrievalService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_build_query_embedding", lambda query: [0.1, 0.2])

    hits = service._search_semantic(query="x", top_k=5, filters={})

    assert len(hits) == 1
    assert hits[0]["source"] == "transcript"
    assert hits[0]["snippet"] == "alpha beta"


def test_build_query_embedding_returns_none_for_blank_query_or_no_key(monkeypatch) -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    assert service._build_query_embedding("   ") is None

    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert service._build_query_embedding("hello") is None


def test_build_query_embedding_handles_import_error(monkeypatch) -> None:
    retrieval_module = __import__("apps.api.app.services.retrieval", fromlist=["RetrievalService"])
    retrieval_module = __import__("importlib").reload(retrieval_module)
    service = retrieval_module.RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    monkeypatch.setattr(
        retrieval_module.Settings,
        "from_env",
        lambda: SimpleNamespace(
            gemini_api_key="key",
            llm_provider="gemini",
            gemini_embedding_model="x",
            api_retrieval_embedding_timeout_seconds=1.0,
        ),
    )

    def _fake_import(name: str):
        if name in {"google.genai", "google.genai.types"}:
            raise ImportError(name)
        return importlib.import_module(name)

    monkeypatch.setattr(retrieval_module.importlib, "import_module", _fake_import)

    with pytest.raises(retrieval_module.ApiServiceError, match="dependency not available"):
        service._build_query_embedding("hello")


def test_build_query_embedding_timeout_raises_api_timeout(monkeypatch) -> None:
    retrieval_module = __import__(
        "apps.api.app.services.retrieval",
        fromlist=["RetrievalService", "Settings", "ApiTimeoutError"],
    )
    retrieval_module = __import__("importlib").reload(retrieval_module)
    service = retrieval_module.RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    monkeypatch.setattr(
        retrieval_module.Settings,
        "from_env",
        lambda: types.SimpleNamespace(
            gemini_api_key="key",
            gemini_embedding_model="gemini-embedding-001",
            api_retrieval_embedding_timeout_seconds=0.5,
        ),
    )

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.models = types.SimpleNamespace(
                embed_content=lambda **kwargs: {"values": [0.1, 0.2]}
            )

    fake_types_module = types.ModuleType("google.genai.types")

    class _EmbedContentConfig:
        def __init__(self, output_dimensionality: int):
            self.output_dimensionality = output_dimensionality

    fake_types_module.EmbedContentConfig = _EmbedContentConfig
    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = _FakeClient
    fake_genai_module.types = fake_types_module
    fake_genai_module.__path__ = []

    def _fake_import(name: str):
        if name == "google.genai":
            return fake_genai_module
        if name == "google.genai.types":
            return fake_types_module
        raise ImportError(name)

    monkeypatch.setattr(retrieval_module.importlib, "import_module", _fake_import)

    class _Future:
        def result(self, timeout: float):
            del timeout
            raise concurrent.futures.TimeoutError

    class _Executor:
        def __init__(self, max_workers: int):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn):
            del fn
            return _Future()

    monkeypatch.setattr(retrieval_module.concurrent.futures, "ThreadPoolExecutor", _Executor)

    with pytest.raises(retrieval_module.ApiTimeoutError, match="retrieval embedding timed out"):
        service._build_query_embedding("hello")


def test_build_query_embedding_returns_none_on_runtime_exception(monkeypatch) -> None:
    retrieval_module = __import__("apps.api.app.services.retrieval", fromlist=["RetrievalService"])
    retrieval_module = __import__("importlib").reload(retrieval_module)
    service = retrieval_module.RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    monkeypatch.setattr(
        retrieval_module.Settings,
        "from_env",
        lambda: types.SimpleNamespace(
            gemini_api_key="key",
            llm_provider="gemini",
            gemini_embedding_model="gemini-embedding-001",
            api_retrieval_embedding_timeout_seconds=0.5,
        ),
    )

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.models = types.SimpleNamespace(
                embed_content=lambda **kwargs: {"values": [0.1, 0.2]}
            )

    fake_types_module = types.ModuleType("google.genai.types")

    class _EmbedContentConfig:
        def __init__(self, output_dimensionality: int):
            self.output_dimensionality = output_dimensionality

    fake_types_module.EmbedContentConfig = _EmbedContentConfig
    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = _FakeClient
    fake_genai_module.types = fake_types_module
    fake_genai_module.__path__ = []

    def _fake_import(name: str):
        if name == "google.genai":
            return fake_genai_module
        if name == "google.genai.types":
            return fake_types_module
        raise ImportError(name)

    monkeypatch.setattr(retrieval_module.importlib, "import_module", _fake_import)

    class _Future:
        def result(self, timeout: float):
            del timeout
            raise RuntimeError("bad")

    class _Executor:
        def __init__(self, max_workers: int):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn):
            del fn
            return _Future()

    monkeypatch.setattr(retrieval_module.concurrent.futures, "ThreadPoolExecutor", _Executor)
    with pytest.raises(
        retrieval_module.ApiServiceError, match="retrieval embedding request failed"
    ):
        service._build_query_embedding("hello")


def test_search_semantic_raises_when_embedding_fails_in_strict_mode(monkeypatch) -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "_build_query_embedding",
        lambda _query: (_ for _ in ()).throw(
            ApiServiceError(
                detail="retrieval embedding request failed",
                error_code="RETRIEVAL_EMBEDDING_REQUEST_FAILED",
            )
        ),
    )

    with pytest.raises(ApiServiceError, match="embedding request failed"):
        service.search(query="timeout", top_k=3, mode="semantic", filters={"platform": "youtube"})


def test_extract_embedding_values_and_extract_values_paths() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]

    response = types.SimpleNamespace(
        embeddings=[types.SimpleNamespace(embedding=types.SimpleNamespace(values=[1, 2, 3]))]
    )
    assert service._extract_embedding_values(response) == [1.0, 2.0, 3.0]

    assert service._extract_values(types.SimpleNamespace(values=[4, 5])) == [4.0, 5.0]
    assert service._extract_values({"values": [6, 7]}) == [6.0, 7.0]
    assert service._extract_values({"embedding": {"values": [8, 9]}}) == [8.0, 9.0]
    assert service._extract_values({"embedding": {"values": []}}) is None


def test_to_vector_literal_and_empty_vector() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    assert service._to_vector_literal([1, 2.5]) == "[1.0000000000,2.5000000000]"
    with pytest.raises(ValueError, match="empty"):
        service._to_vector_literal([])


def test_list_candidate_jobs_rolls_back_on_db_error() -> None:
    db = _ErrorDB([])
    service = RetrievalService(db)  # type: ignore[arg-type]
    rows = service._list_candidate_jobs(top_k=10, filters={})
    assert rows == []
    assert db.rollback_calls == 1


def test_iter_artifact_texts_and_read_text_json_paths(tmp_path: Path) -> None:
    root = tmp_path / "artifact"
    root.mkdir(parents=True, exist_ok=True)
    (root / "digest.md").write_text("digest", encoding="utf-8")
    (root / "outline.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    (root / "comments.json").write_text("{bad-json", encoding="utf-8")
    (root / "knowledge_cards.json").write_text(
        json.dumps(
            [
                {
                    "card_type": "topic",
                    "title": "Topic",
                    "body": "Retry policy",
                    "source_section": "topics",
                    "metadata": {"topic_key": "retry-policy", "topic_label": "Retry policy"},
                }
            ]
        ),
        encoding="utf-8",
    )

    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    payload = dict(service._iter_artifact_texts(str(root)))

    assert payload["digest"] == "digest"
    assert payload["outline"] == '{"a": 1}'
    assert payload["comments"] == "{bad-json"
    assert "topic_key:retry-policy" in payload["knowledge_cards"]


def test_match_content_branches() -> None:
    service = RetrievalService(_FakeDB([]))  # type: ignore[arg-type]
    assert service._match_content(content="", query="x") is None
    assert service._match_content(content="hello", query="zzz") is None

    matched = service._match_content(content="alpha beta alpha", query="alpha")
    assert matched is not None
    score, snippet = matched
    assert score > 0
    assert "alpha" in snippet
