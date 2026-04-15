from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from ..models import Job

ACTIVE_JOB_STATUSES = {"queued", "running", "succeeded"}
RETRYABLE_DISPATCH_FAILURE_REASONS = {"dispatch_failed", "dispatch_timeout"}


class JobsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        video_id: uuid.UUID,
        kind: str,
        mode: str | None,
        overrides_json: dict[str, object] | None,
        status: str = "queued",
        idempotency_key: str,
        error_message: str | None = None,
    ) -> Job:
        instance = Job(
            video_id=video_id,
            kind=kind,
            mode=mode,
            overrides_json=overrides_json,
            status=status,
            idempotency_key=idempotency_key,
            error_message=error_message,
        )
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def create_or_reuse(
        self,
        *,
        video_id: uuid.UUID,
        kind: str,
        mode: str | None,
        overrides_json: dict[str, object] | None,
        idempotency_key: str,
        force: bool = False,
    ) -> tuple[Job, bool]:
        if not force:
            existing = self.get_active_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing, False
            retryable = self.requeue_retryable_dispatch_failure(idempotency_key=idempotency_key)
            if retryable is not None:
                return retryable, True

        try:
            created = self.create(
                video_id=video_id,
                kind=kind,
                mode=mode,
                overrides_json=overrides_json,
                status="queued",
                idempotency_key=idempotency_key,
            )
            return created, True
        except IntegrityError:
            self.db.rollback()
            if not force:
                retryable = self.requeue_retryable_dispatch_failure(idempotency_key=idempotency_key)
                if retryable is not None:
                    return retryable, True
            existing = self.get_by_idempotency_key(idempotency_key)
            if existing is None:
                raise
            return existing, False

    def requeue_retryable_dispatch_failure(self, *, idempotency_key: str) -> Job | None:
        stmt = select(Job).where(
            Job.idempotency_key == idempotency_key,
            Job.status == "failed",
            Job.hard_fail_reason.in_(RETRYABLE_DISPATCH_FAILURE_REASONS),
        )
        job = self.db.scalar(stmt)
        if job is None:
            return None
        job.status = "queued"
        job.error_message = None
        job.hard_fail_reason = None
        job.pipeline_final_status = None
        job.degradation_count = None
        job.last_error_code = None
        job.llm_gate_passed = None
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_dispatch_failed(
        self,
        *,
        job_id: uuid.UUID,
        error_message: str,
        reason: str = "dispatch_failed",
    ) -> Job:
        job = self.get(job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")
        job.status = "failed"
        job.error_message = error_message
        job.pipeline_final_status = "failed"
        job.hard_fail_reason = reason
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)

    def get_previous_successful_job(self, *, job_id: uuid.UUID) -> Job | None:
        current = self.get(job_id)
        if current is None:
            return None
        stmt = (
            select(Job)
            .where(
                Job.video_id == current.video_id,
                Job.status == "succeeded",
                Job.id != current.id,
                Job.created_at < current.created_at,
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get_latest_successful_for_video(self, *, video_id: uuid.UUID) -> Job | None:
        stmt = (
            select(Job)
            .where(
                Job.video_id == video_id,
                Job.status == "succeeded",
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get_by_idempotency_key(self, idempotency_key: str) -> Job | None:
        stmt = select(Job).where(Job.idempotency_key == idempotency_key)
        return self.db.scalar(stmt)

    def get_pipeline_final_status(self, *, job_id: uuid.UUID) -> str | None:
        stmt = text(
            """
            SELECT pipeline_final_status
            FROM jobs
            WHERE id = CAST(:job_id AS UUID)
            LIMIT 1
            """
        )
        try:
            row = self.db.execute(stmt, {"job_id": str(job_id)}).first()
        except DBAPIError as exc:
            self.db.rollback()
            if "pipeline_final_status" in str(exc).lower():
                return None
            raise
        if row is None:
            return None
        value = row[0]
        return str(value) if value else None

    def get_active_by_idempotency_key(self, idempotency_key: str) -> Job | None:
        stmt = select(Job).where(
            Job.idempotency_key == idempotency_key,
            Job.status.in_(ACTIVE_JOB_STATUSES),
        )
        return self.db.scalar(stmt)

    def get_artifact_digest_md(self, *, job_id: uuid.UUID) -> str | None:
        stmt = text(
            """
            SELECT artifact_digest_md
            FROM jobs
            WHERE id = CAST(:job_id AS UUID)
            LIMIT 1
            """
        )
        try:
            row = self.db.execute(stmt, {"job_id": str(job_id)}).first()
        except DBAPIError as exc:
            self.db.rollback()
            if "artifact_digest_md" in str(exc).lower():
                return None
            raise
        if row is None:
            return None
        value = row[0]
        return str(value) if value else None

    def get_artifact_digest_md_by_video_url(self, *, video_url: str) -> str | None:
        stmt = text(
            """
            SELECT j.artifact_digest_md
            FROM jobs j
            JOIN videos v ON v.id = j.video_id
            WHERE v.source_url = :video_url
            ORDER BY j.created_at DESC
            LIMIT 1
            """
        )
        try:
            row = self.db.execute(stmt, {"video_url": video_url}).first()
        except DBAPIError as exc:
            self.db.rollback()
            if "artifact_digest_md" in str(exc).lower():
                return None
            raise
        if row is None:
            return None
        value = row[0]
        return str(value) if value else None
