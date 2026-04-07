from __future__ import annotations

import asyncio
import logging
import uuid
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import ApiTimeoutError
from ..models import Subscription
from ..repositories import IngestRunsRepository

logger = logging.getLogger(__name__)


class IngestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.run_repo = IngestRunsRepository(db)

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
