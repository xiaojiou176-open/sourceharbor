from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..services import JobsService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class JobStepSummary(BaseModel):
    name: str
    status: str
    attempt: int
    started_at: str | None
    finished_at: str | None
    error: Any | None = None


class JobStepDetail(JobStepSummary):
    error_kind: str | None = None
    retry_meta: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    thought_metadata: dict[str, Any] = Field(default_factory=dict)
    cache_key: str | None = None


class JobDegradation(BaseModel):
    step: str | None = None
    status: str | None = None
    reason: str | None = None
    error: Any | None = None
    error_kind: str | None = None
    retry_meta: dict[str, Any] | None = None
    cache_meta: dict[str, Any] | None = None


class NotificationRetrySummary(BaseModel):
    delivery_id: uuid.UUID
    status: str
    attempt_count: int
    next_retry_at: datetime | None = None
    last_error_kind: str | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    video_id: uuid.UUID
    kind: Literal["video_digest_v1", "phase2_ingest_stub"]
    status: Literal["queued", "running", "succeeded", "failed"]
    mode: str | None = None
    idempotency_key: str
    error_message: str | None
    artifact_digest_md: str | None
    artifact_root: str | None
    llm_required: bool | None = None
    llm_gate_passed: bool | None = None
    hard_fail_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    step_summary: list[JobStepSummary]
    steps: list[JobStepDetail]
    degradations: list[JobDegradation]
    pipeline_final_status: Literal["succeeded", "degraded", "failed"] | None = None
    artifacts_index: dict[str, str]
    notification_retry: NotificationRetrySummary | None = None


class JobCompareStats(BaseModel):
    added_lines: int
    removed_lines: int
    changed: bool


class JobCompareResponse(BaseModel):
    job_id: str
    previous_job_id: str | None = None
    has_previous: bool
    current_digest: str | None = None
    previous_digest: str | None = None
    diff_markdown: str
    stats: JobCompareStats


class KnowledgeCardResponse(BaseModel):
    card_type: str
    title: str
    body: str
    source_section: str
    order_index: int


class JobEvidenceBundleResponse(BaseModel):
    bundle_kind: str
    sharing_scope: str
    sample: bool
    generated_at: datetime
    proof_boundary: str
    job: dict[str, Any]
    trace_summary: dict[str, Any]
    digest: str | None = None
    digest_meta: dict[str, Any] | None = None
    rich_evidence: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    knowledge_cards: list[dict[str, Any]]
    artifact_manifest: dict[str, str]
    step_summary: list[dict[str, Any]]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    service = JobsService(db)
    row = service.get_job(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    steps = service.get_steps(job_id)
    step_summary = [
        JobStepSummary(
            name=item["name"],
            status=item["status"],
            attempt=item["attempt"],
            started_at=item["started_at"],
            finished_at=item["finished_at"],
            error=item.get("error"),
        )
        for item in steps
    ]
    degradations = service.get_degradations(
        artifact_root=row.artifact_root,
        artifact_digest_md=row.artifact_digest_md,
        steps=steps,
    )
    pipeline_final_status = service.get_pipeline_final_status(job_id, fallback_status=row.status)
    llm_required, llm_gate_passed, hard_fail_reason = service.resolve_llm_gate_fields(
        llm_required=getattr(row, "llm_required", None),
        llm_gate_passed=getattr(row, "llm_gate_passed", None),
        hard_fail_reason=getattr(row, "hard_fail_reason", None),
        steps=steps,
    )
    artifacts_index = service.get_artifacts_index(
        artifact_root=row.artifact_root,
        artifact_digest_md=row.artifact_digest_md,
        steps=steps,
    )

    return JobResponse(
        id=row.id,
        video_id=row.video_id,
        kind=row.kind,
        status=row.status,
        mode=row.mode,
        idempotency_key=row.idempotency_key,
        error_message=row.error_message,
        artifact_digest_md=row.artifact_digest_md,
        artifact_root=row.artifact_root,
        llm_required=llm_required,
        llm_gate_passed=llm_gate_passed,
        hard_fail_reason=hard_fail_reason,
        created_at=row.created_at,
        updated_at=row.updated_at,
        step_summary=step_summary,
        steps=[JobStepDetail(**item) for item in steps],
        degradations=[JobDegradation(**item) for item in degradations],
        pipeline_final_status=pipeline_final_status,
        artifacts_index=artifacts_index,
        notification_retry=service.get_notification_retry(job_id),
    )


@router.get("/{job_id}/compare", response_model=JobCompareResponse)
def compare_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    service = JobsService(db)
    payload = service.compare_with_previous(job_id=job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobCompareResponse(**payload)


@router.get("/{job_id}/knowledge-cards", response_model=list[KnowledgeCardResponse])
def get_job_knowledge_cards(job_id: uuid.UUID, db: Session = Depends(get_db)):
    service = JobsService(db)
    payload = service.get_knowledge_cards(job_id=job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="job not found")
    return [KnowledgeCardResponse(**item) for item in payload]


@router.get("/{job_id}/bundle", response_model=JobEvidenceBundleResponse)
def get_job_evidence_bundle(job_id: uuid.UUID, db: Session = Depends(get_db)):
    service = JobsService(db)
    payload = service.build_evidence_bundle(job_id=job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobEvidenceBundleResponse(**payload)
