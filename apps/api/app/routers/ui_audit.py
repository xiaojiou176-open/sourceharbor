from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import require_write_access
from ..services.ui_audit import UiAuditService

router = APIRouter(prefix="/api/v1/ui-audit", tags=["ui-audit"])


class UiAuditRunRequest(BaseModel):
    job_id: uuid.UUID | None = None
    artifact_root: str | None = Field(default=None, min_length=1)


class UiAuditSummary(BaseModel):
    artifact_count: int
    finding_count: int
    severity_counts: dict[str, int]


class UiAuditGeminiReview(BaseModel):
    status: str
    reason_code: str
    provider_status: int | None = None
    model: str | None = None
    timeout_seconds: float | None = None
    max_retries: int | None = None


class UiAuditRunResponse(BaseModel):
    run_id: str
    job_id: str | None = None
    artifact_root: str | None = None
    status: str
    created_at: datetime
    summary: UiAuditSummary
    gemini_review: UiAuditGeminiReview | None = None


class UiAuditFinding(BaseModel):
    id: str
    severity: str
    title: str
    message: str
    rule: str | None = None
    artifact_key: str | None = None


class UiAuditArtifact(BaseModel):
    key: str
    path: str
    mime_type: str
    size_bytes: int
    category: str


class UiAuditFindingsResponse(BaseModel):
    items: list[UiAuditFinding]


class UiAuditArtifactsResponse(BaseModel):
    items: list[UiAuditArtifact]


class UiAuditArtifactPayload(UiAuditArtifact):
    exists: bool
    base64: str | None = None


class UiAuditAutofixRequest(BaseModel):
    mode: str = Field(default="dry-run", pattern=r"^(dry-run|apply)$")
    max_files: int = Field(default=3, ge=1, le=20)
    max_changed_lines: int = Field(default=120, ge=1, le=2000)


class UiAuditAutofixSummary(BaseModel):
    finding_count: int
    high_or_worse_count: int


class UiAuditAutofixResponse(BaseModel):
    run_id: str
    mode: str
    autofix_applied: bool
    summary: UiAuditAutofixSummary
    guardrails: dict[str, object]
    suggested_actions: list[str]


@router.post(
    "/run",
    response_model=UiAuditRunResponse,
    dependencies=[Depends(require_write_access)],
)
def run_ui_audit(payload: UiAuditRunRequest, db: Session = Depends(get_db)):
    if payload.job_id is None and not payload.artifact_root:
        raise HTTPException(status_code=400, detail="either job_id or artifact_root is required")

    service = UiAuditService(db)
    result = service.run(job_id=payload.job_id, artifact_root=payload.artifact_root)
    return UiAuditRunResponse(**result)


@router.get(
    "/{run_id}",
    response_model=UiAuditRunResponse,
    dependencies=[Depends(require_write_access)],
)
def get_ui_audit(run_id: str, db: Session = Depends(get_db)):
    del db
    service = UiAuditService()
    payload = service.get(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="ui audit run not found")
    return UiAuditRunResponse(**payload)


@router.get(
    "/{run_id}/findings",
    response_model=UiAuditFindingsResponse,
    dependencies=[Depends(require_write_access)],
)
def list_ui_audit_findings(
    run_id: str,
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    del db
    service = UiAuditService()
    payload = service.list_findings(run_id=run_id, severity=severity)
    if payload is None:
        raise HTTPException(status_code=404, detail="ui audit run not found")
    return UiAuditFindingsResponse(items=[UiAuditFinding(**item) for item in payload])


@router.get(
    "/{run_id}/artifacts",
    response_model=UiAuditArtifactsResponse,
    dependencies=[Depends(require_write_access)],
)
def list_ui_audit_artifacts(run_id: str, db: Session = Depends(get_db)):
    del db
    service = UiAuditService()
    payload = service.list_artifacts(run_id=run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="ui audit run not found")
    return UiAuditArtifactsResponse(items=[UiAuditArtifact(**item) for item in payload])


@router.get(
    "/{run_id}/artifact",
    response_model=UiAuditArtifactPayload,
    dependencies=[Depends(require_write_access)],
)
def get_ui_audit_artifact(
    run_id: str,
    key: str = Query(..., min_length=1),
    include_base64: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    del db
    service = UiAuditService()
    payload = service.get_artifact(run_id=run_id, key=key, include_base64=include_base64)
    if payload is None:
        raise HTTPException(status_code=404, detail="ui audit artifact not found")

    return UiAuditArtifactPayload(**payload)


@router.post(
    "/{run_id}/autofix",
    response_model=UiAuditAutofixResponse,
    dependencies=[Depends(require_write_access)],
)
def run_ui_audit_autofix(
    run_id: str,
    payload: UiAuditAutofixRequest,
    db: Session = Depends(get_db),
):
    del db
    service = UiAuditService()
    result = service.autofix(
        run_id=run_id,
        mode=payload.mode,
        max_files=payload.max_files,
        max_changed_lines=payload.max_changed_lines,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="ui audit run not found")
    return UiAuditAutofixResponse(**result)
