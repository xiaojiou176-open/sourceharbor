from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

WorkflowName = Literal[
    "poll_feeds",
    "consume_pending",
    "daily_digest",
    "notification_retry",
    "cleanup",
    "provider_canary",
]


class CleanupWorkflowPayload(BaseModel):
    run_once: bool | None = None
    interval_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    workspace_dir: str | None = Field(default=None, min_length=1, max_length=512)
    older_than_hours: int | None = Field(default=None, ge=1, le=24 * 365)
    cache_dir: str | None = Field(default=None, min_length=1, max_length=512)
    cache_older_than_hours: int | None = Field(default=None, ge=1, le=24 * 365)
    cache_max_size_mb: int | None = Field(default=None, ge=1, le=10240)

    @model_validator(mode="after")
    def validate_paths(self) -> CleanupWorkflowPayload:
        for path in (self.workspace_dir, self.cache_dir):
            if path is None:
                continue
            normalized = path.strip()
            if not normalized:
                raise ValueError("cleanup path cannot be blank")
            if "\x00" in normalized:
                raise ValueError("cleanup path contains null byte")
            if "://" in normalized:
                raise ValueError("cleanup path must be a local filesystem path")
            if ".." in normalized.split("/"):
                raise ValueError("cleanup path cannot contain parent traversal segments")
        return self


class PollFeedsWorkflowPayload(BaseModel):
    run_once: bool | None = None
    subscription_id: str | None = Field(default=None, min_length=1, max_length=64)
    platform: str | None = Field(default=None, min_length=1, max_length=32)
    max_new_videos: int | None = Field(default=None, ge=1, le=500)
    interval_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


class ConsumePendingWorkflowPayload(BaseModel):
    run_once: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=60, le=24 * 7)
    timezone_name: str | None = Field(default=None, min_length=1, max_length=128)
    window_id: str | None = Field(default=None, min_length=1, max_length=128)


class WorkflowRunRequest(BaseModel):
    workflow: WorkflowName
    run_once: bool = True
    wait_for_result: bool = False
    workflow_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload(self) -> WorkflowRunRequest:
        payload = dict(self.payload or {})
        if len(payload) > 32:
            raise ValueError("payload has too many keys")
        for key in payload:
            if not isinstance(key, str):
                raise ValueError("payload keys must be strings")
            if len(key) > 64:
                raise ValueError("payload key length exceeds 64 characters")

        if self.workflow == "poll_feeds":
            payload = PollFeedsWorkflowPayload.model_validate(payload).model_dump(exclude_none=True)
        if self.workflow == "consume_pending":
            payload = ConsumePendingWorkflowPayload.model_validate(payload).model_dump(
                exclude_none=True
            )
        if self.workflow == "cleanup":
            payload = CleanupWorkflowPayload.model_validate(payload).model_dump(exclude_none=True)

        self.payload = payload
        return self
