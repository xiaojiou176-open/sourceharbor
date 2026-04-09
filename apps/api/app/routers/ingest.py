from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiServiceError
from ..security import require_write_access, sanitize_exception_detail
from ..services import IngestService

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


class IngestPollRequest(BaseModel):
    subscription_id: uuid.UUID | None = None
    platform: str | None = None
    max_new_videos: int = Field(default=50, ge=1, le=500)


class IngestCandidate(BaseModel):
    video_id: uuid.UUID
    platform: str
    video_uid: str
    source_url: str
    title: str | None
    published_at: datetime | None
    job_id: uuid.UUID


class IngestPollResponse(BaseModel):
    run_id: uuid.UUID
    workflow_id: str | None = None
    status: str
    enqueued: int
    candidates: list[IngestCandidate]
    track_interval_minutes: int = 15


class ConsumeBatchRequest(BaseModel):
    trigger_mode: Literal["manual", "auto"] = "manual"
    subscription_id: uuid.UUID | None = None
    platform: str | None = None
    timezone_name: str | None = None
    window_id: str | None = None
    cooldown_minutes: int | None = Field(default=None, ge=60, le=24 * 60)


class ConsumeBatchResponse(BaseModel):
    consumption_batch_id: uuid.UUID | None = None
    workflow_id: str | None = None
    status: str
    trigger_mode: Literal["manual", "auto"]
    window_id: str | None = None
    cutoff_at: datetime | None = None
    source_item_count: int
    pending_window_ids: list[str]
    track_interval_minutes: int
    auto_cooldown_minutes: int
    cooldown_remaining_seconds: int = 0


class IngestRunItemResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID | None
    video_id: uuid.UUID | None
    job_id: uuid.UUID | None
    ingest_event_id: uuid.UUID | None
    platform: str
    video_uid: str
    source_url: str
    title: str | None
    published_at: datetime | None
    entry_hash: str | None
    pipeline_mode: str | None
    content_type: str
    item_status: str
    created_at: datetime
    updated_at: datetime


class IngestRunSummaryResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID | None
    workflow_id: str | None
    platform: str | None
    max_new_videos: int
    status: str
    jobs_created: int
    candidates_count: int
    feeds_polled: int
    entries_fetched: int
    entries_normalized: int
    ingest_events_created: int
    ingest_event_duplicates: int
    job_duplicates: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class IngestRunResponse(IngestRunSummaryResponse):
    requested_by: str | None
    requested_trace_id: str | None
    filters_json: dict[str, object] | None = None
    items: list[IngestRunItemResponse]


class ConsumptionBatchItemResponse(BaseModel):
    id: uuid.UUID
    ingest_run_item_id: uuid.UUID | None
    subscription_id: uuid.UUID | None
    video_id: uuid.UUID | None
    job_id: uuid.UUID | None
    ingest_event_id: uuid.UUID | None
    platform: str
    video_uid: str
    source_url: str
    title: str | None
    published_at: datetime | None
    source_effective_at: datetime
    discovered_at: datetime
    entry_hash: str | None
    pipeline_mode: str | None
    content_type: str
    source_origin: str
    created_at: datetime
    updated_at: datetime


class ConsumptionBatchSummaryResponse(BaseModel):
    id: uuid.UUID
    workflow_id: str | None
    status: str
    trigger_mode: str
    window_id: str
    timezone_name: str
    cutoff_at: datetime
    requested_by: str | None
    requested_trace_id: str | None
    source_item_count: int
    processed_job_count: int
    succeeded_job_count: int
    failed_job_count: int
    error_message: str | None
    judged_at: datetime | None
    materialized_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConsumptionBatchResponse(ConsumptionBatchSummaryResponse):
    filters_json: dict[str, object] | None = None
    base_published_doc_versions: list[str] = Field(default_factory=list)
    process_summary_json: dict[str, object] | None = None
    items: list[ConsumptionBatchItemResponse]


@router.post(
    "/poll",
    response_model=IngestPollResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_write_access)],
)
async def poll_ingest(
    payload: IngestPollRequest,
    db: Session = Depends(get_db),
):
    service = IngestService(db)
    try:
        result = await service.poll(
            subscription_id=payload.subscription_id,
            platform=payload.platform,
            max_new_videos=payload.max_new_videos,
        )
    except ApiServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc
    except ValueError as exc:
        detail = sanitize_exception_detail(exc)
        if "not found" in detail.lower() or "does not exist" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    return IngestPollResponse(
        run_id=result["run_id"],
        workflow_id=result.get("workflow_id"),
        status=result["status"],
        enqueued=result["enqueued"],
        candidates=[
            IngestCandidate(
                video_id=item["video_id"],
                platform=item["platform"],
                video_uid=item["video_uid"],
                source_url=item["source_url"],
                title=item["title"],
                published_at=item["published_at"],
                job_id=item["job_id"],
            )
            for item in result["candidates"]
        ],
        track_interval_minutes=int(result.get("track_interval_minutes") or 15),
    )


