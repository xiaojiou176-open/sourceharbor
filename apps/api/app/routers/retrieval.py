from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiServiceError
from ..services.retrieval import RetrievalService
from .watchlists import (
    WatchlistBriefingPageResponse,
    WatchlistBriefingRoutes,
)

router = APIRouter(prefix="/api/v1/retrieval", tags=["retrieval"])


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievalHit(BaseModel):
    job_id: str
    video_id: str
    platform: str
    video_uid: str
    source_url: str
    title: str | None = None
    kind: str
    mode: str | None = None
    source: Literal["digest", "transcript", "outline", "knowledge_cards", "comments", "meta"]
    snippet: str
    score: float


class RetrievalSearchResponse(BaseModel):
    query: str
    top_k: int
    filters: dict[str, Any]
    items: list[RetrievalHit]


class AskAnswerRequest(BaseModel):
    query: str = Field(min_length=1)
    watchlist_id: str | None = Field(default=None, min_length=1)
    story_id: str | None = Field(default=None, min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"
    filters: dict[str, Any] = Field(default_factory=dict)


class AskAnswerContext(BaseModel):
    watchlist_id: str | None = None
    watchlist_name: str | None = None
    story_id: str | None = None
    selected_story_id: str | None = None
    story_headline: str | None = None
    topic_key: str | None = None
    topic_label: str | None = None
    selection_basis: Literal[
        "requested_story_id",
        "query_match",
        "suggested_story_id",
        "first_story",
        "none",
    ] = "none"
    mode: Literal["keyword", "semantic", "hybrid"]
    filters: dict[str, Any]
    briefing_available: bool


class AskAnswerBody(BaseModel):
    direct_answer: str
    summary: str
    reason: str | None = None
    confidence: Literal["grounded", "limited"]


class AskAnswerChanges(BaseModel):
    summary: str
    story_focus_summary: str | None = None
    latest_job_id: str | None = None
    previous_job_id: str | None = None
    added_topics: list[str] = Field(default_factory=list)
    removed_topics: list[str] = Field(default_factory=list)
    added_claim_kinds: list[str] = Field(default_factory=list)
    removed_claim_kinds: list[str] = Field(default_factory=list)
    new_story_keys: list[str] = Field(default_factory=list)
    removed_story_keys: list[str] = Field(default_factory=list)
    compare_excerpt: str | None = None
    compare_route: str | None = None
    has_previous: bool


class AskAnswerCitation(BaseModel):
    kind: Literal["briefing_story", "briefing_card", "retrieval_hit", "job_compare"]
    label: str
    snippet: str
    source_url: str | None = None
    job_id: str | None = None
    route: str | None = None
    route_label: str | None = None


class AskAnswerSelectedStory(BaseModel):
    story_id: str
    story_key: str
    headline: str
    topic_key: str | None = None
    topic_label: str | None = None
    source_count: int
    run_count: int
    matched_card_count: int
    platforms: list[str] = Field(default_factory=list)
    claim_kinds: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    latest_run_job_id: str | None = None
    routes: WatchlistBriefingRoutes


class AskAnswerFallbackAction(BaseModel):
    kind: Literal["open_briefing", "open_story", "open_job", "open_knowledge", "open_search"]
    label: str
    route: str | None = None


class AskAnswerEvidenceCard(BaseModel):
    card_id: str | None = None
    job_id: str | None = None
    platform: str | None = None
    source_url: str | None = None
    title: str | None = None
    body: str
    source_section: str | None = None


class AskAnswerEvidence(BaseModel):
    briefing_overview: str | None = None
    selected_story_id: str | None = None
    selected_story_headline: str | None = None
    latest_job_id: str | None = None
    citation_count: int
    retrieval_hit_count: int
    retrieval_items: list[RetrievalHit] = Field(default_factory=list)
    story_cards: list[AskAnswerEvidenceCard] = Field(default_factory=list)


class AskAnswerFallback(BaseModel):
    status: Literal[
        "grounded",
        "limited",
        "briefing_unavailable",
        "story_not_found",
        "insufficient_evidence",
    ]
    reason: str | None = None
    suggested_next_step: str | None = None
    actions: list[AskAnswerFallbackAction] = Field(default_factory=list)


class AskAnswerResponse(BaseModel):
    query: str
    context: AskAnswerContext
    selected_story: AskAnswerSelectedStory | None = None
    answer: AskAnswerBody
    changes: AskAnswerChanges
    citations: list[AskAnswerCitation] = Field(default_factory=list)
    evidence: AskAnswerEvidence
    fallback: AskAnswerFallback


class AskPageRequest(BaseModel):
    query: str = ""
    watchlist_id: str | None = Field(default=None, min_length=1)
    story_id: str | None = Field(default=None, min_length=1)
    topic_key: str | None = Field(default=None, min_length=1)
    top_k: int = Field(default=6, ge=1, le=20)
    mode: Literal["keyword", "semantic", "hybrid"] = "keyword"
    filters: dict[str, Any] = Field(default_factory=dict)


class AskPageContext(BaseModel):
    watchlist_id: str | None = None
    watchlist_name: str | None = None
    story_id: str | None = None
    selected_story_id: str | None = None
    story_headline: str | None = None
    topic_key: str | None = None
    topic_label: str | None = None
    selection_basis: Literal[
        "requested_story_id",
        "query_match",
        "suggested_story_id",
        "first_story",
        "none",
    ] = "none"
    mode: Literal["keyword", "semantic", "hybrid"]
    filters: dict[str, Any] = Field(default_factory=dict)
    briefing_available: bool


class AskPageResponse(BaseModel):
    question: str
    mode: Literal["keyword", "semantic", "hybrid"]
    top_k: int
    context: AskPageContext
    answer_state: Literal[
        "briefing_grounded",
        "missing_context",
        "briefing_unavailable",
        "no_confident_answer",
    ]
    answer_headline: str | None = None
    answer_summary: str | None = None
    answer_reason: str | None = None
    answer_confidence: Literal["grounded", "limited"]
    story_change_summary: str | None = None
    story_page: WatchlistBriefingPageResponse | None = None
    retrieval: RetrievalSearchResponse | None = None
    citations: list[AskAnswerCitation] = Field(default_factory=list)
    fallback_reason: str | None = None
    fallback_next_step: str | None = None
    fallback_actions: list[AskAnswerFallbackAction] = Field(default_factory=list)


@router.post("/search", response_model=RetrievalSearchResponse)
def retrieval_search(
    payload: RetrievalSearchRequest,
    db: Session = Depends(get_db),
) -> RetrievalSearchResponse | JSONResponse:
    service = RetrievalService(db)
    try:
        result = service.search(
            query=payload.query, top_k=payload.top_k, mode=payload.mode, filters=payload.filters
        )
    except ApiServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    return RetrievalSearchResponse(**result)


@router.post("/answer", response_model=AskAnswerResponse)
def retrieval_answer(
    payload: AskAnswerRequest,
    db: Session = Depends(get_db),
) -> AskAnswerResponse | JSONResponse:
    service = RetrievalService(db)
    try:
        result = service.answer(
            query=payload.query,
            watchlist_id=payload.watchlist_id,
            story_id=payload.story_id,
            top_k=payload.top_k,
            mode=payload.mode,
            filters=payload.filters,
        )
    except ApiServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    return AskAnswerResponse(**result)


@router.post("/answer/page", response_model=AskPageResponse)
def retrieval_answer_page(
    payload: AskPageRequest,
    db: Session = Depends(get_db),
) -> AskPageResponse | JSONResponse:
    service = RetrievalService(db)
    try:
        result = service.answer_page(
            query=payload.query,
            watchlist_id=payload.watchlist_id,
            story_id=payload.story_id,
            topic_key=payload.topic_key,
            top_k=payload.top_k,
            mode=payload.mode,
            filters=payload.filters,
        )
    except ApiServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    return AskPageResponse(**result)
