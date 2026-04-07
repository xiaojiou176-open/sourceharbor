from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "source_type",
            "source_value",
            name="uq_subscriptions_platform_source",
        ),
        CheckConstraint(
            "adapter_type IN ('rsshub_route', 'rss_generic')",
            name="subscriptions_adapter_type_check",
        ),
        CheckConstraint(
            "category IN ('tech', 'creator', 'macro', 'ops', 'misc')",
            name="subscriptions_category_check",
        ),
        CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="subscriptions_priority_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    adapter_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="rsshub_route", index=True
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    rsshub_route: Mapped[str] = mapped_column(String(1024), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="misc", index=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ingest_events = relationship(
        "IngestEvent",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