@router.post(
    "/consume",
    response_model=ConsumeBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_write_access)],
)
async def consume_ingest(
    payload: ConsumeBatchRequest,
    db: Session = Depends(get_db),
):
    service = IngestService(db)
    try:
        result = await service.consume(
            trigger_mode=payload.trigger_mode,
            subscription_id=payload.subscription_id,
            platform=payload.platform,
            timezone_name=payload.timezone_name,
            window_id=payload.window_id,
            cooldown_minutes=payload.cooldown_minutes,
        )
    except ApiServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc
    except ValueError as exc:
        detail = sanitize_exception_detail(exc)
        if "not found" in detail.lower() or "does not exist" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc

    return ConsumeBatchResponse(
        consumption_batch_id=result.get("consumption_batch_id"),
        workflow_id=result.get("workflow_id"),
        status=str(result["status"]),
        trigger_mode=str(result["trigger_mode"]),
        window_id=result.get("window_id"),
        cutoff_at=result.get("cutoff_at"),
        source_item_count=int(result.get("source_item_count") or 0),
        pending_window_ids=list(result.get("pending_window_ids") or []),
        track_interval_minutes=int(result.get("track_interval_minutes") or 15),
        auto_cooldown_minutes=int(result.get("auto_cooldown_minutes") or 60),
        cooldown_remaining_seconds=int(result.get("cooldown_remaining_seconds") or 0),
    )


def _to_ingest_run_summary_response(row) -> IngestRunSummaryResponse:
    return IngestRunSummaryResponse(
        id=row.id,
        subscription_id=row.subscription_id,
        workflow_id=row.workflow_id,
        platform=row.platform,
        max_new_videos=row.max_new_videos,
        status=row.status,
        jobs_created=row.jobs_created,
        candidates_count=row.candidates_count,
        feeds_polled=row.feeds_polled,
        entries_fetched=row.entries_fetched,
        entries_normalized=row.entries_normalized,
        ingest_events_created=row.ingest_events_created,
        ingest_event_duplicates=row.ingest_event_duplicates,
        job_duplicates=row.job_duplicates,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def _to_consumption_batch_summary_response(row) -> ConsumptionBatchSummaryResponse:
    return ConsumptionBatchSummaryResponse(
        id=row.id,
        workflow_id=row.workflow_id,
        status=row.status,
        trigger_mode=row.trigger_mode,
        window_id=row.window_id,
        timezone_name=row.timezone_name,
        cutoff_at=row.cutoff_at,
        requested_by=row.requested_by,
        requested_trace_id=row.requested_trace_id,
        source_item_count=row.source_item_count,
        processed_job_count=row.processed_job_count,
        succeeded_job_count=row.succeeded_job_count,
        failed_job_count=row.failed_job_count,
        error_message=row.error_message,
        judged_at=row.judged_at,
        materialized_at=row.materialized_at,
        closed_at=row.closed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/runs", response_model=list[IngestRunSummaryResponse])
def list_ingest_runs(
    status: str | None = None,
    platform: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = IngestService(db)
    rows = service.list_runs(limit=limit, status=status, platform=platform)
    return [_to_ingest_run_summary_response(row) for row in rows]


@router.get("/runs/{run_id}", response_model=IngestRunResponse)
def get_ingest_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    service = IngestService(db)
    row = service.get_run(run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ingest run not found")

    return IngestRunResponse(
        **_to_ingest_run_summary_response(row).model_dump(),
        requested_by=row.requested_by,
        requested_trace_id=row.requested_trace_id,
        filters_json=row.filters_json if isinstance(row.filters_json, dict) else None,
        items=[
            IngestRunItemResponse(
                id=item.id,
                subscription_id=item.subscription_id,
                video_id=item.video_id,
                job_id=item.job_id,
                ingest_event_id=item.ingest_event_id,
                platform=item.platform,
                video_uid=item.video_uid,
                source_url=item.source_url,
                title=item.title,
                published_at=item.published_at,
                entry_hash=item.entry_hash,
                pipeline_mode=item.pipeline_mode,
                content_type=item.content_type,
                item_status=item.item_status,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in row.items
        ],
    )


@router.get("/batches", response_model=list[ConsumptionBatchSummaryResponse])
def list_consumption_batches(
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = IngestService(db)
    rows = service.list_batches(limit=limit, status=status)
    return [_to_consumption_batch_summary_response(row) for row in rows]


@router.get("/batches/{batch_id}", response_model=ConsumptionBatchResponse)
def get_consumption_batch(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    service = IngestService(db)
    row = service.get_batch(batch_id=batch_id)
    if row is None:
        raise HTTPException(status_code=404, detail="consumption batch not found")

    return ConsumptionBatchResponse(
        **_to_consumption_batch_summary_response(row).model_dump(),
        filters_json=row.filters_json if isinstance(row.filters_json, dict) else None,
        base_published_doc_versions=list(row.base_published_doc_versions or []),
        process_summary_json=(
            row.process_summary_json if isinstance(row.process_summary_json, dict) else None
        ),
        items=[
            ConsumptionBatchItemResponse(
                id=item.id,
                ingest_run_item_id=item.ingest_run_item_id,
                subscription_id=item.subscription_id,
                video_id=item.video_id,
                job_id=item.job_id,
                ingest_event_id=item.ingest_event_id,
                platform=item.platform,
                video_uid=item.video_uid,
                source_url=item.source_url,
                title=item.title,
                published_at=item.published_at,
                source_effective_at=item.source_effective_at,
                discovered_at=item.discovered_at,
                entry_hash=item.entry_hash,
                pipeline_mode=item.pipeline_mode,
                content_type=item.content_type,
                source_origin=item.source_origin,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in row.items
        ],
    )
