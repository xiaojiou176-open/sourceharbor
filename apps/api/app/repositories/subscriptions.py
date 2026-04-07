from __future__ import annotations

import json
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import Subscription


class SubscriptionsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        *,
        platform: str | None = None,
        category: str | None = None,
        enabled_only: bool = False,
    ) -> list[Subscription]:
        stmt = select(Subscription)
        if platform is not None:
            stmt = stmt.where(Subscription.platform == platform)
        if category is not None:
            stmt = stmt.where(Subscription.category == category)
        if enabled_only:
            stmt = stmt.where(Subscription.enabled.is_(True))
        stmt = stmt.order_by(Subscription.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def upsert(
        self,
        *,
        platform: str,
        source_type: str,
        source_value: str,
        adapter_type: str,
        source_url: str | None,
        rsshub_route: str,
        category: str,
        tags: list[str],
        priority: int,
        enabled: bool,
    ) -> tuple[Subscription, bool]:
        dialect_name = (self.db.bind.dialect.name if self.db.bind is not None else "").lower()
        if dialect_name == "postgresql":
            row = (
                self.db.execute(
                    text(
                        """
                    INSERT INTO subscriptions (
                        id,
                        platform,
                        source_type,
                        source_value,
                        adapter_type,
                        source_url,
                        rsshub_route,
                        category,
                        tags,
                        priority,
                        enabled,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        CAST(:id AS UUID),
                        :platform,
                        :source_type,
                        :source_value,
                        :adapter_type,
                        :source_url,
                        :rsshub_route,
                        :category,
                        CAST(:tags AS JSONB),
                        :priority,
                        :enabled,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (platform, source_type, source_value)
                    DO UPDATE SET
                        adapter_type = EXCLUDED.adapter_type,
                        source_url = EXCLUDED.source_url,
                        rsshub_route = EXCLUDED.rsshub_route,
                        category = EXCLUDED.category,
                        tags = EXCLUDED.tags,
                        priority = EXCLUDED.priority,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    RETURNING id, (xmax = 0) AS created
                    """
                    ),
                    {
                        "platform": platform,
                        "id": str(uuid.uuid4()),
                        "source_type": source_type,
                        "source_value": source_value,
                        "adapter_type": adapter_type,
                        "source_url": source_url,
                        "rsshub_route": rsshub_route,
                        "category": category,
                        "tags": json.dumps(tags, ensure_ascii=False),
                        "priority": priority,
                        "enabled": enabled,
                    },
                )
                .mappings()
                .one()
            )
            subscription_id = row["id"]
            created = bool(row["created"])
            self.db.commit()
            existing = self.db.get(Subscription, subscription_id)
            if existing is None:
                raise RuntimeError("failed to load subscription after upsert")
            self.db.refresh(existing)
            return existing, created

        stmt = select(Subscription).where(
            Subscription.platform == platform,
            Subscription.source_type == source_type,
            Subscription.source_value == source_value,
        )
        existing = self.db.scalar(stmt)
        created = existing is None

        if existing is None:
            existing = Subscription(
                platform=platform,
                source_type=source_type,
                source_value=source_value,
                adapter_type=adapter_type,
                source_url=source_url,
                rsshub_route=rsshub_route,
                category=category,
                tags=tags,
                priority=priority,
                enabled=enabled,
            )
            self.db.add(existing)
        else:
            existing.adapter_type = adapter_type
            existing.source_url = source_url
            existing.rsshub_route = rsshub_route
            existing.category = category
            existing.tags = tags
            existing.priority = priority
            existing.enabled = enabled

        self.db.commit()
        self.db.refresh(existing)
        return existing, created

    def batch_update_category(
        self,
        *,
        ids: list[uuid.UUID],
        category: str,
    ) -> int:
        if not ids:
            return 0
        stmt = select(Subscription).where(Subscription.id.in_(ids))
        rows = list(self.db.scalars(stmt).all())
        for row in rows:
            row.category = category
        self.db.commit()
        return len(rows)

    def get(self, subscription_id: uuid.UUID) -> Subscription | None:
        return self.db.get(Subscription, subscription_id)

    def delete(self, subscription_id: uuid.UUID) -> bool:
        instance = self.db.get(Subscription, subscription_id)
        if instance is None:
            return False
        self.db.delete(instance)
        self.db.commit()
        return True
