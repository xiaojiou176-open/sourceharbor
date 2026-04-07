from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class IngestEvent(Base):
    __tablename__ = "ingest_events"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "entry_hash",
            name="uq_ingest_events_subscription_entry_hash",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    feed_guid: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    feed_link: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subscription = relationship("Subscription", back_populates="ingest_events")
    video = relationship("Video", back_populates="ingest_events")
