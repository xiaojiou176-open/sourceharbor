from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services.knowledge import KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeCardResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    video_id: uuid.UUID
    card_type: str
    source_section: str
    title: str | None = None
    body: str
    order_index: int
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


@router.get("/cards", response_model=list[KnowledgeCardResponse])
def list_knowledge_cards(
    job_id: uuid.UUID | None = Query(default=None),
    video_id: uuid.UUID | None = Query(default=None),
    card_type: str | None = Query(default=None),
    topic_key: str | None = Query(default=None),
    claim_kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    service = KnowledgeService(db)
    rows = service.list_cards(
        job_id=job_id,
        video_id=video_id,
        card_type=card_type,
        topic_key=topic_key,
        claim_kind=claim_kind,
        limit=limit,
    )
    return [
        KnowledgeCardResponse(
            id=row.id,
            job_id=row.job_id,
            video_id=row.video_id,
            card_type=row.card_type,
            source_section=row.source_section,
            title=row.title,
            body=row.body,
            order_index=row.ordinal,
            metadata_json=row.metadata_json if isinstance(row.metadata_json, dict) else {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]
