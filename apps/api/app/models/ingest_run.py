from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class IngestRun(Base):
    __tablename__ = "ingest_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'skipped')",
            name="ingest_runs_status_check",
        ),
        CheckConstraint(
            "jobs_created >= 0 AND candidates_count >= 0 AND feeds_polled >= 0 "
            "AND entries_fetched >= 0 AND entries_normalized >= 0 "
            "AND ingest_events_created >= 0 AND ingest_event_duplicates >= 0 "
            "AND job_duplicates >= 0",
            name="ingest_runs_non_negative_counts_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    platform: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    max_new_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filters_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    jobs_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    feeds_polled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entries_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entries_normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingest_events_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingest_event_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    job_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list[IngestRunItem]] = relationship(
        lambda: IngestRunItem,
        back_populates="ingest_run",
        cascade="all, delete-orphan",
    )


class IngestRunItem(Base):
    __tablename__ = "ingest_run_items"
    __table_args__ = (
        CheckConstraint(
            "item_status IN ('pending_consume', 'batch_assigned', 'closed', 'deduped', 'skipped')",
            name="ingest_run_items_item_status_check",
        ),
        CheckConstraint(
            "content_type IN ('video', 'article')",
            name="ingest_run_items_content_type_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingest_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    ingest_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    video_uid: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pipeline_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="video")
    item_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_consume")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ingest_run: Mapped[IngestRun] = relationship(lambda: IngestRun, back_populates="items")
