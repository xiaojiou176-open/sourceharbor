from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ConsumptionBatch(Base):
    __tablename__ = "consumption_batches"
    __table_args__ = (
        CheckConstraint(
            "trigger_mode IN ('manual', 'auto')",
            name="consumption_batches_trigger_mode_check",
        ),
        CheckConstraint(
            "status IN ('frozen', 'judged', 'materialized', 'closed', 'failed')",
            name="consumption_batches_status_check",
        ),
        CheckConstraint(
            "source_item_count >= 0 AND processed_job_count >= 0 "
            "AND succeeded_job_count >= 0 AND failed_job_count >= 0",
            name="consumption_batches_non_negative_counts_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    trigger_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="frozen", index=True)
    window_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    timezone_name: Mapped[str] = mapped_column(String(128), nullable=False)
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filters_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    base_published_doc_versions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded_job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_job_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    process_summary_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    materialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    items: Mapped[list[ConsumptionBatchItem]] = relationship(
        lambda: ConsumptionBatchItem,
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class ConsumptionBatchItem(Base):
    __tablename__ = "consumption_batch_items"
    __table_args__ = (
        CheckConstraint(
            "source_origin IN ('subscription_tracked', 'manual_injected')",
            name="consumption_batch_items_source_origin_check",
        ),
        CheckConstraint(
            "content_type IN ('video', 'article')",
            name="consumption_batch_items_content_type_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consumption_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumption_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ingest_run_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_run_items.id", ondelete="SET NULL"),
        nullable=True,
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
        index=True,
    )
    ingest_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    video_uid: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pipeline_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="video")
    source_origin: Mapped[str] = mapped_column(
        String(32), nullable=False, default="subscription_tracked"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    batch: Mapped[ConsumptionBatch] = relationship(lambda: ConsumptionBatch, back_populates="items")
