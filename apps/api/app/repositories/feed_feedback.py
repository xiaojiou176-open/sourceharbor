from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import FeedFeedback


class FeedFeedbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_job_id(self, *, job_id: uuid.UUID) -> FeedFeedback | None:
        stmt = select(FeedFeedback).where(FeedFeedback.job_id == job_id)
        return self.db.scalar(stmt)

    def upsert(
        self,
        *,
        job_id: uuid.UUID,
        saved: bool,
        feedback_label: str | None,
    ) -> FeedFeedback:
        row = self.get_by_job_id(job_id=job_id)
        if row is None:
            row = FeedFeedback(job_id=job_id, saved=saved, feedback_label=feedback_label)
            self.db.add(row)
        else:
            row.saved = saved
            row.feedback_label = feedback_label
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
