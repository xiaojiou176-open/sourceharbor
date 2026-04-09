from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.mcp.tools.ingest import register_ingest_tools
from apps.mcp.tools.workflows import _normalize_workflow_payload, register_workflow_tools

UUID_1 = "11111111-1111-1111-1111-111111111111"


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., dict[str, Any]]] = {}

    def tool(self, *, name: str, description: str):
        def _decorator(func: Callable[..., dict[str, Any]]):
            self.tools[name] = func
            return func

        return _decorator


def test_ingest_poll_rejects_invalid_subscription_id() -> None:
    mcp = _FakeMCP()
    register_ingest_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.ingest.poll"](subscription_id="sub-1")

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "subscription_id"
    assert payload["details"]["path"] == "/api/v1/ingest/poll"


def test_ingest_poll_rejects_invalid_max_new_videos() -> None:
    mcp = _FakeMCP()
    register_ingest_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.ingest.poll"](max_new_videos=0)

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "max_new_videos"


def test_ingest_poll_posts_expected_payload_with_normalized_uuid() -> None:
    mcp = _FakeMCP()
    calls: list[dict[str, Any]] = []

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "kwargs": kwargs})
        return {
            "run_id": UUID_1,
            "workflow_id": "wf-ingest-0",
            "status": "queued",
            "enqueued": 0,
            "candidates": [],
        }

    register_ingest_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.ingest.poll"](
        subscription_id=UUID_1.upper(),
        platform="youtube",
        max_new_videos=10,
    )

    assert payload["run_id"] == UUID_1
    assert payload["workflow_id"] == "wf-ingest-0"
    assert calls == [
        {
            "method": "POST",
            "path": "/api/v1/ingest/poll",
            "kwargs": {
                "json_body": {
                    "subscription_id": UUID_1,
                    "platform": "youtube",
                    "max_new_videos": 10,
                }
            },
        }
    ]


def test_ingest_poll_normalizes_run_response() -> None:
    mcp = _FakeMCP()

    register_ingest_tools(
        mcp,
        lambda *_args, **_kwargs: {
            "run_id": UUID_1,
            "workflow_id": "wf-ingest-1",
            "status": "queued",
            "enqueued": 0,
            "candidates": [],
        },
    )

    payload = mcp.tools["sourceharbor.ingest.poll"](platform="youtube")

    assert payload["run_id"] == UUID_1
    assert payload["workflow_id"] == "wf-ingest-1"
    assert payload["status"] == "queued"
    assert payload["enqueued"] == 0


def test_ingest_runs_list_and_get_normalize_payloads() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> Any:
        if method == "GET" and path == "/api/v1/ingest/runs":
            return [
                {
                    "id": UUID_1,
                    "subscription_id": None,
                    "workflow_id": "wf-ingest-2",
                    "platform": "youtube",
                    "max_new_videos": 5,
                    "status": "succeeded",
                    "jobs_created": 2,
                    "candidates_count": 2,
                    "feeds_polled": 1,
                    "entries_fetched": 2,
                    "entries_normalized": 2,
                    "ingest_events_created": 2,
                    "ingest_event_duplicates": 0,
                    "job_duplicates": 0,
                    "error_message": None,
                    "created_at": "2026-03-29T00:00:00Z",
                    "updated_at": "2026-03-29T00:00:00Z",
                    "completed_at": "2026-03-29T00:01:00Z",
                }
            ]
        if method == "GET" and path == f"/api/v1/ingest/runs/{UUID_1}":
            return {
                "id": UUID_1,
                "subscription_id": None,
                "workflow_id": "wf-ingest-2",
                "platform": "youtube",
                "max_new_videos": 5,
                "status": "succeeded",
                "jobs_created": 2,
                "candidates_count": 2,
                "feeds_polled": 1,
                "entries_fetched": 2,
                "entries_normalized": 2,
                "ingest_events_created": 2,
                "ingest_event_duplicates": 0,
                "job_duplicates": 0,
                "error_message": None,
                "created_at": "2026-03-29T00:00:00Z",
                "updated_at": "2026-03-29T00:00:00Z",
                "completed_at": "2026-03-29T00:01:00Z",
                "requested_by": "tester",
                "requested_trace_id": "trace-1",
                "filters_json": {"platform": "youtube"},
                "items": [
                    {
                        "id": "item-1",
                        "subscription_id": None,
                        "video_id": "video-1",
                        "job_id": "job-1",
                        "ingest_event_id": "event-1",
                        "platform": "youtube",
                        "video_uid": "abc123",
                        "source_url": "https://example.com/watch?v=abc123",
                        "title": "Demo",
                        "published_at": "2026-03-29T00:00:00Z",
                        "entry_hash": "entry-1",
                        "pipeline_mode": "full",
                        "content_type": "video",
                        "item_status": "queued",
                        "created_at": "2026-03-29T00:00:00Z",
                        "updated_at": "2026-03-29T00:00:00Z",
                    }
                ],
            }
        raise AssertionError(f"unexpected api call: {method} {path} {kwargs}")

    register_ingest_tools(mcp, fake_api_call)

    list_payload = mcp.tools["sourceharbor.ingest.runs.list"](
        platform="youtube",
        status="succeeded",
        limit=5,
    )
    get_payload = mcp.tools["sourceharbor.ingest.runs.get"](run_id=UUID_1)

    assert list_payload["items"][0]["id"] == UUID_1
    assert list_payload["items"][0]["workflow_id"] == "wf-ingest-2"
    assert get_payload["id"] == UUID_1
    assert get_payload["requested_by"] == "tester"
    assert get_payload["items"][0]["job_id"] == "job-1"


