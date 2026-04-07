from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiServiceError
from ..security import require_write_access, sanitize_exception_detail
from ..services import VideosService

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


class VideoResponse(BaseModel):
    id: uuid.UUID
    platform: str
    video_uid: str
    source_url: str
    title: str | None
    published_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    status: Literal["queued", "running", "succeeded", "failed"] | None = None
    last_job_id: uuid.UUID | None = None


class VideoProcessInput(BaseModel):
    platform: str = Field(min_length=1)
    url: str = Field(min_length=1)
    video_id: str | None = None


class VideoProcessRequest(BaseModel):
    video: VideoProcessInput
    mode: Literal["full", "text_only", "refresh_comments", "refresh_llm"] = "full"
    overrides: dict[str, Any] = Field(default_factory=dict)
    force: bool = False


class VideoProcessResponse(BaseModel):
    job_id: uuid.UUID
    video_db_id: uuid.UUID
    video_uid: str
    status: Literal["queued", "running", "succeeded", "failed"]
    idempotency_key: str
    mode: str
    overrides: dict[str, Any]
    force: bool
    reused: bool
    workflow_id: str | None


@router.get("", response_model=list[VideoResponse])
def list_videos(
    platform: str | None = None,
    status: Literal["queued", "running", "succeeded", "failed"] | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    service = VideosService(db)
    rows = service.list_videos(platform=platform, status=status, limit=limit)
    return [
        VideoResponse(
            id=row["id"],
            platform=row["platform"],
            video_uid=row["video_uid"],
            source_url=row["source_url"],
            title=row["title"],
            published_at=row["published_at"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            status=row["latest_job_status"],
            last_job_id=row["latest_job_id"],
        )
        for row in rows
    ]


@router.post(
    "/process",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_write_access)],
)
async def process_video(
    payload: VideoProcessRequest,
    db: Session = Depends(get_db),
):
    service = VideosService(db)
    try:
        result = await service.process_video(
            platform=payload.video.platform,
            url=payload.video.url,
            video_id=payload.video.video_id,
            mode=payload.mode,
            overrides=payload.overrides,
            force=payload.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=sanitize_exception_detail(exc)) from exc
    except ApiServiceError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=sanitize_exception_detail(exc)) from exc

    return VideoProcessResponse(
        job_id=result["job_id"],
        video_db_id=result["video_db_id"],
        video_uid=result["video_uid"],
        status=result["status"],
        idempotency_key=result["idempotency_key"],
        mode=result["mode"],
        overrides=result["overrides"],
        force=result["force"],
        reused=result["reused"],
        workflow_id=result["workflow_id"],
    )
