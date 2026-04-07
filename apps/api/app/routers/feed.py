from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas.feed import DigestFeedItem, DigestFeedResponse
from ..security import require_write_access, sanitize_exception_detail
from ..services.feed import FeedService

router = APIRouter(prefix="/api/v1/feed", tags=["feed"])


class FeedFeedbackResponse(BaseModel):
    job_id: uuid.UUID
    saved: bool
    feedback_label: str | None = None
    exists: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FeedFeedbackUpdateRequest(BaseModel):
    job_id: uuid.UUID
    saved: bool = False
    feedback_label: str | None = None


@router.get("/digests", response_model=DigestFeedResponse)
def list_digests(
    source: str | None = Query(default=None),
    category: str | None = Query(default=None),
    feedback: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    subscription_id: uuid.UUID | None = Query(default=None, alias="sub"),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = FeedService(db)
    payload = service.list_digest_feed(
        source=source,
        category=category,
        feedback=feedback,
        sort=sort,
        subscription_id=str(subscription_id) if subscription_id is not None else None,
        limit=limit,
        cursor=cursor,
        since=since,
    )
    return DigestFeedResponse(
        items=[DigestFeedItem(**item) for item in payload.get("items", [])],
        has_more=bool(payload.get("has_more", False)),
        next_cursor=payload.get("next_cursor"),
    )


@router.get("/feedback", response_model=FeedFeedbackResponse)
def get_feedback(
    job_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    service = FeedService(db)
    return FeedFeedbackResponse(**service.get_feedback(job_id=job_id))


@router.put(
    "/feedback",
    response_model=FeedFeedbackResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_write_access)],
)
def put_feedback(payload: FeedFeedbackUpdateRequest, db: Session = Depends(get_db)):
    service = FeedService(db)
    try:
        result = service.set_feedback(
            job_id=payload.job_id,
            saved=payload.saved,
            feedback_label=payload.feedback_label,
        )
    except ValueError as exc:
        detail = sanitize_exception_detail(exc)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return FeedFeedbackResponse(**result)
