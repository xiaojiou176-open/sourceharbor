from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

WorkflowName = Literal[
    "poll_feeds", "daily_digest", "notification_retry", "cleanup", "provider_canary"
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

        if self.workflow == "cleanup":
            payload = CleanupWorkflowPayload.model_validate(payload).model_dump(exclude_none=True)

        self.payload = payload
        return self
