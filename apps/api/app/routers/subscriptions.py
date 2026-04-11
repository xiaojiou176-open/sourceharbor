from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import require_write_access, sanitize_exception_detail
from ..services import SubscriptionsService, VideosService
from ..services.manual_source_intake import ManualSourceIntakeService
from ..services.source_identity import build_identity_payload
from ..services.source_names import build_source_name_fallback, resolve_source_name
from ..services.subscription_templates import load_subscription_template_catalog
from ..services.subscriptions import (
    resolve_subscription_content_profile,
    resolve_subscription_support_tier,
)

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


class SubscriptionUpsertRequest(BaseModel):
    platform: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_value: str = Field(min_length=1)
    adapter_type: str = "rsshub_route"
    source_url: str | None = None
    rsshub_route: str | None = None
    category: str = "misc"
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    enabled: bool = True


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    platform: str
    source_type: str
    source_value: str
    source_name: str
    support_tier: str
    content_profile: str
    adapter_type: str = "rsshub_route"
    source_url: str | None = None
    rsshub_route: str
    creator_display_name: str | None = None
    creator_handle: str | None = None
    source_homepage_url: str | None = None
    avatar_url: str | None = None
    avatar_label: str | None = None
    thumbnail_url: str | None = None
    source_universe_label: str | None = None
    identity_status: str = "derived_identity"
    category: str = "misc"
    tags: list[str] = Field(default_factory=list)
    priority: int = 50
    enabled: bool
    created_at: datetime
    updated_at: datetime