def test_ingest_runs_get_rejects_invalid_run_id() -> None:
    mcp = _FakeMCP()
    register_ingest_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.ingest.runs.get"](run_id="bad-run-id")

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "run_id"


def test_workflows_run_rejects_invalid_workflow_id() -> None:
    mcp = _FakeMCP()
    register_workflow_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.workflows.run"](
        workflow="daily_digest",
        workflow_id="bad workflow id",
    )

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "workflow_id"


def test_workflows_run_rejects_unknown_workflow_name() -> None:
    mcp = _FakeMCP()
    register_workflow_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.workflows.run"](workflow="not-supported")

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "workflow"


def test_workflows_run_passes_through_error_payload_from_upstream() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/workflows/run"
        assert kwargs["json_body"]["workflow"] == "daily_digest"
        return {
            "code": "UPSTREAM_HTTP_ERROR",
            "message": "gateway unavailable",
            "details": {"status_code": 503},
        }

    register_workflow_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.workflows.run"](workflow="daily_digest")

    assert payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert payload["details"]["status_code"] == 503


def test_workflows_run_rejects_invalid_boolean_flags() -> None:
    mcp = _FakeMCP()
    calls = 0

    def fake_api_call(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"ok": True}

    register_workflow_tools(mcp, fake_api_call)

    bad_run_once = mcp.tools["sourceharbor.workflows.run"](
        workflow="daily_digest",
        run_once="true",  # type: ignore[arg-type]
    )
    bad_wait_for_result = mcp.tools["sourceharbor.workflows.run"](
        workflow="daily_digest",
        wait_for_result="false",  # type: ignore[arg-type]
    )

    assert bad_run_once["code"] == "INVALID_ARGUMENT"
    assert bad_run_once["details"]["field"] == "run_once"
    assert bad_wait_for_result["code"] == "INVALID_ARGUMENT"
    assert bad_wait_for_result["details"]["field"] == "wait_for_result"
    assert calls == 0


def test_workflows_run_rejects_invalid_payload_value_ranges() -> None:
    mcp = _FakeMCP()
    register_workflow_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.workflows.run"](
        workflow="daily_digest",
        payload={"local_hour": 30},
    )

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "payload.local_hour"


def test_workflows_payload_normalizer_covers_bool_and_range_branches() -> None:
    invalid_payload, field, error = _normalize_workflow_payload(
        "poll_feeds",
        {"run_once": "yes"},
    )
    assert invalid_payload is None
    assert field == "run_once"
    assert error == "payload.run_once must be a boolean"

    poll_feeds, field, error = _normalize_workflow_payload(
        "poll_feeds",
        {"run_once": True, "max_new_videos": 25},
    )
    assert error is None and field is None
    assert poll_feeds == {"run_once": True, "max_new_videos": 25}

    poll_with_interval, field, error = _normalize_workflow_payload(
        "poll_feeds",
        {"run_once": False, "interval_minutes": 15},
    )
    assert error is None and field is None
    assert poll_with_interval == {"run_once": False, "interval_minutes": 15}

    consume_pending, field, error = _normalize_workflow_payload(
        "consume_pending",
        {"run_once": False, "interval_minutes": 120, "timezone_name": "America/Los_Angeles"},
    )
    assert error is None and field is None
    assert consume_pending == {
        "run_once": False,
        "interval_minutes": 120,
        "timezone_name": "America/Los_Angeles",
    }

    notification_retry, field, error = _normalize_workflow_payload(
        "notification_retry",
        {"interval_minutes": 15, "retry_batch_limit": 9},
    )
    assert error is None and field is None
    assert notification_retry == {"interval_minutes": 15, "retry_batch_limit": 9}

    provider_canary, field, error = _normalize_workflow_payload(
        "provider_canary",
        {"interval_hours": 4, "timeout_seconds": 60},
    )
    assert error is None and field is None
    assert provider_canary == {"interval_hours": 4, "timeout_seconds": 60}
