from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas.workflows import WorkflowRunRequest
from ..security import require_write_access, sanitize_exception_detail

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


class WorkflowRunResponse(BaseModel):
    workflow: str
    workflow_name: str
    workflow_id: str
    run_id: str | None = None
    status: str
    started_at: datetime
    result: dict | None = None


_WORKFLOW_NAME_MAP = {
    "poll_feeds": "PollFeedsWorkflow",
    "consume_pending": "ConsumePendingWorkflow",
    "daily_digest": "DailyDigestWorkflow",
    "notification_retry": "NotificationRetryWorkflow",
    "cleanup": "CleanupWorkspaceWorkflow",
    "provider_canary": "ProviderCanaryWorkflow",
}


@router.post(
    "/run", response_model=WorkflowRunResponse, dependencies=[Depends(require_write_access)]
)
async def run_workflow(payload: WorkflowRunRequest, db: Session = Depends(get_db)):
    del db  # reserved for future authorization / audit persistence

    try:
        from temporalio.client import Client
        from temporalio.exceptions import WorkflowAlreadyStartedError
    except Exception as exc:  # pragma: no cover
        detail = sanitize_exception_detail(exc)
        raise HTTPException(
            status_code=503, detail=f"temporal client not available: {detail}"
        ) from exc

    workflow_name = _WORKFLOW_NAME_MAP[payload.workflow]
    request_payload = dict(payload.payload or {})
    request_payload.setdefault("run_once", payload.run_once)

    workflow_id = payload.workflow_id or f"api-{payload.workflow}-{uuid4()}"
    if not payload.run_once and payload.workflow_id is None:
        workflow_id = f"{payload.workflow}-workflow"

    try:
        client = await asyncio.wait_for(
            Client.connect(
                settings.temporal_target_host,
                namespace=settings.temporal_namespace,
            ),
            timeout=settings.api_temporal_connect_timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                "temporal connect timed out "
                f"after {settings.api_temporal_connect_timeout_seconds:.1f}s"
            ),
        ) from exc
    except Exception as exc:
        detail = sanitize_exception_detail(exc)
        raise HTTPException(
            status_code=503, detail=f"failed to connect temporal: {detail}"
        ) from exc

    try:
        handle = await asyncio.wait_for(
            client.start_workflow(
                workflow_name,
                request_payload,
                id=workflow_id,
                task_queue=settings.temporal_task_queue,
            ),
            timeout=settings.api_temporal_start_timeout_seconds,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                "temporal workflow start timed out "
                f"after {settings.api_temporal_start_timeout_seconds:.1f}s"
            ),
        ) from exc
    except WorkflowAlreadyStartedError:
        return WorkflowRunResponse(
            workflow=payload.workflow,
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            status="already_running",
            started_at=datetime.now(UTC),
            result=None,
        )
    except Exception as exc:
        detail = sanitize_exception_detail(exc)
        raise HTTPException(status_code=503, detail=f"failed to start workflow: {detail}") from exc

    run_id = getattr(handle, "first_execution_run_id", None) or getattr(handle, "run_id", None)

    if payload.wait_for_result:
        try:
            result = await asyncio.wait_for(
                handle.result(),
                timeout=settings.api_temporal_result_timeout_seconds,
            )
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail=(
                    "workflow result timed out "
                    f"after {settings.api_temporal_result_timeout_seconds:.1f}s"
                ),
            ) from exc
        except Exception as exc:
            detail = sanitize_exception_detail(exc)
            raise HTTPException(
                status_code=502, detail=f"workflow execution failed: {detail}"
            ) from exc
        return WorkflowRunResponse(
            workflow=payload.workflow,
            workflow_name=workflow_name,
            workflow_id=handle.id,
            run_id=run_id,
            status="completed",
            started_at=datetime.now(UTC),
            result=result if isinstance(result, dict) else {"value": result},
        )

    return WorkflowRunResponse(
        workflow=payload.workflow,
        workflow_name=workflow_name,
        workflow_id=handle.id,
        run_id=run_id,
        status="started",
        started_at=datetime.now(UTC),
        result=None,
    )