def _to_subscription_response(row) -> SubscriptionResponse:
    source_type = str(getattr(row, "source_type", "") or "")
    source_value = str(getattr(row, "source_value", "") or "")
    platform = str(getattr(row, "platform", "") or "")
    adapter_type = getattr(row, "adapter_type", "rsshub_route")
    explicit_source_name = str(getattr(row, "source_name", "") or "").strip()
    priority_value = getattr(row, "priority", None)
    resolved_priority = 50 if priority_value is None else int(priority_value)
    resolved_source_name = resolve_source_name(
        source_type=source_type,
        source_value=source_value,
        fallback=explicit_source_name
        or build_source_name_fallback(
            platform=platform,
            source_type=source_type,
            source_value=source_value,
            source_url=getattr(row, "source_url", None),
            rsshub_route=getattr(row, "rsshub_route", None),
        ),
    )
    creator_handle = source_value if source_value.startswith("@") else None
    identity = build_identity_payload(
        platform=platform,
        display_name=resolved_source_name,
        creator_handle=creator_handle,
        source_homepage_url=getattr(row, "source_url", None) or getattr(row, "rsshub_route", None),
        source_url=getattr(row, "source_url", None),
        source_universe_label=resolved_source_name,
    )
    return SubscriptionResponse(
        id=row.id,
        platform=platform,
        source_type=source_type,
        source_value=source_value,
        source_name=resolved_source_name,
        support_tier=resolve_subscription_support_tier(
            platform=platform,
            source_type=source_type,
        ),
        content_profile=resolve_subscription_content_profile(
            platform=platform,
            source_type=source_type,
            adapter_type=adapter_type,
        ),
        adapter_type=adapter_type,
        source_url=getattr(row, "source_url", None),
        rsshub_route=row.rsshub_route,
        creator_display_name=identity.creator_display_name,
        creator_handle=identity.creator_handle,
        source_homepage_url=identity.source_homepage_url,
        avatar_url=identity.avatar_url,
        avatar_label=identity.avatar_label,
        thumbnail_url=identity.thumbnail_url,
        source_universe_label=identity.source_universe_label,
        identity_status=identity.identity_status,
        category=getattr(row, "category", "misc"),
        tags=list(getattr(row, "tags", []) or []),
        priority=resolved_priority,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SubscriptionUpsertResponse(BaseModel):
    subscription: SubscriptionResponse
    created: bool


class SubscriptionTemplateSupportTier(BaseModel):
    id: str
    label: str
    description: str
    content_profile: str
    supports_video_pipeline: bool
    verification_status: str


class SubscriptionTemplate(BaseModel):
    id: str
    label: str
    description: str
    support_tier: str
    platform: str
    source_type: str
    adapter_type: str
    content_profile: str
    category: str | None = None
    source_value_placeholder: str | None = None
    source_url_placeholder: str | None = None
    rsshub_route_hint: str | None = None
    source_url_required: bool = False
    supports_video_pipeline: bool = False
    fill_now: str | None = None
    proof_boundary: str | None = None
    evidence_note: str | None = None


class SubscriptionTemplateCatalogResponse(BaseModel):
    support_tiers: list[SubscriptionTemplateSupportTier]
    templates: list[SubscriptionTemplate]


class ManualSourceIntakeRequest(BaseModel):
    raw_input: str = Field(min_length=1, max_length=20_000)
    category: str = "misc"
    tags: list[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    enabled: bool = True


class ManualSourceIntakeResult(BaseModel):
    line_number: int
    raw_input: str
    target_kind: Literal["subscription_source", "manual_source_item", "unsupported"]
    recommended_action: Literal["save_subscription", "add_to_today", "unsupported"]
    applied_action: Literal["save_subscription", "add_to_today"] | None = None
    status: Literal["created", "updated", "queued", "reused", "rejected"]
    platform: str | None = None
    source_type: str | None = None
    source_value: str | None = None
    source_url: str | None = None
    rsshub_route: str | None = None
    adapter_type: str | None = None
    content_profile: str | None = None
    support_tier: str | None = None
    display_name: str | None = None
    relation_kind: str | None = None
    matched_subscription_id: str | None = None
    matched_subscription_name: str | None = None
    matched_by: str | None = None
    match_confidence: str | None = None
    source_universe_label: str | None = None
    creator_display_name: str | None = None
    creator_handle: str | None = None
    thumbnail_url: str | None = None
    avatar_url: str | None = None
    avatar_label: str | None = None
    message: str
    subscription_id: str | None = None
    job_id: str | None = None


class ManualSourceIntakeResponse(BaseModel):
    processed_count: int
    created_subscriptions: int
    updated_subscriptions: int
    queued_manual_items: int
    reused_manual_items: int
    rejected_count: int
    results: list[ManualSourceIntakeResult]


class BatchUpdateCategoryRequest(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list)
    category: str = Field(min_length=1)


class BatchUpdateCategoryResponse(BaseModel):
    updated: int


@router.get("", response_model=list[SubscriptionResponse])
def list_subscriptions(
    platform: str | None = None,
    category: str | None = None,
    enabled_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    service = SubscriptionsService(db)
    rows = service.list_subscriptions(
        platform=platform, category=category, enabled_only=enabled_only
    )
    return [_to_subscription_response(row) for row in rows]


@router.get("/templates", response_model=SubscriptionTemplateCatalogResponse)
def get_subscription_templates():
    payload = load_subscription_template_catalog()
    return SubscriptionTemplateCatalogResponse(**payload)


@router.post(
    "",
    response_model=SubscriptionUpsertResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_write_access)],
)
def upsert_subscription(payload: SubscriptionUpsertRequest, db: Session = Depends(get_db)):
    service = SubscriptionsService(db)
    try:
        row, created = service.upsert_subscription(
            platform=payload.platform,
            source_type=payload.source_type,
            source_value=payload.source_value,
            adapter_type=payload.adapter_type,
            source_url=payload.source_url,
            rsshub_route=payload.rsshub_route,
            category=payload.category,
            tags=payload.tags,
            priority=payload.priority,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc

    return SubscriptionUpsertResponse(
        subscription=_to_subscription_response(row),
        created=created,
    )


@router.post(
    "/manual-intake",
    response_model=ManualSourceIntakeResponse,
    dependencies=[Depends(require_write_access)],
)
async def submit_manual_source_intake(
    payload: ManualSourceIntakeRequest,
    db: Session = Depends(get_db),
):
    service = ManualSourceIntakeService(
        subscriptions_service=SubscriptionsService(db),
        videos_service=VideosService(db),
    )
    try:
        result = await service.submit(
            raw_input=payload.raw_input,
            category=payload.category,
            tags=payload.tags,
            priority=payload.priority,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc
    return ManualSourceIntakeResponse(**result)


@router.post(
    "/batch-update-category",
    response_model=BatchUpdateCategoryResponse,
    dependencies=[Depends(require_write_access)],
)
def batch_update_category(payload: BatchUpdateCategoryRequest, db: Session = Depends(get_db)):
    service = SubscriptionsService(db)
    try:
        updated = service.batch_update_category(ids=payload.ids, category=payload.category)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc
    return BatchUpdateCategoryResponse(updated=updated)


@router.delete(
    "/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_write_access)]
)
def delete_subscription(id: uuid.UUID, db: Session = Depends(get_db)):
    service = SubscriptionsService(db)
    deleted = service.delete_subscription(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="subscription not found")
