from __future__ import annotations

import uuid
from datetime import datetime

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
