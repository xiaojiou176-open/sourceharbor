from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "kind = 'video_digest_v1'",
            name="jobs_kind_check",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="jobs_status_check",
        ),
        CheckConstraint(
            "pipeline_final_status IS NULL OR pipeline_final_status IN ('succeeded', 'degraded', 'failed')",
            name="jobs_pipeline_final_status_check",
        ),
        CheckConstraint(
            "degradation_count IS NULL OR degradation_count >= 0",
            name="jobs_degradation_count_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_digest_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_root: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_final_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    degradation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    llm_gate_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hard_fail_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    overrides_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    video = relationship("Video", back_populates="jobs")
