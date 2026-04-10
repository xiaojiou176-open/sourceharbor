from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session
from worker.state.postgres_store import PostgresBusinessStore

from ..config import settings
from ..errors import ApiTimeoutError
from ..models import ConsumptionBatch, Subscription
from ..repositories import ConsumptionBatchesRepository, IngestRunsRepository

logger = logging.getLogger(__name__)
_DEFAULT_TRACK_INTERVAL_MINUTES = 15
_DEFAULT_AUTO_COOLDOWN_MINUTES = 60


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IngestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.run_repo = IngestRunsRepository(db)
        self.batch_repo = ConsumptionBatchesRepository(db)

    async def poll(
        self,
        *,
        subscription_id: uuid.UUID | None,
        platform: str | None,
        max_new_videos: int,
        trace_id: str | None = None,
        user: str | None = None,
    ) -> dict[str, object]:
        trace = str(trace_id or "missing_trace")
        actor = str(user or "system")
        logger.info(
            "ingest_poll_started",
            extra={
                "trace_id": trace,
                "user": actor,
                "subscription_id": str(subscription_id) if subscription_id else None,
                "platform": platform,
                "max_new_videos": max_new_videos,
            },
        )
        if subscription_id is not None:
            exists = self.db.scalar(
                select(Subscription.id).where(Subscription.id == subscription_id)
            )
            if exists is None:
                raise ValueError("subscription does not exist")

        try:
            from temporalio.client import Client
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "ingest_temporal_client_import_failed",
                extra={"trace_id": trace, "user": actor, "error": str(exc)},
            )
            raise RuntimeError(f"temporal client not available: {exc}") from exc

        try:
            client = await asyncio.wait_for(
                Client.connect(
                    settings.temporal_target_host,
                    namespace=settings.temporal_namespace,
                ),
                timeout=settings.api_temporal_connect_timeout_seconds,
            )
        except TimeoutError as exc:
            logger.error(
                "ingest_temporal_connect_timeout",
                extra={
                    "trace_id": trace,
                    "user": actor,
                    "timeout_seconds": settings.api_temporal_connect_timeout_seconds,
                    "error": str(exc),
                },
            )
            raise ApiTimeoutError(
                detail=(
                    "temporal connect timed out "
                    f"after {settings.api_temporal_connect_timeout_seconds:.1f}s"
                ),
                error_code="TEMPORAL_CONNECT_TIMEOUT",
            ) from exc

        filters = {
            "subscription_id": str(subscription_id) if subscription_id else None,
            "platform": platform,
            "max_new_videos": max_new_videos,
        }
        run = self.run_repo.create(
            subscription_id=subscription_id,
            platform=platform,
            max_new_videos=max_new_videos,
            filters_json=filters,
            requested_by=actor,
            requested_trace_id=trace,
        )
        filters["ingest_run_id"] = str(run.id)

        try:
            handle = await asyncio.wait_for(
                client.start_workflow(
                    "PollFeedsWorkflow",
                    filters,
                    id=f"api-poll-feeds-{run.id}-{uuid4()}",
                    task_queue=settings.temporal_task_queue,
                ),
                timeout=settings.api_temporal_start_timeout_seconds,
            )
        except TimeoutError as exc:
            self.run_repo.mark_failed(
                run_id=run.id,
                error_message=(
                    "temporal workflow start timed out "
                    f"after {settings.api_temporal_start_timeout_seconds:.1f}s"
                ),
            )
            logger.error(
                "ingest_temporal_start_timeout",
                extra={
                    "trace_id": trace,
                    "user": actor,
                    "timeout_seconds": settings.api_temporal_start_timeout_seconds,
                    "error": str(exc),
                },
            )
            raise ApiTimeoutError(
                detail=(
                    "temporal workflow start timed out "
                    f"after {settings.api_temporal_start_timeout_seconds:.1f}s"
                ),
                error_code="TEMPORAL_WORKFLOW_START_TIMEOUT",
            ) from exc
        except Exception as exc:
            self.run_repo.mark_failed(run_id=run.id, error_message=str(exc))
            raise

        run = self.run_repo.mark_workflow_started(
            run_id=run.id,
            workflow_id=str(getattr(handle, "id", "") or ""),
        )
        logger.info(
            "ingest_poll_completed",
            extra={
                "trace_id": trace,
                "user": actor,
                "workflow_id": getattr(handle, "id", None),
                "run_id": str(run.id),
                "status": run.status,
            },
        )
        return {
            "run_id": run.id,
            "workflow_id": run.workflow_id,
            "status": run.status,
            "enqueued": 0,
            "candidates": [],
            "track_interval_minutes": _DEFAULT_TRACK_INTERVAL_MINUTES,
        }

    async def consume(
        self,
        *,
        trigger_mode: str,
        subscription_id: uuid.UUID | None,
        platform: str | None,
        timezone_name: str | None,
        window_id: str | None,
        cooldown_minutes: int | None,
        trace_id: str | None = None,
        user: str | None = None,
    ) -> dict[str, object]:
        trace = str(trace_id or "missing_trace")
        actor = str(user or "system")
        normalized_trigger_mode = str(trigger_mode or "manual").strip().lower() or "manual"
        if normalized_trigger_mode not in {"manual", "auto"}:
            raise ValueError("trigger_mode must be 'manual' or 'auto'")
        if subscription_id is not None:
            exists = self.db.scalar(
                select(Subscription.id).where(Subscription.id == subscription_id)
            )
            if exists is None:
                raise ValueError("subscription does not exist")
        resolved_timezone_name = self._resolve_timezone_name(timezone_name)
        cooldown_floor = max(
            _DEFAULT_AUTO_COOLDOWN_MINUTES,
            int(cooldown_minutes or _DEFAULT_AUTO_COOLDOWN_MINUTES),
        )

        latest_batch = self.batch_repo.latest_batch()
        now = _utc_now()
        if normalized_trigger_mode == "auto" and latest_batch is not None:
            remaining = self._cooldown_remaining_seconds(
                latest_cutoff_at=latest_batch.cutoff_at,
                now=now,
                cooldown_minutes=cooldown_floor,
            )
            if remaining > 0:
                return {
                    "consumption_batch_id": None,
                    "workflow_id": latest_batch.workflow_id,
                    "status": "cooldown_blocked",
                    "trigger_mode": normalized_trigger_mode,
                    "window_id": str(window_id or getattr(latest_batch, "window_id", None) or "")
                    or None,
                    "cutoff_at": latest_batch.cutoff_at,
                    "source_item_count": 0,
                    "pending_window_ids": [],
                    "track_interval_minutes": _DEFAULT_TRACK_INTERVAL_MINUTES,
                    "auto_cooldown_minutes": cooldown_floor,
                    "cooldown_remaining_seconds": remaining,
                }

        pg_store = PostgresBusinessStore(settings.database_url)
        prepared = pg_store.prepare_consumption_batch(
            trigger_mode=normalized_trigger_mode,
            window_id=window_id,
            timezone_name=resolved_timezone_name,
            requested_by=actor,
            requested_trace_id=trace,
            subscription_id=str(subscription_id) if subscription_id is not None else None,
            platform=platform,
            max_items=200,
        )
        if str(prepared.get("status")) == "no_pending_items":
            return {
                "consumption_batch_id": None,
                "workflow_id": None,
                "status": "no_pending_items",
                "trigger_mode": normalized_trigger_mode,
                "window_id": prepared.get("window_id"),
                "cutoff_at": prepared.get("cutoff_at"),
                "source_item_count": int(prepared.get("source_item_count") or 0),
                "pending_window_ids": list(prepared.get("pending_window_ids") or []),
                "track_interval_minutes": _DEFAULT_TRACK_INTERVAL_MINUTES,
                "auto_cooldown_minutes": cooldown_floor,
                "cooldown_remaining_seconds": 0,
            }
        batch_id_raw = prepared.get("consumption_batch_id")
        if not isinstance(batch_id_raw, str) or not batch_id_raw.strip():
            raise RuntimeError("prepared consumption batch missing id")
        batch_id = uuid.UUID(batch_id_raw)

        try:
            from temporalio.client import Client
        except Exception as exc:  # pragma: no cover
            self.batch_repo.mark_start_failed(batch_id=batch_id, error_message=str(exc))
            raise RuntimeError(f"temporal client not available: {exc}") from exc

        try:
            client = await asyncio.wait_for(
                Client.connect(
                    settings.temporal_target_host,
                    namespace=settings.temporal_namespace,
                ),
                timeout=settings.api_temporal_connect_timeout_seconds,
            )
        except TimeoutError as exc:
            self.batch_repo.mark_start_failed(
                batch_id=batch_id,
                error_message=(
                    "temporal connect timed out "
                    f"after {settings.api_temporal_connect_timeout_seconds:.1f}s"
                ),
            )
            raise ApiTimeoutError(
                detail=(
                    "temporal connect timed out "
                    f"after {settings.api_temporal_connect_timeout_seconds:.1f}s"
                ),
                error_code="TEMPORAL_CONNECT_TIMEOUT",
            ) from exc

        workflow_id = f"consume-batch-{batch_id}"
        try:
            handle = await asyncio.wait_for(
                client.start_workflow(
                    "ConsumeBatchWorkflow",
                    {"consumption_batch_id": str(batch_id)},
                    id=workflow_id,
                    task_queue=settings.temporal_task_queue,
                ),
                timeout=settings.api_temporal_start_timeout_seconds,
            )
        except TimeoutError as exc:
            self.batch_repo.mark_start_failed(
                batch_id=batch_id,
                error_message=(
                    "temporal workflow start timed out "
                    f"after {settings.api_temporal_start_timeout_seconds:.1f}s"
                ),
            )
            raise ApiTimeoutError(
                detail=(
                    "temporal workflow start timed out "
                    f"after {settings.api_temporal_start_timeout_seconds:.1f}s"
                ),
                error_code="TEMPORAL_WORKFLOW_START_TIMEOUT",
            ) from exc
        except Exception as exc:
            self.batch_repo.mark_start_failed(batch_id=batch_id, error_message=str(exc))
            raise

        batch = self.batch_repo.mark_workflow_started(
            batch_id=batch_id,
            workflow_id=str(getattr(handle, "id", "") or workflow_id),
        )
        return {
            "consumption_batch_id": batch.id,
            "workflow_id": batch.workflow_id,
            "status": batch.status,
            "trigger_mode": batch.trigger_mode,
            "window_id": batch.window_id,
            "cutoff_at": batch.cutoff_at,
            "source_item_count": batch.source_item_count,
            "pending_window_ids": list(prepared.get("pending_window_ids") or []),
            "track_interval_minutes": _DEFAULT_TRACK_INTERVAL_MINUTES,
            "auto_cooldown_minutes": cooldown_floor,
            "cooldown_remaining_seconds": 0,
        }

    def get_run(self, *, run_id: uuid.UUID):
        return self.run_repo.get_with_items(run_id=run_id)

    def list_runs(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        platform: str | None = None,
    ):
        return self.run_repo.list_recent(limit=limit, status=status, platform=platform)

    def get_batch(self, *, batch_id: uuid.UUID) -> ConsumptionBatch | None:
        return self.batch_repo.get_with_items(batch_id=batch_id)

    def list_batches(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
    ) -> list[ConsumptionBatch]:
        return self.batch_repo.list_recent(limit=limit, status=status)

    @staticmethod
    def _resolve_timezone_name(timezone_name: str | None) -> str:
        candidate = str(timezone_name or settings.digest_local_timezone or "UTC").strip() or "UTC"
        try:
            ZoneInfo(candidate)
        except Exception as exc:
            raise ValueError("timezone_name must be a valid IANA timezone") from exc
        return candidate

    @staticmethod
    def _cooldown_remaining_seconds(
        *,
        latest_cutoff_at: datetime | None,
        now: datetime,
        cooldown_minutes: int,
    ) -> int:
        if latest_cutoff_at is None:
            return 0
        latest = latest_cutoff_at
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        deadline = latest + timedelta(minutes=cooldown_minutes)
        remaining = int((deadline - now).total_seconds())
        return max(0, remaining)
