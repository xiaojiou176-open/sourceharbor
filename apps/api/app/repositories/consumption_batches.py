from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from ..models import ConsumptionBatch, ConsumptionBatchItem, IngestRun, IngestRunItem


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ConsumptionBatchesRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_pending_items(
        self,
        *,
        subscription_id: uuid.UUID | None,
        platform: str | None,
    ) -> list[dict[str, Any]]:
        stmt: Select[tuple[IngestRunItem, IngestRun]] = (
            select(IngestRunItem, IngestRun)
            .join(IngestRun, IngestRun.id == IngestRunItem.ingest_run_id)
            .where(IngestRun.status == "succeeded")
            .where(IngestRunItem.item_status == "pending_consume")
            .order_by(IngestRunItem.created_at.asc())
        )
        if subscription_id is not None:
            stmt = stmt.where(IngestRunItem.subscription_id == subscription_id)
        if platform is not None:
            stmt = stmt.where(IngestRunItem.platform == platform)
        rows = self.db.execute(stmt).all()
        payload: list[dict[str, Any]] = []
        for item, run in rows:
            payload.append(
                {
                    "ingest_run_item_id": item.id,
                    "ingest_run_id": run.id,
                    "subscription_id": item.subscription_id,
                    "video_id": item.video_id,
                    "job_id": item.job_id,
                    "ingest_event_id": item.ingest_event_id,
                    "platform": item.platform,
                    "video_uid": item.video_uid,
                    "source_url": item.source_url,
                    "title": item.title,
                    "published_at": item.published_at,
                    "entry_hash": item.entry_hash,
                    "pipeline_mode": item.pipeline_mode,
                    "content_type": item.content_type,
                    "item_status": item.item_status,
                    "discovered_at": item.created_at,
                    "filters_json": run.filters_json if isinstance(run.filters_json, dict) else {},
                }
            )
        return payload

    def create_batch(
        self,
        *,
        trigger_mode: str,
        window_id: str,
        timezone_name: str,
        cutoff_at: datetime,
        requested_by: str | None,
        requested_trace_id: str | None,
        filters_json: dict[str, object],
        base_published_doc_versions: list[str],
        items: Sequence[dict[str, Any]],
    ) -> ConsumptionBatch:
        batch = ConsumptionBatch(
            trigger_mode=trigger_mode,
            status="frozen",
            window_id=window_id,
            timezone_name=timezone_name,
            cutoff_at=cutoff_at,
            requested_by=requested_by,
            requested_trace_id=requested_trace_id,
            filters_json=filters_json,
            base_published_doc_versions=base_published_doc_versions,
            source_item_count=len(items),
        )
        self.db.add(batch)
        self.db.flush()

        for item in items:
            batch_item = ConsumptionBatchItem(
                consumption_batch_id=batch.id,
                ingest_run_item_id=item.get("ingest_run_item_id"),
                subscription_id=item.get("subscription_id"),
                video_id=item.get("video_id"),
                job_id=item.get("job_id"),
                ingest_event_id=item.get("ingest_event_id"),
                platform=str(item.get("platform") or ""),
                video_uid=str(item.get("video_uid") or ""),
                source_url=str(item.get("source_url") or ""),
                title=item.get("title"),
                published_at=item.get("published_at"),
                source_effective_at=item["source_effective_at"],
                discovered_at=item["discovered_at"],
                entry_hash=item.get("entry_hash"),
                pipeline_mode=item.get("pipeline_mode"),
                content_type=str(item.get("content_type") or "video"),
                source_origin=str(item.get("source_origin") or "subscription_tracked"),
            )
            self.db.add(batch_item)
            ingest_run_item_id = item.get("ingest_run_item_id")
            if isinstance(ingest_run_item_id, uuid.UUID):
                run_item = self.db.get(IngestRunItem, ingest_run_item_id)
                if run_item is not None:
                    run_item.item_status = "batch_assigned"
                    self.db.add(run_item)

        self.db.commit()
        self.db.refresh(batch)
        return batch

    def mark_workflow_started(
        self,
        *,
        batch_id: uuid.UUID,
        workflow_id: str,
    ) -> ConsumptionBatch:
        batch = self.db.get(ConsumptionBatch, batch_id)
        if batch is None:
            raise ValueError(f"consumption batch not found: {batch_id}")
        batch.workflow_id = workflow_id
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def mark_start_failed(
        self,
        *,
        batch_id: uuid.UUID,
        error_message: str,
    ) -> ConsumptionBatch:
        return self.mark_failed(batch_id=batch_id, error_message=error_message)

    def mark_failed(
        self,
        *,
        batch_id: uuid.UUID,
        error_message: str,
    ) -> ConsumptionBatch:
        batch = self.db.get(ConsumptionBatch, batch_id)
        if batch is None:
            raise ValueError(f"consumption batch not found: {batch_id}")
        batch.status = "failed"
        batch.error_message = error_message
        batch.closed_at = _utc_now()
        for item in batch.items:
            if item.ingest_run_item_id is None:
                continue
            run_item = self.db.get(IngestRunItem, item.ingest_run_item_id)
            if run_item is not None:
                run_item.item_status = "pending_consume"
                self.db.add(run_item)
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def mark_materialized(
        self,
        *,
        batch_id: uuid.UUID,
        process_results: Sequence[dict[str, Any]],
    ) -> ConsumptionBatch:
        batch = self.db.get(ConsumptionBatch, batch_id)
        if batch is None:
            raise ValueError(f"consumption batch not found: {batch_id}")
        processed_count = len(process_results)
        succeeded_count = sum(1 for item in process_results if bool(item.get("ok")))
        failed_count = processed_count - succeeded_count
        batch.status = "materialized"
        batch.processed_job_count = processed_count
        batch.succeeded_job_count = succeeded_count
        batch.failed_job_count = failed_count
        batch.process_summary_json = {"process_results": list(process_results)}
        batch.materialized_at = _utc_now()
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def mark_judged(
        self,
        *,
        batch_id: uuid.UUID,
        manifest_id: uuid.UUID,
        manifest_status: str,
        cluster_count: int,
        singleton_count: int,
    ) -> ConsumptionBatch:
        batch = self.db.get(ConsumptionBatch, batch_id)
        if batch is None:
            raise ValueError(f"consumption batch not found: {batch_id}")
        batch.status = "judged"
        batch.judged_at = _utc_now()
        summary = dict(batch.process_summary_json or {})
        summary.update(
            {
                "reader_stage": "judged",
                "downstream_status": "cluster_verdict_manifest_ready",
                "cluster_verdict_manifest": {
                    "manifest_id": str(manifest_id),
                    "status": manifest_status,
                    "cluster_count": cluster_count,
                    "singleton_count": singleton_count,
                },
                "cluster_verdict_manifest_id": str(manifest_id),
                "cluster_verdict_manifest_status": manifest_status,
                "cluster_count": cluster_count,
                "singleton_count": singleton_count,
            }
        )
        batch.process_summary_json = summary
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def close_batch(self, *, batch_id: uuid.UUID) -> ConsumptionBatch:
        batch = self.db.get(ConsumptionBatch, batch_id)
        if batch is None:
            raise ValueError(f"consumption batch not found: {batch_id}")
        batch.status = "closed"
        batch.closed_at = _utc_now()
        for item in batch.items:
            if item.ingest_run_item_id is None:
                continue
            run_item = self.db.get(IngestRunItem, item.ingest_run_item_id)
            if run_item is not None:
                run_item.item_status = "closed"
                self.db.add(run_item)
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def latest_batch(self) -> ConsumptionBatch | None:
        stmt = (
            select(ConsumptionBatch)
            .where(ConsumptionBatch.status != "failed")
            .order_by(ConsumptionBatch.cutoff_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def list_recent(self, *, limit: int = 20, status: str | None = None) -> list[ConsumptionBatch]:
        stmt = select(ConsumptionBatch).options(selectinload(ConsumptionBatch.items))
        if status is not None:
            stmt = stmt.where(ConsumptionBatch.status == status)
        stmt = stmt.order_by(ConsumptionBatch.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_with_items(self, *, batch_id: uuid.UUID) -> ConsumptionBatch | None:
        stmt = (
            select(ConsumptionBatch)
            .options(selectinload(ConsumptionBatch.items))
            .where(ConsumptionBatch.id == batch_id)
        )
        return self.db.scalar(stmt)
