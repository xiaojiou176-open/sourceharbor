from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import require_write_access
from ..services.watchlists import WatchlistsService

router = APIRouter(prefix="/api/v1/watchlists", tags=["watchlists"])


class WatchlistResponse(BaseModel):
    id: str
    name: str
    matcher_type: str
    matcher_value: str
    delivery_channel: str
    enabled: bool
    created_at: str
    updated_at: str


class WatchlistUpsertRequest(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    matcher_type: str = Field(pattern="^(topic_key|claim_kind|platform|source_match)$")
    matcher_value: str = Field(min_length=1, max_length=200)
    delivery_channel: str = Field(default="dashboard", pattern="^(dashboard|email)$")
    enabled: bool = True


class WatchlistTrendCard(BaseModel):
    card_id: str
    job_id: str
    video_id: str
    platform: str
    video_title: str | None = None
    source_url: str | None = None
    created_at: str
    card_type: str
    card_title: str | None = None
    card_body: str
    source_section: str
    topic_key: str | None = None
    topic_label: str | None = None
    claim_kind: str | None = None


class WatchlistTrendRun(BaseModel):
    job_id: str
    video_id: str
    platform: str
    title: str
    source_url: str | None = None
    created_at: str
    matched_card_count: int
    cards: list[WatchlistTrendCard]
    topics: list[str]
    claim_kinds: list[str]
    added_topics: list[str]
    removed_topics: list[str]
    added_claim_kinds: list[str]
    removed_claim_kinds: list[str]


class WatchlistTrendSummary(BaseModel):
    recent_runs: int
    matched_cards: int
    matcher_type: str
    matcher_value: str


class WatchlistMergedStory(BaseModel):
    id: str
    story_key: str
    headline: str
    topic_key: str | None = None
    topic_label: str | None = None
    latest_created_at: str
    matched_card_count: int
    platforms: list[str]
    claim_kinds: list[str]
    source_urls: list[str]
    run_ids: list[str]
    cards: list[WatchlistTrendCard]


class WatchlistTrendResponse(BaseModel):
    watchlist: WatchlistResponse
    summary: WatchlistTrendSummary
    timeline: list[WatchlistTrendRun]
    merged_stories: list[WatchlistMergedStory]


class WatchlistBriefingSignal(BaseModel):
    story_key: str
    headline: str
    matched_card_count: int
    latest_run_job_id: str | None = None
    reason: str


class WatchlistBriefingSummary(BaseModel):
    overview: str
    source_count: int
    run_count: int
    story_count: int
    matched_cards: int
    primary_story_headline: str | None = None
    signals: list[WatchlistBriefingSignal] = Field(default_factory=list)


class WatchlistBriefingCompare(BaseModel):
    job_id: str
    has_previous: bool
    previous_job_id: str | None = None
    changed: bool
    added_lines: int
    removed_lines: int
    diff_excerpt: str | None = None
    compare_route: str


class WatchlistBriefingDifferences(BaseModel):
    latest_job_id: str | None = None
    previous_job_id: str | None = None
    added_topics: list[str] = Field(default_factory=list)
    removed_topics: list[str] = Field(default_factory=list)
    added_claim_kinds: list[str] = Field(default_factory=list)
    removed_claim_kinds: list[str] = Field(default_factory=list)
    new_story_keys: list[str] = Field(default_factory=list)
    removed_story_keys: list[str] = Field(default_factory=list)
    compare: WatchlistBriefingCompare | None = None


class WatchlistBriefingRoutes(BaseModel):
    watchlist_trend: str
    briefing: str | None = None
    ask: str | None = None
    job_compare: str | None = None
    job_bundle: str | None = None
    job_knowledge_cards: str | None = None


class WatchlistBriefingStoryEvidence(BaseModel):
    story_id: str
    story_key: str
    headline: str
    topic_key: str | None = None
    topic_label: str | None = None
    source_count: int
    run_count: int
    matched_card_count: int
    platforms: list[str]
    claim_kinds: list[str]
    source_urls: list[str]
    latest_run_job_id: str | None = None
    evidence_cards: list[WatchlistTrendCard]
    routes: WatchlistBriefingRoutes


class WatchlistBriefingRunEvidence(BaseModel):
    job_id: str
    video_id: str
    platform: str
    title: str
    source_url: str | None = None
    created_at: str
    matched_card_count: int
    routes: WatchlistBriefingRoutes


class WatchlistBriefingEvidence(BaseModel):
    suggested_story_id: str | None = None
    stories: list[WatchlistBriefingStoryEvidence]
    featured_runs: list[WatchlistBriefingRunEvidence]


class WatchlistBriefingSelection(BaseModel):
    selected_story_id: str | None = None
    selection_basis: Literal[
        "requested_story_id",
        "query_match",
        "suggested_story_id",
        "first_story",
        "none",
    ] = "none"
    story: WatchlistBriefingStoryEvidence | None = None


class WatchlistBriefingResponse(BaseModel):
    watchlist: WatchlistResponse
    summary: WatchlistBriefingSummary
    differences: WatchlistBriefingDifferences
    evidence: WatchlistBriefingEvidence
    selection: WatchlistBriefingSelection | None = None


class WatchlistBriefingPageContext(BaseModel):
    watchlist_id: str
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
    question_seed: str | None = None


class WatchlistBriefingPageCitation(BaseModel):
    kind: Literal["briefing_story", "briefing_card", "job_compare"]
    label: str
    snippet: str
    source_url: str | None = None
    job_id: str | None = None
    route: str | None = None
    route_label: str | None = None


class WatchlistBriefingPageFallbackAction(BaseModel):
    kind: Literal["open_briefing", "open_story", "open_job", "open_knowledge", "open_trend"]
    label: str
    route: str | None = None


class WatchlistBriefingPageResponse(BaseModel):
    context: WatchlistBriefingPageContext
    briefing: WatchlistBriefingResponse
    selected_story: WatchlistBriefingStoryEvidence | None = None
    story_change_summary: str | None = None
    citations: list[WatchlistBriefingPageCitation] = Field(default_factory=list)
    routes: WatchlistBriefingRoutes
    ask_route: str | None = None
    compare_route: str | None = None
    fallback_reason: str | None = None
    fallback_next_step: str | None = None
    fallback_actions: list[WatchlistBriefingPageFallbackAction] = Field(default_factory=list)


@router.get("", response_model=list[WatchlistResponse])
def list_watchlists(db: Session = Depends(get_db)):
    service = WatchlistsService(db)
    return [WatchlistResponse(**item) for item in service.list_watchlists()]


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_write_access)],
)
def upsert_watchlist(payload: WatchlistUpsertRequest, db: Session = Depends(get_db)):
    service = WatchlistsService(db)
    try:
        item = service.upsert_watchlist(
            watchlist_id=payload.id,
            name=payload.name,
            matcher_type=payload.matcher_type,
            matcher_value=payload.matcher_value,
            delivery_channel=payload.delivery_channel,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistResponse(**item)


@router.delete(
    "/{watchlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_write_access)],
)
def delete_watchlist(watchlist_id: str, db: Session = Depends(get_db)):
    service = WatchlistsService(db)
    deleted = service.delete_watchlist(watchlist_id=watchlist_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return


@router.get("/{watchlist_id}/trend", response_model=WatchlistTrendResponse)
def get_watchlist_trend(
    watchlist_id: str,
    limit_runs: int = Query(default=3, ge=1, le=10),
    limit_cards: int = Query(default=18, ge=1, le=60),
    db: Session = Depends(get_db),
):
    service = WatchlistsService(db)
    payload = service.get_watchlist_trend(
        watchlist_id=watchlist_id,
        limit_runs=limit_runs,
        limit_cards=limit_cards,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return WatchlistTrendResponse(**payload)


@router.get("/{watchlist_id}/briefing", response_model=WatchlistBriefingResponse)
def get_watchlist_briefing(
    watchlist_id: str,
    limit_runs: int = Query(default=4, ge=1, le=10),
    limit_cards: int = Query(default=18, ge=1, le=60),
    limit_stories: int = Query(default=4, ge=1, le=12),
    limit_evidence_per_story: int = Query(default=3, ge=1, le=8),
    db: Session = Depends(get_db),
):
    service = WatchlistsService(db)
    payload = service.get_watchlist_briefing(
        watchlist_id=watchlist_id,
        limit_runs=limit_runs,
        limit_cards=limit_cards,
        limit_stories=limit_stories,
        limit_evidence_per_story=limit_evidence_per_story,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return WatchlistBriefingResponse(**payload)


@router.get("/{watchlist_id}/briefing/page", response_model=WatchlistBriefingPageResponse)
def get_watchlist_briefing_page(
    watchlist_id: str,
    story_id: str | None = Query(default=None, min_length=1),
    query: str | None = Query(default=None),
    limit_runs: int = Query(default=4, ge=1, le=10),
    limit_cards: int = Query(default=18, ge=1, le=60),
    limit_stories: int = Query(default=4, ge=1, le=12),
    limit_evidence_per_story: int = Query(default=3, ge=1, le=8),
    db: Session = Depends(get_db),
):
    service = WatchlistsService(db)
    payload = service.get_watchlist_briefing_page(
        watchlist_id=watchlist_id,
        story_id=story_id,
        query=query,
        limit_runs=limit_runs,
        limit_cards=limit_cards,
        limit_stories=limit_stories,
        limit_evidence_per_story=limit_evidence_per_story,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return WatchlistBriefingPageResponse(**payload)
