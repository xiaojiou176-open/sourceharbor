from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class PublishedReaderDocument(Base):
    __tablename__ = "published_reader_documents"
    __table_args__ = (
        CheckConstraint(
            "materialization_mode IN ('merge_then_polish', 'polish_only', 'repair_patch', 'repair_section', 'repair_cluster')",
            name="published_reader_documents_materialization_mode_check",
        ),
        CheckConstraint("version >= 1", name="published_reader_documents_version_check"),
        CheckConstraint(
            "source_item_count >= 0", name="published_reader_documents_source_item_count_check"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stable_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    window_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    topic_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    reader_output_locale: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    reader_style_profile: Mapped[str] = mapped_column(
        String(64), nullable=False, default="briefing"
    )
    materialization_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    published_with_gap: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumption_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumption_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cluster_verdict_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cluster_verdict_manifests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supersedes_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("published_reader_documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    warning_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    coverage_ledger_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    traceability_pack_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    source_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    sections_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    repair_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    batch = relationship("ConsumptionBatch")
    manifest = relationship("ClusterVerdictManifest")
    supersedes_document = relationship(
        "PublishedReaderDocument",
        remote_side=lambda: PublishedReaderDocument.id,
        foreign_keys=[supersedes_document_id],
    )
