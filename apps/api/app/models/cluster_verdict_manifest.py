from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ClusterVerdictManifest(Base):
    __tablename__ = "cluster_verdict_manifests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'gap_detected')",
            name="cluster_verdict_manifests_status_check",
        ),
        CheckConstraint(
            "source_item_count >= 0 AND cluster_count >= 0 AND singleton_count >= 0",
            name="cluster_verdict_manifests_non_negative_counts_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consumption_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consumption_batches.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    window_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    manifest_json: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    source_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cluster_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    singleton_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
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
