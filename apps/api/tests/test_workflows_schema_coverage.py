from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.api.app.schemas.workflows import CleanupWorkflowPayload, WorkflowRunRequest


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("workspace_dir", "   ", "cleanup path cannot be blank"),
        ("cache_dir", "bad\x00path", "cleanup path contains null byte"),
        (
            "workspace_dir",
            "https://example.com/tmp",
            "cleanup path must be a local filesystem path",
        ),
        ("cache_dir", "a/../b", "cleanup path cannot contain parent traversal segments"),
    ],
)
def test_cleanup_workflow_payload_rejects_invalid_paths(
    field: str, value: str, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        CleanupWorkflowPayload.model_validate({field: value})


def test_workflow_run_request_rejects_payload_too_many_keys() -> None:
    payload = {f"k{i}": i for i in range(33)}
    with pytest.raises(ValidationError, match="payload has too many keys"):
        WorkflowRunRequest.model_validate({"workflow": "poll_feeds", "payload": payload})


def test_workflow_run_request_rejects_non_string_payload_keys_via_construct() -> None:
    request = WorkflowRunRequest.model_construct(
        workflow="poll_feeds",
        run_once=True,
        wait_for_result=False,
        workflow_id=None,
        payload={1: "x"},
    )
    with pytest.raises(ValueError, match="payload keys must be strings"):
        request.validate_payload()


def test_workflow_run_request_rejects_oversized_payload_key() -> None:
    with pytest.raises(ValidationError, match="payload key length exceeds 64 characters"):
        WorkflowRunRequest.model_validate({"workflow": "poll_feeds", "payload": {"x" * 65: 1}})


def test_workflow_run_request_cleanup_payload_is_normalized() -> None:
    request = WorkflowRunRequest.model_validate(
        {
            "workflow": "cleanup",
            "payload": {
                "workspace_dir": "/tmp/workspace",
                "cache_dir": "/tmp/cache",
                "interval_hours": 2,
            },
        }
    )
    assert request.payload == {
        "workspace_dir": "/tmp/workspace",
        "cache_dir": "/tmp/cache",
        "interval_hours": 2,
    }


def test_workflow_run_request_poll_feeds_payload_is_normalized() -> None:
    request = WorkflowRunRequest.model_validate(
        {
            "workflow": "poll_feeds",
            "payload": {
                "interval_minutes": 15,
                "max_new_videos": 25,
            },
        }
    )
    assert request.payload == {
        "interval_minutes": 15,
        "max_new_videos": 25,
    }


def test_workflow_run_request_poll_feeds_rejects_invalid_interval_minutes() -> None:
    with pytest.raises(ValidationError, match="interval_minutes"):
        WorkflowRunRequest.model_validate(
            {
                "workflow": "poll_feeds",
                "payload": {"interval_minutes": 0},
            }
        )
