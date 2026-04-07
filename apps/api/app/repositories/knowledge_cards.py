from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import KnowledgeCard


class KnowledgeCardsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        job_id: uuid.UUID | None = None,
        video_id: uuid.UUID | None = None,
        card_type: str | None = None,
        limit: int = 50,
    ) -> list[KnowledgeCard]:
        stmt = select(KnowledgeCard)
        if job_id is not None:
            stmt = stmt.where(KnowledgeCard.job_id == job_id)
        if video_id is not None:
            stmt = stmt.where(KnowledgeCard.video_id == video_id)
        if card_type is not None:
            stmt = stmt.where(KnowledgeCard.card_type == card_type)
        stmt = stmt.order_by(KnowledgeCard.created_at.desc(), KnowledgeCard.ordinal.asc()).limit(
            limit
        )
        return list(self.db.scalars(stmt).all())
