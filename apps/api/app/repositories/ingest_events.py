from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import IngestEvent


class IngestEventsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        subscription_id: uuid.UUID,
        feed_guid: str | None,
        feed_link: str | None,
        entry_hash: str,
        video_id: uuid.UUID,
    ) -> IngestEvent:
        instance = IngestEvent(
            subscription_id=subscription_id,
            feed_guid=feed_guid,
            feed_link=feed_link,
            entry_hash=entry_hash,
            video_id=video_id,
        )
        self.db.add(instance)
        self.db.flush()
        return instance

    def list_recent_video_ids(self, *, subscription_id: uuid.UUID, limit: int) -> list[uuid.UUID]:
        stmt = (
            select(IngestEvent.video_id)
            .where(IngestEvent.subscription_id == subscription_id)
            .order_by(IngestEvent.created_at.desc())
            .limit(limit)
        )
        raw_ids = [row[0] for row in self.db.execute(stmt).all()]
        return list(dict.fromkeys(raw_ids))
