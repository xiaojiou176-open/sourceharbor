from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import IngestRun


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IngestRunsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        subscription_id: uuid.UUID | None,
        platform: str | None,
        max_new_videos: int,
        filters_json: dict[str, object],
        requested_by: str | None,
        requested_trace_id: str | None,
    ) -> IngestRun:
        instance = IngestRun(
            subscription_id=subscription_id,
            platform=platform,
            max_new_videos=max_new_videos,
            status="queued",
            filters_json=filters_json,
            requested_by=requested_by,
            requested_trace_id=requested_trace_id,
        )
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def mark_workflow_started(
        self,
        *,
        run_id: uuid.UUID,
        workflow_id: str,
        status: str = "queued",
    ) -> IngestRun:
        instance = self.db.get(IngestRun, run_id)
        if instance is None:
            raise ValueError(f"ingest run not found: {run_id}")
        instance.workflow_id = workflow_id
        instance.status = status
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def mark_failed(self, *, run_id: uuid.UUID, error_message: str) -> IngestRun:
        instance = self.db.get(IngestRun, run_id)
        if instance is None:
            raise ValueError(f"ingest run not found: {run_id}")
        instance.status = "failed"
        instance.error_message = error_message
        instance.completed_at = _utc_now()
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def get_with_items(self, *, run_id: uuid.UUID) -> IngestRun | None:
        stmt = (
            select(IngestRun).options(selectinload(IngestRun.items)).where(IngestRun.id == run_id)
        )
        return self.db.scalar(stmt)

    def list_recent(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        platform: str | None = None,
    ) -> list[IngestRun]:
        stmt = select(IngestRun)
        if status is not None:
            stmt = stmt.where(IngestRun.status == status)
        if platform is not None:
            stmt = stmt.where(IngestRun.platform == platform)
        stmt = stmt.order_by(IngestRun.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())
