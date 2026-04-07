from __future__ import annotations

import concurrent.futures
import importlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from integrations.providers.gemini import build_gemini_client, load_gemini_sdk

from ..config import Settings
from ..errors import ApiServiceError, ApiTimeoutError
from .story_read_model import build_briefing_page_payload, select_story_from_briefing

_ALLOWED_FILTERS = {
    "platform",
    "job_id",
    "video_id",
    "video_uid",
    "kind",
    "mode",
}

_SEARCH_FILES = (
    ("digest", "digest.md"),
    ("transcript", "transcript.txt"),
    ("outline", "outline.json"),
    ("knowledge_cards", "knowledge_cards.json"),
    ("comments", "comments.json"),
    ("meta", "meta.json"),
)

_RETRIEVAL_MODES = {"keyword", "semantic", "hybrid"}
_EMBEDDING_DIMENSION = 768
_KEYWORD_SOURCE_SCORE_BOOSTS = {
    "knowledge_cards": 1.5,
    "digest": 0.25,
    "outline": 0.15,
    "comments": 0.05,
    "meta": 0.0,
    "transcript": 0.0,
}
_QUERY_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
RetrievalMode = Literal["keyword", "semantic", "hybrid"]
logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def answer(
        self,
        *,
        query: str,
        watchlist_id: str | None = None,
        story_id: str | None = None,
        top_k: int,
        filters: dict[str, Any] | None = None,
        mode: RetrievalMode = "keyword",
    ) -> dict[str, Any]:
        normalized_query = query.strip()
        normalized_watchlist_id = str(watchlist_id or "").strip() or None
        normalized_story_id = str(story_id or "").strip() or None
        normalized_filters = self._normalize_filters(filters)
        normalized_mode = self._normalize_mode(mode)
        briefing = (
            self._ensure_story_page_payload(
                self._load_watchlist_briefing_page(
                    watchlist_id=normalized_watchlist_id,
                    story_id=normalized_story_id,
                    query=normalized_query,
                ),
                watchlist_id=normalized_watchlist_id,
                story_id=normalized_story_id,
                query=normalized_query,
            )
            if normalized_watchlist_id
            else None
        )
        briefing_context = self._extract_briefing_context(briefing)
        briefing_payload = self._extract_briefing_payload(briefing)
        selected_story = self._extract_selected_story(
            briefing,
            briefing_payload=briefing_payload,
            story_id=normalized_story_id,
            query=normalized_query,
        )
        _, derived_selection_basis = self._select_briefing_story(
            briefing=briefing_payload,
            story_id=normalized_story_id,
            query=normalized_query,
        )
        selection_basis = (
            str(
                briefing_context.get("selection_basis") or derived_selection_basis or "none"
            ).strip()
            or "none"
        )
        selected_story_dict = selected_story if isinstance(selected_story, dict) else {}

        retrieval_filters = dict(normalized_filters)
        primary_job_id = self._resolve_primary_job_id(
            briefing=briefing_payload,
            story=selected_story,
        )
        if primary_job_id and "job_id" not in retrieval_filters:
            retrieval_filters["job_id"] = primary_job_id

        retrieval_payload = self.search(
            query=normalized_query,
            top_k=top_k,
            filters=retrieval_filters,
            mode=normalized_mode,
        )
        retrieval_items = list(retrieval_payload.get("items") or [])
        changes = self._build_answer_changes(briefing=briefing_payload, story=selected_story)
        citations = self._build_answer_citations(
            briefing=briefing_payload,
            story=selected_story,
            retrieval_items=retrieval_items,
            changes=changes,
        )
        fallback = self._build_answer_fallback(
            watchlist_id=watchlist_id,
            story_id=story_id,
            briefing=briefing_payload,
            story=selected_story,
            retrieval_items=retrieval_items,
            citations=citations,
        )

        return {
            "query": normalized_query,
            "context": {
                "watchlist_id": normalized_watchlist_id,
                "watchlist_name": str(
                    briefing_context.get("watchlist_name")
                    or self._watchlist_name(briefing_payload)
                    or ""
                ).strip()
                or None,
                "story_id": str(
                    briefing_context.get("selected_story_id") or normalized_story_id or ""
                ).strip()
                or None,
                "selected_story_id": str(
                    briefing_context.get("selected_story_id")
                    or selected_story_dict.get("story_id")
                    or ""
                ).strip()
                or None,
                "story_headline": str(
                    briefing_context.get("story_headline")
                    or selected_story_dict.get("headline")
                    or ""
                ).strip()
                or None
                if selected_story_dict or briefing_context
                else None,
                "topic_key": str(
                    briefing_context.get("topic_key") or selected_story_dict.get("topic_key") or ""
                ).strip()
                or None
                if selected_story_dict or briefing_context
                else None,
                "topic_label": str(
                    briefing_context.get("topic_label")
                    or selected_story_dict.get("topic_label")
                    or ""
                ).strip()
                or None
                if selected_story_dict or briefing_context
                else None,
                "selection_basis": selection_basis,
                "mode": normalized_mode,
                "filters": retrieval_filters,
                "briefing_available": briefing is not None,
            },
            "selected_story": self._serialize_selected_story(story=selected_story),
            "answer": self._build_answer_output(
                query=normalized_query,
                briefing=briefing_payload,
                story=selected_story,
                retrieval_items=retrieval_items,
                changes=changes,
                fallback_status=str(fallback.get("status") or "limited"),
            ),
            "changes": changes,
            "citations": citations,
            "evidence": self._build_answer_evidence(
                briefing=briefing_payload,
                story=selected_story,
                retrieval_items=retrieval_items,
                citation_count=len(citations),
            ),
            "fallback": fallback,
        }

    def answer_page(
        self,
        *,
        query: str | None = None,
        watchlist_id: str | None = None,
        story_id: str | None = None,
        topic_key: str | None = None,
        top_k: int,
        filters: dict[str, Any] | None = None,
        mode: RetrievalMode = "keyword",
    ) -> dict[str, Any]:
        normalized_query = str(query or "").strip()
        normalized_watchlist_id = str(watchlist_id or "").strip() or None
        normalized_story_id = str(story_id or "").strip() or None
        normalized_topic_key = str(topic_key or "").strip() or None
        normalized_mode = self._normalize_mode(mode)
        normalized_top_k = max(1, min(top_k, 20))
        normalized_filters = self._normalize_filters(filters)

        briefing_page = (
            self._ensure_story_page_payload(
                self._load_watchlist_briefing_page(
                    watchlist_id=normalized_watchlist_id,
                    story_id=normalized_story_id,
                    query=normalized_query or normalized_topic_key or "",
                ),
                watchlist_id=normalized_watchlist_id,
                story_id=normalized_story_id,
                query=normalized_query or normalized_topic_key or "",
            )
            if normalized_watchlist_id
            else None
        )
        story_page = briefing_page if isinstance(briefing_page, dict) else None
        briefing = self._extract_briefing_payload(story_page)
        selected_story = self._extract_selected_story(
            story_page,
            briefing_payload=briefing,
            story_id=normalized_story_id,
            query=normalized_query or normalized_topic_key or "",
        )
        briefing_page_context = self._extract_briefing_context(story_page)
        _, derived_selection_basis = self._select_briefing_story(
            briefing=briefing,
            story_id=normalized_story_id,
            query=normalized_query or normalized_topic_key or "",
        )
        selection_basis = (
            str(
                briefing_page_context.get("selection_basis") or derived_selection_basis or "none"
            ).strip()
            or "none"
        )
        answer_contract = (
            self.answer(
                query=normalized_query,
                watchlist_id=normalized_watchlist_id,
                story_id=normalized_story_id,
                top_k=normalized_top_k,
                filters=normalized_filters,
                mode=normalized_mode,
            )
            if normalized_query and normalized_watchlist_id
            else None
        )
        raw_retrieval = (
            self.search(
                query=normalized_query,
                top_k=normalized_top_k,
                filters=normalized_filters,
                mode=normalized_mode,
            )
            if normalized_query and not normalized_watchlist_id
            else None
        )

        selected_story_payload = (
            answer_contract.get("selected_story")
            if isinstance(answer_contract, dict)
            and isinstance(answer_contract.get("selected_story"), dict)
            else self._serialize_selected_story(story=selected_story)
        )
        retrieval = (
            {
                "query": str(answer_contract.get("query") or normalized_query),
                "top_k": normalized_top_k,
                "filters": (
                    answer_contract.get("context", {}).get("filters")
                    if isinstance(answer_contract.get("context"), dict)
                    else normalized_filters
                ),
                "items": (
                    answer_contract.get("evidence", {}).get("retrieval_items") or []
                    if isinstance(answer_contract.get("evidence"), dict)
                    else []
                ),
            }
            if isinstance(answer_contract, dict)
            else raw_retrieval
        )
        retrieval_items = list(retrieval.get("items") or []) if isinstance(retrieval, dict) else []
        fallback = (
            answer_contract.get("fallback")
            if isinstance(answer_contract, dict)
            and isinstance(answer_contract.get("fallback"), dict)
            else {}
        )
        fallback_status = str(fallback.get("status") or "").strip()
        retrieval_hit_count = len(retrieval_items)
        answer_state = (
            "missing_context"
            if not normalized_watchlist_id
            else (
                "briefing_unavailable"
                if not isinstance(briefing, dict) or fallback_status == "briefing_unavailable"
                else (
                    "no_confident_answer"
                    if normalized_query
                    and (
                        fallback_status in {"limited", "insufficient_evidence", "story_not_found"}
                        or retrieval_hit_count == 0
                    )
                    else "briefing_grounded"
                )
            )
        )

        context = (
            answer_contract.get("context")
            if isinstance(answer_contract, dict)
            and isinstance(answer_contract.get("context"), dict)
            else {}
        )
        selected_story_page_dict = (
            selected_story_payload if isinstance(selected_story_payload, dict) else {}
        )
        selected_story_dict = selected_story if isinstance(selected_story, dict) else {}
        briefing_summary = (
            briefing.get("summary")
            if isinstance(briefing, dict) and isinstance(briefing.get("summary"), dict)
            else {}
        )

        return {
            "question": normalized_query,
            "mode": normalized_mode,
            "top_k": normalized_top_k,
            "context": {
                "watchlist_id": normalized_watchlist_id,
                "watchlist_name": str(
                    context.get("watchlist_name")
                    or briefing_page_context.get("watchlist_name")
                    or self._watchlist_name(briefing)
                ).strip()
                or None,
                "story_id": str(
                    selected_story_page_dict.get("story_id")
                    or selected_story_dict.get("story_id")
                    or briefing_page_context.get("selected_story_id")
                    or normalized_story_id
                    or ""
                ).strip()
                or None,
                "selected_story_id": str(
                    context.get("selected_story_id")
                    or selected_story_page_dict.get("story_id")
                    or selected_story_dict.get("story_id")
                    or briefing_page_context.get("selected_story_id")
                    or ""
                ).strip()
                or None,
                "story_headline": str(
                    context.get("story_headline")
                    or selected_story_page_dict.get("headline")
                    or selected_story_dict.get("headline")
                    or briefing_page_context.get("story_headline")
                    or ""
                ).strip()
                or None,
                "topic_key": str(
                    context.get("topic_key")
                    or selected_story_page_dict.get("topic_key")
                    or selected_story_dict.get("topic_key")
                    or briefing_page_context.get("topic_key")
                    or normalized_topic_key
                    or ""
                ).strip()
                or None,
                "topic_label": str(
                    context.get("topic_label")
                    or selected_story_page_dict.get("topic_label")
                    or selected_story_dict.get("topic_label")
                    or briefing_page_context.get("topic_label")
                    or ""
                ).strip()
                or None,
                "selection_basis": str(
                    context.get("selection_basis")
                    or briefing_page_context.get("selection_basis")
                    or selection_basis
                    or "none"
                ),
                "mode": normalized_mode,
                "filters": (
                    context.get("filters")
                    if isinstance(context.get("filters"), dict)
                    else normalized_filters
                ),
                "briefing_available": isinstance(briefing, dict),
            },
            "answer_state": answer_state,
            "answer_headline": (
                str(
                    answer_contract.get("answer", {}).get("direct_answer")
                    if isinstance(answer_contract, dict)
                    and isinstance(answer_contract.get("answer"), dict)
                    and normalized_query
                    else ""
                ).strip()
                or str(
                    selected_story_page_dict.get("headline")
                    or selected_story_dict.get("headline")
                    or briefing_summary.get("primary_story_headline")
                    or ""
                ).strip()
                or None
            ),
            "answer_summary": (
                str(
                    (
                        answer_contract.get("answer", {}).get("summary")
                        if isinstance(answer_contract, dict)
                        and isinstance(answer_contract.get("answer"), dict)
                        and normalized_query
                        else briefing_summary.get("overview")
                    )
                    or ""
                ).strip()
                or None
                if answer_state == "briefing_grounded"
                else None
            ),
            "answer_reason": (
                (
                    str(
                        (
                            answer_contract.get("answer", {}).get("reason")
                            if isinstance(answer_contract, dict)
                            and isinstance(answer_contract.get("answer"), dict)
                            and normalized_query
                            else (
                                (briefing_summary.get("signals") or [{}])[0].get("reason")
                                if isinstance(briefing_summary.get("signals"), list)
                                and briefing_summary.get("signals")
                                and isinstance((briefing_summary.get("signals") or [{}])[0], dict)
                                else None
                            )
                        )
                        or (
                            answer_contract.get("changes", {}).get("story_focus_summary")
                            if isinstance(answer_contract, dict)
                            and isinstance(answer_contract.get("changes"), dict)
                            else None
                        )
                        or (
                            answer_contract.get("fallback", {}).get("reason")
                            if isinstance(answer_contract, dict)
                            and isinstance(answer_contract.get("fallback"), dict)
                            else None
                        )
                        or (
                            briefing.get("differences", {}).get("compare", {}).get("diff_excerpt")
                            if isinstance(briefing, dict)
                            and isinstance(briefing.get("differences"), dict)
                            and isinstance(briefing.get("differences", {}).get("compare"), dict)
                            else None
                        )
                        or ""
                    ).strip()
                    or None
                )
                if answer_state == "briefing_grounded"
                else str(fallback.get("reason") or "").strip() or None
            ),
            "answer_confidence": (
                str(
                    answer_contract.get("answer", {}).get("confidence")
                    if isinstance(answer_contract, dict)
                    and isinstance(answer_contract.get("answer"), dict)
                    else ("grounded" if answer_state == "briefing_grounded" else "limited")
                ).strip()
                or "limited"
            ),
            "story_change_summary": (
                str(
                    answer_contract.get("changes", {}).get("story_focus_summary")
                    if isinstance(answer_contract, dict)
                    and isinstance(answer_contract.get("changes"), dict)
                    else (
                        story_page.get("story_change_summary")
                        if isinstance(story_page, dict)
                        else ""
                    )
                ).strip()
                or None
            ),
            "story_page": story_page,
            "retrieval": retrieval,
            "citations": (
                list(answer_contract.get("citations") or [])
                if isinstance(answer_contract, dict)
                else (
                    list(story_page.get("citations") or []) if isinstance(story_page, dict) else []
                )
            ),
            "fallback_reason": (
                str(fallback.get("reason") or "").strip()
                or (
                    str(story_page.get("fallback_reason") or "").strip()
                    if isinstance(story_page, dict)
                    else None
                )
            ),
            "fallback_next_step": (
                str(fallback.get("suggested_next_step") or "").strip()
                or (
                    str(story_page.get("fallback_next_step") or "").strip()
                    if isinstance(story_page, dict)
                    else None
                )
            ),
            "fallback_actions": list(fallback.get("actions") or [])
            or (
                list(story_page.get("fallback_actions") or [])
                if isinstance(story_page, dict)
                else []
            ),
        }

    def search(
        self,
        *,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
        mode: RetrievalMode = "keyword",
    ) -> dict[str, Any]:
        normalized_query = query.strip()
        normalized_filters = self._normalize_filters(filters)
        normalized_mode = self._normalize_mode(mode)
        keyword_hits = self._search_keyword(
            query=normalized_query,
            top_k=top_k,
            filters=normalized_filters,
        )
        if normalized_mode == "keyword":
            hits = keyword_hits
        else:
            semantic_hits = self._search_semantic(
                query=normalized_query,
                top_k=top_k,
                filters=normalized_filters,
                strict=(normalized_mode == "semantic"),
            )
            if normalized_mode == "semantic":
                hits = semantic_hits
            else:
                hits = self._merge_hybrid_hits(
                    keyword_hits=keyword_hits, semantic_hits=semantic_hits, top_k=top_k
                )

        return {
            "query": normalized_query,
            "top_k": top_k,
            "filters": normalized_filters,
            "items": hits[:top_k],
        }

    def _load_watchlist_briefing(self, *, watchlist_id: str | None) -> dict[str, Any] | None:
        normalized_watchlist_id = str(watchlist_id or "").strip()
        if not normalized_watchlist_id:
            return None
        from .watchlists import WatchlistsService

        return WatchlistsService(self.db).get_watchlist_briefing(
            watchlist_id=normalized_watchlist_id
        )

    def _load_watchlist_briefing_page(
        self,
        *,
        watchlist_id: str | None,
        story_id: str | None,
        query: str,
    ) -> dict[str, Any] | None:
        normalized_watchlist_id = str(watchlist_id or "").strip()
        if not normalized_watchlist_id:
            return None
        from .watchlists import WatchlistsService

        return WatchlistsService(self.db).get_watchlist_briefing_page(
            watchlist_id=normalized_watchlist_id,
            story_id=story_id,
            query=query,
        )

    @staticmethod
    def _extract_briefing_context(payload: dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(payload, dict) and isinstance(payload.get("context"), dict):
            return payload.get("context") or {}
        return {}

    @staticmethod
    def _extract_briefing_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if isinstance(payload, dict) and isinstance(payload.get("briefing"), dict):
            return payload.get("briefing")
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("summary"), dict)
            and isinstance(payload.get("evidence"), dict)
        ):
            return payload
        return None

    def _extract_selected_story(
        self,
        payload: dict[str, Any] | None,
        *,
        briefing_payload: dict[str, Any] | None,
        story_id: str | None,
        query: str,
    ) -> dict[str, Any] | None:
        candidate_story_id = None
        if isinstance(payload, dict):
            selected_story = payload.get("selected_story")
            if isinstance(selected_story, dict):
                candidate_story_id = str(selected_story.get("story_id") or "").strip() or None
                if isinstance(selected_story.get("evidence_cards"), list):
                    return selected_story
            selection = payload.get("selection")
            if isinstance(selection, dict) and isinstance(selection.get("story"), dict):
                selected_story = selection.get("story")
                candidate_story_id = str(selected_story.get("story_id") or "").strip() or None
                if isinstance(selected_story.get("evidence_cards"), list):
                    return selected_story
        if isinstance(briefing_payload, dict) and candidate_story_id:
            evidence = briefing_payload.get("evidence")
            stories = evidence.get("stories") if isinstance(evidence, dict) else None
            if isinstance(stories, list):
                for story in stories:
                    if not isinstance(story, dict):
                        continue
                    if str(story.get("story_id") or "").strip() == candidate_story_id:
                        return story
        selected_story, _ = self._select_briefing_story(
            briefing=briefing_payload,
            story_id=story_id,
            query=query,
        )
        return selected_story

    def _ensure_story_page_payload(
        self,
        payload: dict[str, Any] | None,
        *,
        watchlist_id: str | None,
        story_id: str | None,
        query: str,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        if isinstance(payload.get("briefing"), dict) and isinstance(payload.get("context"), dict):
            normalized = dict(payload)
            briefing = self._extract_briefing_payload(normalized)
            selected_story = self._extract_selected_story(
                normalized,
                briefing_payload=briefing,
                story_id=story_id,
                query=query,
            )
            if isinstance(briefing, dict):
                normalized_briefing = dict(briefing)
                selection = normalized_briefing.get("selection")
                if isinstance(selection, dict):
                    normalized_selection = dict(selection)
                    normalized_selection["story"] = None
                    normalized_briefing["selection"] = normalized_selection
                normalized["briefing"] = normalized_briefing
            normalized["selected_story"] = selected_story
            normalized.pop("story_focus", None)
            return normalized

        briefing = self._extract_briefing_payload(payload)
        if not isinstance(briefing, dict):
            return None

        page = build_briefing_page_payload(
            briefing=briefing,
            story_id=story_id,
            selection_query=query,
        )
        selection = page["selection"]
        selected_story = page["selected_story"]
        routes = page["routes"]
        watchlist = briefing.get("watchlist") if isinstance(briefing.get("watchlist"), dict) else {}

        return {
            "context": {
                "watchlist_id": str(watchlist_id or "").strip() or None,
                "watchlist_name": str(watchlist.get("name") or "").strip() or None,
                "story_id": selection["requested_story_id"],
                "selected_story_id": selection["selected_story_id"],
                "story_headline": selection["story_headline"],
                "topic_key": selection["topic_key"],
                "topic_label": selection["topic_label"],
                "selection_basis": selection["selection_basis"],
                "question_seed": selection["question_seed"],
            },
            "briefing": {
                **briefing,
                "selection": {
                    "selected_story_id": selection["selected_story_id"],
                    "selection_basis": selection["selection_basis"],
                    "story": None,
                },
            },
            "selected_story": selected_story,
            "story_change_summary": None,
            "citations": [],
            "routes": routes,
            "ask_route": str(routes.get("ask") or "").strip() or None,
            "compare_route": str(routes.get("job_compare") or "").strip() or None,
            "fallback_reason": None,
            "fallback_next_step": None,
            "fallback_actions": [],
        }

    def _select_briefing_story(
        self,
        *,
        briefing: dict[str, Any] | None,
        story_id: str | None,
        query: str,
    ) -> tuple[dict[str, Any] | None, str]:
        return select_story_from_briefing(briefing, story_id=story_id, query=query)

    def _resolve_primary_job_id(
        self,
        *,
        briefing: dict[str, Any] | None,
        story: dict[str, Any] | None,
    ) -> str | None:
        if isinstance(story, dict):
            story_job_id = str(story.get("latest_run_job_id") or "").strip()
            if story_job_id:
                return story_job_id
        if not isinstance(briefing, dict):
            return None
        differences = briefing.get("differences")
        if isinstance(differences, dict):
            latest_job_id = str(differences.get("latest_job_id") or "").strip()
            if latest_job_id:
                return latest_job_id
        return None

    def _build_answer_output(
        self,
        *,
        query: str,
        briefing: dict[str, Any] | None,
        story: dict[str, Any] | None,
        retrieval_items: list[dict[str, Any]],
        changes: dict[str, Any],
        fallback_status: str,
    ) -> dict[str, Any]:
        overview = self._briefing_overview(briefing)
        watchlist_name = self._watchlist_name(briefing)
        story_headline = str(story.get("headline") or "").strip() if isinstance(story, dict) else ""
        strongest_hit = retrieval_items[0] if retrieval_items else None

        if story_headline:
            direct_answer = (
                f'For "{query}", the current briefing most strongly points to "{story_headline}".'
            )
        elif strongest_hit is not None:
            direct_answer = (
                f'For "{query}", the strongest grounded match comes from '
                f"{self._format_hit_source(strongest_hit)}."
            )
        elif isinstance(briefing, dict):
            direct_answer = (
                f"{watchlist_name} has a briefing context, but it does not yet surface a direct answer for "
                f'"{query}".'
            )
        else:
            direct_answer = (
                f'There is not enough grounded briefing evidence to answer "{query}" yet.'
            )

        summary_parts: list[str] = []
        if overview:
            summary_parts.append(overview)
        if strongest_hit is not None:
            summary_parts.append(
                f"The strongest query match is {self._format_hit_source(strongest_hit)}: "
                f"{str(strongest_hit.get('snippet') or '').strip()}"
            )
        elif isinstance(story, dict):
            evidence_cards = story.get("evidence_cards")
            if isinstance(evidence_cards, list) and evidence_cards:
                lead_card = evidence_cards[0] if isinstance(evidence_cards[0], dict) else {}
                card_body = str(lead_card.get("card_body") or "").strip()
                if card_body:
                    summary_parts.append(f"Selected story evidence: {card_body}")
        if not summary_parts:
            summary_parts.append(direct_answer)

        story_focus_summary = str(changes.get("story_focus_summary") or "").strip()
        answer_reason: str | None = None
        if story_focus_summary:
            answer_reason = story_focus_summary
        elif strongest_hit is not None:
            answer_reason = (
                f"The current answer is anchored by {self._format_hit_source(strongest_hit)} "
                "as the strongest grounded match."
            )
        elif overview:
            answer_reason = overview
        elif isinstance(briefing, dict):
            answer_reason = (
                f"{watchlist_name} still provides a briefing context, but the current story layer "
                "needs stronger supporting evidence."
            )

        confidence = "grounded" if fallback_status == "grounded" else "limited"
        return {
            "direct_answer": direct_answer,
            "summary": " ".join(part for part in summary_parts if part).strip(),
            "reason": answer_reason,
            "confidence": confidence,
        }

    def _build_answer_changes(
        self,
        *,
        briefing: dict[str, Any] | None,
        story: dict[str, Any] | None,
    ) -> dict[str, Any]:
        differences = briefing.get("differences") if isinstance(briefing, dict) else None
        if not isinstance(differences, dict):
            return {
                "summary": "No watchlist briefing changes are available for this answer.",
                "story_focus_summary": self._build_story_focus_summary(
                    story=story,
                    new_story_keys=[],
                    removed_story_keys=[],
                    compare_excerpt=None,
                ),
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
            }

        compare = differences.get("compare")
        compare_dict = compare if isinstance(compare, dict) else {}
        added_topics = [
            str(item).strip() for item in differences.get("added_topics") or [] if str(item).strip()
        ]
        removed_topics = [
            str(item).strip()
            for item in differences.get("removed_topics") or []
            if str(item).strip()
        ]
        added_claim_kinds = [
            str(item).strip()
            for item in differences.get("added_claim_kinds") or []
            if str(item).strip()
        ]
        removed_claim_kinds = [
            str(item).strip()
            for item in differences.get("removed_claim_kinds") or []
            if str(item).strip()
        ]
        new_story_keys = [
            str(item).strip()
            for item in differences.get("new_story_keys") or []
            if str(item).strip()
        ]
        removed_story_keys = [
            str(item).strip()
            for item in differences.get("removed_story_keys") or []
            if str(item).strip()
        ]

        summary_parts: list[str] = []
        if added_topics:
            summary_parts.append(f"Added topics: {', '.join(added_topics)}.")
        if removed_topics:
            summary_parts.append(f"Removed topics: {', '.join(removed_topics)}.")
        if added_claim_kinds:
            summary_parts.append(f"Added claim kinds: {', '.join(added_claim_kinds)}.")
        if removed_claim_kinds:
            summary_parts.append(f"Removed claim kinds: {', '.join(removed_claim_kinds)}.")
        if new_story_keys:
            summary_parts.append(f"New story keys: {', '.join(new_story_keys)}.")
        if removed_story_keys:
            summary_parts.append(f"Removed story keys: {', '.join(removed_story_keys)}.")
        compare_excerpt = str(compare_dict.get("diff_excerpt") or "").strip() or None
        if compare_excerpt and not summary_parts:
            summary_parts.append("The latest run includes a compare diff excerpt.")
        if not summary_parts:
            summary_parts.append(
                "No major watchlist-to-watchlist changes were surfaced in the current briefing."
            )

        return {
            "summary": " ".join(summary_parts).strip(),
            "story_focus_summary": self._build_story_focus_summary(
                story=story,
                new_story_keys=new_story_keys,
                removed_story_keys=removed_story_keys,
                compare_excerpt=compare_excerpt,
            ),
            "latest_job_id": str(differences.get("latest_job_id") or "").strip() or None,
            "previous_job_id": str(differences.get("previous_job_id") or "").strip() or None,
            "added_topics": added_topics,
            "removed_topics": removed_topics,
            "added_claim_kinds": added_claim_kinds,
            "removed_claim_kinds": removed_claim_kinds,
            "new_story_keys": new_story_keys,
            "removed_story_keys": removed_story_keys,
            "compare_excerpt": compare_excerpt,
            "compare_route": str(compare_dict.get("compare_route") or "").strip() or None,
            "has_previous": bool(compare_dict.get("has_previous")),
        }

    def _build_answer_citations(
        self,
        *,
        briefing: dict[str, Any] | None,
        story: dict[str, Any] | None,
        retrieval_items: list[dict[str, Any]],
        changes: dict[str, Any],
    ) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        if isinstance(story, dict):
            routes = story.get("routes") if isinstance(story.get("routes"), dict) else {}
            citations.append(
                {
                    "kind": "briefing_story",
                    "label": str(story.get("headline") or "Selected briefing story").strip(),
                    "snippet": self._story_support_snippet(story),
                    "source_url": None,
                    "job_id": str(story.get("latest_run_job_id") or "").strip() or None,
                    "route": str(routes.get("briefing") or "").strip() or None,
                    "route_label": "Open briefing story",
                }
            )
            cards = story.get("evidence_cards")
            if isinstance(cards, list):
                for card in cards[:2]:
                    if not isinstance(card, dict):
                        continue
                    citations.append(
                        {
                            "kind": "briefing_card",
                            "label": str(
                                card.get("card_title")
                                or card.get("topic_label")
                                or card.get("source_section")
                                or "Briefing evidence card"
                            ).strip(),
                            "snippet": str(card.get("card_body") or "").strip(),
                            "source_url": str(card.get("source_url") or "").strip() or None,
                            "job_id": str(card.get("job_id") or "").strip() or None,
                            "route": str(routes.get("job_knowledge_cards") or "").strip() or None,
                            "route_label": "Open knowledge cards",
                        }
                    )
        for hit in retrieval_items[:2]:
            citations.append(
                {
                    "kind": "retrieval_hit",
                    "label": self._format_hit_source(hit),
                    "snippet": str(hit.get("snippet") or "").strip(),
                    "source_url": str(hit.get("source_url") or "").strip() or None,
                    "job_id": str(hit.get("job_id") or "").strip() or None,
                    "route": self._job_route_for_hit(hit),
                    "route_label": "Open job trace",
                }
            )
        compare_excerpt = str(changes.get("compare_excerpt") or "").strip()
        compare_route = str(changes.get("compare_route") or "").strip()
        latest_job_id = str(changes.get("latest_job_id") or "").strip()
        if compare_excerpt:
            citations.append(
                {
                    "kind": "job_compare",
                    "label": "Latest compare excerpt",
                    "snippet": compare_excerpt,
                    "source_url": None,
                    "job_id": latest_job_id or None,
                    "route": compare_route or None,
                    "route_label": "Open compare",
                }
            )
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in citations:
            key = (
                str(item.get("kind") or ""),
                str(item.get("label") or ""),
                str(item.get("snippet") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:6]

    def _build_answer_evidence(
        self,
        *,
        briefing: dict[str, Any] | None,
        story: dict[str, Any] | None,
        retrieval_items: list[dict[str, Any]],
        citation_count: int,
    ) -> dict[str, Any]:
        story_cards_payload: list[dict[str, Any]] = []
        if isinstance(story, dict):
            cards = story.get("evidence_cards")
            if isinstance(cards, list):
                for item in cards[:3]:
                    if not isinstance(item, dict):
                        continue
                    story_cards_payload.append(
                        {
                            "card_id": str(item.get("card_id") or "").strip() or None,
                            "job_id": str(item.get("job_id") or "").strip() or None,
                            "platform": str(item.get("platform") or "").strip() or None,
                            "source_url": str(item.get("source_url") or "").strip() or None,
                            "title": str(item.get("card_title") or "").strip() or None,
                            "body": str(item.get("card_body") or "").strip(),
                            "source_section": str(item.get("source_section") or "").strip() or None,
                        }
                    )
        return {
            "briefing_overview": self._briefing_overview(briefing),
            "selected_story_id": str(story.get("story_id") or "").strip() or None
            if isinstance(story, dict)
            else None,
            "selected_story_headline": str(story.get("headline") or "").strip() or None
            if isinstance(story, dict)
            else None,
            "latest_job_id": self._resolve_primary_job_id(briefing=briefing, story=story),
            "citation_count": citation_count,
            "retrieval_hit_count": len(retrieval_items),
            "retrieval_items": retrieval_items[:3],
            "story_cards": story_cards_payload,
        }

    def _build_answer_fallback(
        self,
        *,
        watchlist_id: str | None,
        story_id: str | None,
        briefing: dict[str, Any] | None,
        story: dict[str, Any] | None,
        retrieval_items: list[dict[str, Any]],
        citations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        story_routes = (
            story.get("routes")
            if isinstance(story, dict) and isinstance(story.get("routes"), dict)
            else {}
        )
        if (
            isinstance(watchlist_id, str)
            and watchlist_id.strip()
            and not isinstance(briefing, dict)
        ):
            return {
                "status": "briefing_unavailable",
                "reason": "The requested watchlist does not have a briefing payload yet.",
                "suggested_next_step": "Open the watchlist briefing first, then retry Ask against that watchlist.",
                "actions": [
                    {
                        "kind": "open_briefing",
                        "label": "Open watchlist briefing",
                        "route": f"/briefings?watchlist_id={watchlist_id.strip()}",
                    }
                ],
            }
        if isinstance(story_id, str) and story_id.strip() and not isinstance(story, dict):
            return {
                "status": "story_not_found",
                "reason": "The requested story_id was not found inside the current briefing context.",
                "suggested_next_step": "Use the suggested story from the current briefing or pick a visible story id.",
                "actions": [
                    {
                        "kind": "open_briefing",
                        "label": "Open watchlist briefing",
                        "route": f"/briefings?watchlist_id={watchlist_id.strip()}"
                        if watchlist_id
                        else None,
                    }
                ],
            }
        if citations:
            return {
                "status": "grounded",
                "reason": None,
                "suggested_next_step": None,
                "actions": [],
            }
        if isinstance(briefing, dict):
            if retrieval_items:
                return {
                    "status": "limited",
                    "reason": "Retrieval found matches, but the current briefing did not supply stronger structured citations.",
                    "suggested_next_step": "Inspect the cited jobs and knowledge cards before treating this as a strong answer.",
                    "actions": [
                        {
                            "kind": "open_story",
                            "label": "Open selected story",
                            "route": str(story_routes.get("briefing") or "").strip() or None,
                        },
                        {
                            "kind": "open_job",
                            "label": "Open latest job trace",
                            "route": self._job_route_for_hit(retrieval_items[0])
                            if retrieval_items
                            else None,
                        },
                    ],
                }
            return {
                "status": "limited",
                "reason": "The briefing exists, but it does not yet surface direct evidence for this question.",
                "suggested_next_step": "Refine the question or open a story with stronger evidence cards.",
                "actions": [
                    {
                        "kind": "open_story",
                        "label": "Open selected story",
                        "route": str(story_routes.get("briefing") or "").strip() or None,
                    },
                    {
                        "kind": "open_search",
                        "label": "Open raw search",
                        "route": "/search",
                    },
                ],
            }
        return {
            "status": "insufficient_evidence",
            "reason": "No briefing context or grounded evidence was available for this question.",
            "suggested_next_step": "Provide a watchlist-backed briefing context before asking for an answer.",
            "actions": [
                {
                    "kind": "open_briefing",
                    "label": "Open briefings",
                    "route": "/briefings",
                }
            ],
        }

    def _serialize_selected_story(self, *, story: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(story, dict):
            return None
        return {
            "story_id": str(story.get("story_id") or "").strip(),
            "story_key": str(story.get("story_key") or "").strip(),
            "headline": str(story.get("headline") or "").strip(),
            "topic_key": str(story.get("topic_key") or "").strip() or None,
            "topic_label": str(story.get("topic_label") or "").strip() or None,
            "source_count": int(story.get("source_count") or 0),
            "run_count": int(story.get("run_count") or 0),
            "matched_card_count": int(story.get("matched_card_count") or 0),
            "platforms": list(story.get("platforms") or []),
            "claim_kinds": list(story.get("claim_kinds") or []),
            "source_urls": list(story.get("source_urls") or []),
            "latest_run_job_id": str(story.get("latest_run_job_id") or "").strip() or None,
            "routes": story.get("routes") if isinstance(story.get("routes"), dict) else {},
        }

    def _build_story_focus_summary(
        self,
        *,
        story: dict[str, Any] | None,
        new_story_keys: list[str],
        removed_story_keys: list[str],
        compare_excerpt: str | None,
    ) -> str | None:
        if not isinstance(story, dict):
            return None
        headline = str(story.get("headline") or "").strip() or "The selected story"
        story_key = str(story.get("story_key") or "").strip()
        source_count = int(story.get("source_count") or 0)
        run_count = int(story.get("run_count") or 0)
        matched_card_count = int(story.get("matched_card_count") or 0)
        if story_key and story_key in new_story_keys:
            return (
                f'"{headline}" is newly surfaced in the latest briefing and is already backed by '
                f"{source_count} source families."
            )
        if story_key and story_key in removed_story_keys:
            return f'"{headline}" was removed from the latest story set, so treat this answer as stale context.'
        if compare_excerpt:
            return (
                f'"{headline}" remains the selected story focus, and the latest compare still shows movement '
                "around it."
            )
        if matched_card_count > 0:
            return (
                f'"{headline}" is the current story focus across {run_count} runs and '
                f"{matched_card_count} matched evidence cards."
            )
        if source_count > 0:
            return f'"{headline}" remains the strongest story focus across {source_count} source families.'
        return f'"{headline}" is the current story focus for this answer.'

    @staticmethod
    def _watchlist_name(briefing: dict[str, Any] | None) -> str:
        if not isinstance(briefing, dict):
            return "This watchlist"
        watchlist = briefing.get("watchlist")
        if not isinstance(watchlist, dict):
            return "This watchlist"
        return str(watchlist.get("name") or "").strip() or "This watchlist"

    @staticmethod
    def _briefing_overview(briefing: dict[str, Any] | None) -> str | None:
        if not isinstance(briefing, dict):
            return None
        summary = briefing.get("summary")
        if not isinstance(summary, dict):
            return None
        overview = str(summary.get("overview") or "").strip()
        return overview or None

    @staticmethod
    def _story_support_snippet(story: dict[str, Any]) -> str:
        source_count = int(story.get("source_count") or 0)
        run_count = int(story.get("run_count") or 0)
        matched_card_count = int(story.get("matched_card_count") or 0)
        return (
            f"Supported across {source_count} source families, {run_count} runs, "
            f"and {matched_card_count} matched cards."
        )

    @staticmethod
    def _format_hit_source(hit: dict[str, Any]) -> str:
        source = str(hit.get("source") or "").strip() or "retrieval"
        platform = str(hit.get("platform") or "").strip() or "unknown platform"
        title = str(hit.get("title") or "").strip() or "untitled source"
        return f"{source} on {platform} ({title})"

    @staticmethod
    def _job_route_for_hit(hit: dict[str, Any]) -> str | None:
        job_id = str(hit.get("job_id") or "").strip()
        if not job_id:
            return None
        return f"/jobs?job_id={job_id}"

    @staticmethod
    def _query_tokens(query: str) -> set[str]:
        return {token for token in _QUERY_TOKEN_PATTERN.findall(query.strip().lower()) if token}

    def _normalize_mode(self, mode: str) -> RetrievalMode:
        normalized = str(mode).strip().lower()
        if normalized not in _RETRIEVAL_MODES:
            return "keyword"
        return cast("RetrievalMode", normalized)

    def _search_keyword(
        self, *, query: str, top_k: int, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        rows = self._list_candidate_jobs(top_k=top_k, filters=filters)
        hits: list[dict[str, Any]] = []
        for row in rows:
            artifact_root = row.get("artifact_root")
            if not isinstance(artifact_root, str) or not artifact_root.strip():
                continue
            for source, content in self._iter_artifact_texts(artifact_root):
                if source == "knowledge_cards":
                    hits.extend(
                        self._match_knowledge_cards(
                            row=row,
                            content=content,
                            query=query,
                        )
                    )
                    continue
                match = self._match_content(content=content, query=query)
                if match is None:
                    continue
                score, snippet = match
                score += _KEYWORD_SOURCE_SCORE_BOOSTS.get(source, 0.0)
                hits.append(
                    self._build_hit(
                        row=row,
                        source=source,
                        snippet=snippet,
                        score=score,
                    )
                )
        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits[:top_k]

    def _match_knowledge_cards(
        self,
        *,
        row: dict[str, Any],
        content: str,
        query: str,
    ) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = self._match_content(content=content, query=query)
            if match is None:
                return []
            score, snippet = match
            score += _KEYWORD_SOURCE_SCORE_BOOSTS.get("knowledge_cards", 0.0)
            return [
                self._build_hit(
                    row=row,
                    source="knowledge_cards",
                    snippet=snippet[:400],
                    score=score,
                )
            ]
        cards = parsed if isinstance(parsed, list) else []
        hits: list[dict[str, Any]] = []
        query_norm = query.strip().lower()
        if not query_norm:
            return []

        for index, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            title = str(card.get("title") or "").strip()
            body = str(card.get("body") or "").strip()
            source_section = str(card.get("source_section") or "").strip()
            metadata = card.get("metadata")
            metadata_dict = metadata if isinstance(metadata, dict) else {}
            topic_key = str(metadata_dict.get("topic_key") or "").strip()
            topic_label = str(metadata_dict.get("topic_label") or "").strip()
            claim_kind = str(metadata_dict.get("claim_kind") or "").strip()
            confidence_label = str(metadata_dict.get("confidence_label") or "").strip()
            searchable = "\n".join(
                part
                for part in [
                    title,
                    body,
                    source_section,
                    topic_key,
                    topic_label,
                    claim_kind,
                    confidence_label,
                ]
                if part
            )
            match = self._match_content(content=searchable, query=query)
            if match is None:
                continue
            score, _snippet = match
            score += _KEYWORD_SOURCE_SCORE_BOOSTS.get("knowledge_cards", 0.0)
            if query_norm in topic_key.lower() or query_norm in topic_label.lower():
                score += 1.5
            if query_norm == claim_kind.lower():
                score += 1.2
            if confidence_label.lower() == "high":
                score += 0.35

            snippet_parts = [
                title or f"Knowledge card {index + 1}",
                body,
            ]
            if topic_label:
                snippet_parts.append(f"Topic: {topic_label}")
            if claim_kind:
                snippet_parts.append(f"claim_kind:{claim_kind}")
            if topic_key:
                snippet_parts.append(f"topic_key:{topic_key}")
            snippet = re.sub(
                r"\s+", " ", " | ".join(part for part in snippet_parts if part)
            ).strip()
            hits.append(
                self._build_hit(
                    row=row,
                    source="knowledge_cards",
                    snippet=snippet[:400],
                    score=score,
                )
            )
        return hits

    def _search_semantic(
        self, *, query: str, top_k: int, filters: dict[str, Any], strict: bool = False
    ) -> list[dict[str, Any]]:
        try:
            query_embedding = self._build_query_embedding(query)
        except ApiServiceError:
            if strict:
                raise
            logger.warning(
                "retrieval_semantic_embedding_failed_fallback",
                extra={"query_length": len(query.strip())},
            )
            return []
        if not query_embedding:
            return []
        params: dict[str, Any] = {
            "query_embedding": self._to_vector_literal(query_embedding),
            "platform": filters.get("platform"),
            "job_id": filters.get("job_id"),
            "video_id": filters.get("video_id"),
            "video_uid": filters.get("video_uid"),
            "kind": filters.get("kind"),
            "mode": filters.get("mode"),
            "limit": min(max(top_k * 4, 20), 120),
        }
        statement = text(
            """
            SELECT
                j.id AS job_id,
                j.video_id AS video_id,
                j.kind AS kind,
                j.mode AS mode,
                v.platform AS platform,
                v.video_uid AS video_uid,
                v.source_url AS source_url,
                v.title AS title,
                ve.content_type AS source,
                ve.chunk_text AS snippet,
                1 - (ve.embedding <=> CAST(:query_embedding AS vector(768))) AS score
            FROM video_embeddings ve
            JOIN jobs j ON j.id = ve.job_id
            JOIN videos v ON v.id = ve.video_id
            WHERE j.status = 'succeeded'
              AND (:platform IS NULL OR v.platform = :platform)
              AND (:job_id IS NULL OR CAST(j.id AS TEXT) = :job_id)
              AND (:video_id IS NULL OR CAST(v.id AS TEXT) = :video_id)
              AND (:video_uid IS NULL OR v.video_uid = :video_uid)
              AND (:kind IS NULL OR j.kind = :kind)
              AND (:mode IS NULL OR j.mode = :mode)
            ORDER BY ve.embedding <=> CAST(:query_embedding AS vector(768)) ASC
            LIMIT :limit
            """
        )
        try:
            rows = self.db.execute(statement, params).mappings().all()
        except DBAPIError as exc:
            self.db.rollback()
            if strict:
                logger.exception(
                    "retrieval_semantic_query_failed",
                    extra={"query_length": len(query.strip())},
                )
                raise ApiServiceError(
                    detail="retrieval semantic query failed",
                    error_code="RETRIEVAL_SEMANTIC_QUERY_FAILED",
                ) from exc
            logger.warning(
                "retrieval_semantic_query_failed_fallback",
                extra={"query_length": len(query.strip())},
            )
            return []

        hits: list[dict[str, Any]] = []
        for row in rows:
            source = str(row.get("source") or "").strip().lower()
            if source not in {"transcript", "outline"}:
                source = "transcript"
            score_raw = row.get("score")
            if not isinstance(score_raw, (int, float)):
                continue
            snippet = re.sub(r"\s+", " ", str(row.get("snippet") or "")).strip()
            if not snippet:
                continue
            hits.append(
                self._build_hit(
                    row=row,
                    source=source,
                    snippet=snippet[:400],
                    score=float(score_raw),
                )
            )

        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits[:top_k]

    @staticmethod
    def _merge_hybrid_hits(
        *,
        keyword_hits: list[dict[str, Any]],
        semantic_hits: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in keyword_hits + semantic_hits:
            key = (
                str(item.get("job_id") or ""),
                str(item.get("source") or ""),
                str(item.get("snippet") or ""),
            )
            existing = merged.get(key)
            if existing is None or float(item.get("score") or 0.0) > float(
                existing.get("score") or 0.0
            ):
                merged[key] = item
        ordered = sorted(
            merged.values(), key=lambda item: float(item.get("score") or 0.0), reverse=True
        )
        return ordered[:top_k]

    def _build_query_embedding(self, query: str) -> list[float] | None:
        normalized_query = query.strip()
        if not normalized_query:
            return None
        settings = Settings.from_env()
        provider = (getattr(settings, "llm_provider", "gemini") or "").strip().lower()
        api_key = (settings.gemini_api_key or "").strip()
        if provider != "gemini":
            logger.info(
                "retrieval_embedding_skipped_provider_not_supported", extra={"provider": provider}
            )
            return None
        if not api_key:
            logger.info("retrieval_embedding_skipped_missing_api_key", extra={"provider": provider})
            return None
        model = (
            settings.gemini_embedding_model or "gemini-embedding-001"
        ).strip() or "gemini-embedding-001"
        try:
            sdk = load_gemini_sdk(import_module=importlib.import_module)
            genai_types = sdk.genai_types
        except ImportError as exc:
            logger.exception(
                "retrieval_embedding_dependency_missing",
                extra={"provider": provider, "model": model, "query_length": len(normalized_query)},
            )
            raise ApiServiceError(
                detail="retrieval embedding dependency not available",
                error_code="RETRIEVAL_EMBEDDING_DEPENDENCY_MISSING",
                error_kind="dependency_error",
            ) from exc

        def _embed_content() -> Any:
            client = build_gemini_client(api_key=api_key, import_module=importlib.import_module)
            return client.models.embed_content(
                model=model,
                contents=[normalized_query],
                config=genai_types.EmbedContentConfig(output_dimensionality=_EMBEDDING_DIMENSION),
            )

        def _raise_embedding_timeout(timeout_seconds: float, exc: Exception) -> None:
            raise ApiTimeoutError(
                detail=f"retrieval embedding timed out after {timeout_seconds:.1f}s",
                error_code="RETRIEVAL_EMBEDDING_TIMEOUT",
            ) from exc

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                response = executor.submit(_embed_content).result(
                    timeout=settings.api_retrieval_embedding_timeout_seconds
                )
        except concurrent.futures.TimeoutError as exc:
            logger.error(
                "retrieval_embedding_timeout",
                extra={
                    "provider": provider,
                    "model": model,
                    "timeout_seconds": settings.api_retrieval_embedding_timeout_seconds,
                    "query_length": len(normalized_query),
                },
            )
            _raise_embedding_timeout(settings.api_retrieval_embedding_timeout_seconds, exc)
        except Exception as exc:
            if isinstance(exc, TimeoutError) or exc.__class__.__name__ == "TimeoutError":
                logger.error(
                    "retrieval_embedding_timeout",
                    extra={
                        "provider": provider,
                        "model": model,
                        "timeout_seconds": settings.api_retrieval_embedding_timeout_seconds,
                        "query_length": len(normalized_query),
                    },
                )
                _raise_embedding_timeout(settings.api_retrieval_embedding_timeout_seconds, exc)
            logger.exception(
                "retrieval_embedding_request_failed",
                extra={"provider": provider, "model": model, "query_length": len(normalized_query)},
            )
            raise ApiServiceError(
                detail="retrieval embedding request failed",
                error_code="RETRIEVAL_EMBEDDING_REQUEST_FAILED",
            ) from exc
        embedding = self._extract_embedding_values(response)
        if not embedding:
            logger.error(
                "retrieval_embedding_response_invalid",
                extra={"provider": provider, "model": model, "query_length": len(normalized_query)},
            )
            raise ApiServiceError(
                detail="retrieval embedding response invalid",
                error_code="RETRIEVAL_EMBEDDING_RESPONSE_INVALID",
            )
        return embedding

    def _extract_embedding_values(self, response: Any) -> list[float] | None:
        embeddings = getattr(response, "embeddings", None)
        if isinstance(embeddings, list) and embeddings:
            candidate = embeddings[0]
            values = self._extract_values(candidate)
            if values:
                return values
        return self._extract_values(response)

    def _extract_values(self, value: Any) -> list[float] | None:
        embedding = getattr(value, "embedding", None)
        if embedding is not None:
            values = getattr(embedding, "values", None)
            if isinstance(values, list) and values:
                return [float(v) for v in values]
        values = getattr(value, "values", None)
        if isinstance(values, list) and values:
            return [float(v) for v in values]
        if isinstance(value, dict):
            candidate = value.get("values")
            if isinstance(candidate, list) and candidate:
                return [float(v) for v in candidate]
            nested = value.get("embedding")
            if isinstance(nested, dict):
                nested_values = nested.get("values")
                if isinstance(nested_values, list) and nested_values:
                    return [float(v) for v in nested_values]
        return None

    @staticmethod
    def _to_vector_literal(values: list[float]) -> str:
        if not values:
            raise ValueError("embedding vector is empty")
        return "[" + ",".join(f"{float(value):.10f}" for value in values) + "]"

    def _build_hit(
        self,
        *,
        row: dict[str, Any],
        source: str,
        snippet: str,
        score: float,
    ) -> dict[str, Any]:
        return {
            "job_id": str(row.get("job_id")),
            "video_id": str(row.get("video_id")),
            "platform": str(row.get("platform") or ""),
            "video_uid": str(row.get("video_uid") or ""),
            "source_url": str(row.get("source_url") or ""),
            "title": row.get("title"),
            "kind": str(row.get("kind") or ""),
            "mode": row.get("mode"),
            "source": source,
            "snippet": snippet,
            "score": float(score),
        }

    def _normalize_filters(self, filters: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(filters, dict):
            return {}
        normalized: dict[str, Any] = {}
        for key, value in filters.items():
            if key not in _ALLOWED_FILTERS:
                continue
            if value is None:
                continue
            value_str = str(value).strip()
            if value_str:
                normalized[key] = value_str
        return normalized

    def _list_candidate_jobs(self, *, top_k: int, filters: dict[str, Any]) -> list[dict[str, Any]]:
        limit = min(max(top_k * 8, 50), 200)
        params: dict[str, Any] = {
            "platform": filters.get("platform"),
            "job_id": filters.get("job_id"),
            "video_id": filters.get("video_id"),
            "video_uid": filters.get("video_uid"),
            "kind": filters.get("kind"),
            "mode": filters.get("mode"),
            "limit": limit,
        }
        statement = text(
            """
            SELECT
                j.id AS job_id,
                j.video_id AS video_id,
                j.kind AS kind,
                j.mode AS mode,
                j.artifact_root AS artifact_root,
                v.platform AS platform,
                v.video_uid AS video_uid,
                v.source_url AS source_url,
                v.title AS title
            FROM jobs j
            JOIN videos v ON v.id = j.video_id
            WHERE j.status = 'succeeded'
              AND j.artifact_root IS NOT NULL
              AND (:platform IS NULL OR v.platform = :platform)
              AND (:job_id IS NULL OR CAST(j.id AS TEXT) = :job_id)
              AND (:video_id IS NULL OR CAST(v.id AS TEXT) = :video_id)
              AND (:video_uid IS NULL OR v.video_uid = :video_uid)
              AND (:kind IS NULL OR j.kind = :kind)
              AND (:mode IS NULL OR j.mode = :mode)
            ORDER BY j.updated_at DESC
            LIMIT :limit
            """
        )
        try:
            rows = self.db.execute(statement, params).mappings().all()
        except DBAPIError:
            self.db.rollback()
            return []
        return [dict(row) for row in rows]

    def _iter_artifact_texts(self, artifact_root: str) -> list[tuple[str, str]]:
        root = Path(artifact_root).expanduser()
        if not root.exists() or not root.is_dir():
            return []

        payload: list[tuple[str, str]] = []
        for source, filename in _SEARCH_FILES:
            path = root / filename
            if not path.exists() or not path.is_file():
                continue
            text_value = self._read_text(path)
            if text_value:
                payload.append((source, text_value))
        return payload

    def _read_text(self, path: Path) -> str:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return ""

        if path.suffix == ".json":
            try:
                parsed = json.loads(raw)
                if path.name == "knowledge_cards.json":
                    return self._render_knowledge_cards_text(parsed)
                return json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                return raw
        return raw

    def _render_knowledge_cards_text(self, payload: Any) -> str:
        if not isinstance(payload, list):
            return json.dumps(payload, ensure_ascii=False)

        lines: list[str] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            card_type = str(item.get("card_type") or "").strip()
            title = str(item.get("title") or "").strip()
            body = str(item.get("body") or "").strip()
            source_section = str(item.get("source_section") or "").strip()
            metadata = item.get("metadata")
            segments = [
                segment
                for segment in [card_type, title, body, source_section]
                if isinstance(segment, str) and segment
            ]
            if isinstance(metadata, dict):
                for key in (
                    "topic_key",
                    "topic_label",
                    "claim_id",
                    "claim_kind",
                    "confidence_label",
                ):
                    value = metadata.get(key)
                    if isinstance(value, str) and value.strip():
                        segments.append(f"{key}:{value.strip()}")
            if segments:
                lines.append(" | ".join(segments))
        return "\n".join(lines)

    def _match_content(self, *, content: str, query: str) -> tuple[float, str] | None:
        content_norm = content.strip()
        if not content_norm:
            return None

        query_norm = query.lower()
        haystack = content_norm.lower()
        first_index = haystack.find(query_norm)
        if first_index < 0:
            return None

        occurrences = haystack.count(query_norm)
        score = float(occurrences) + max(0.0, (2000.0 - min(2000, first_index)) / 2000.0)

        start = max(0, first_index - 80)
        end = min(len(content_norm), first_index + len(query) + 160)
        snippet = re.sub(r"\s+", " ", content_norm[start:end]).strip()
        return score, snippet
