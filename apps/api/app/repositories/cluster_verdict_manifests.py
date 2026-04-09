from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ClusterVerdictManifest


class ClusterVerdictManifestsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_batch_id(self, *, consumption_batch_id: uuid.UUID) -> ClusterVerdictManifest | None:
        stmt = select(ClusterVerdictManifest).where(
            ClusterVerdictManifest.consumption_batch_id == consumption_batch_id
        )
        return self.db.scalar(stmt)

    def upsert_for_batch(
        self,
        *,
        consumption_batch_id: uuid.UUID,
        window_id: str,
        status: str,
        manifest_json: dict[str, object],
        source_item_count: int,
        cluster_count: int,
        singleton_count: int,
        summary_markdown: str | None,
    ) -> ClusterVerdictManifest:
        instance = self.get_by_batch_id(consumption_batch_id=consumption_batch_id)
        if instance is None:
            instance = ClusterVerdictManifest(
                consumption_batch_id=consumption_batch_id,
                window_id=window_id,
            )
            self.db.add(instance)
        instance.window_id = window_id
        instance.status = status
        instance.manifest_json = manifest_json
        instance.source_item_count = source_item_count
        instance.cluster_count = cluster_count
        instance.singleton_count = singleton_count
        instance.summary_markdown = summary_markdown
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
