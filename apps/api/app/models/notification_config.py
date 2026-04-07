from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NotificationConfig(Base):
    __tablename__ = "notification_configs"
    __table_args__ = (
        CheckConstraint("singleton_key = 1", name="notification_configs_singleton_key_check"),
        CheckConstraint(
            "daily_digest_hour_utc IS NULL OR (daily_digest_hour_utc >= 0 AND daily_digest_hour_utc <= 23)",
            name="notification_configs_daily_digest_hour_utc_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_key: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        unique=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    to_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_digest_hour_utc: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    failure_alert_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    category_rules: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
