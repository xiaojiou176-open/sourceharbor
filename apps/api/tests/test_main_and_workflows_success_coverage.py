from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from apps.api.app import main as main_module

pytestmark = pytest.mark.allow_unauth_write


def _request(
    path: str, *, headers: list[tuple[bytes, bytes]] | None = None, route_path: str | None = None
) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "headers": headers or [],
        "query_string": b"",
        "scheme": "http",
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    if route_path is not None:
        scope["route"] = SimpleNamespace(path=route_path)
    return Request(scope)


def test_readyz_returns_ok_status(api_client: TestClient) -> None:
    response = api_client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_request_helpers_cover_traceparent_and_route_fallback() -> None:
    trace_request = _request(
        "/healthz",
        headers=[(b"traceparent", b"00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01")],
    )
    assert main_module._resolve_trace_id(trace_request) == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    route_request = _request("/metrics", route_path="  /metrics  ")
    assert main_module._request_route_label(route_request) == "/metrics"

    fallback_request = _request("/fallback-path")
    assert main_module._request_route_label(fallback_request) == "/fallback-path"


def test_request_observability_middleware_records_error_metrics() -> None:
    request = _request("/boom")
    before_counter = dict(main_module._REQUEST_COUNTER)
    before_duration = {
        key: {"count": value["count"], "sum": value["sum"]}
        for key, value in main_module._REQUEST_DURATION.items()
    }

    async def _boom(_: Request):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(main_module.request_observability_middleware(request, _boom))

    key = ("GET", "/boom", "500")
    assert main_module._REQUEST_COUNTER[key] == before_counter.get(key, 0) + 1
    assert (
        main_module._REQUEST_DURATION[("GET", "/boom")]["count"]
        == before_duration.get(
            ("GET", "/boom"),
            {"count": 0.0},
        )["count"]
        + 1.0
    )


def test_workflows_run_wait_for_result_success_returns_completed_payload(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    class _Handle:
        id = "wf-id-completed"
        run_id = "run-id-completed"
        first_execution_run_id = "run-id-completed"

        async def result(self):
            return {"status": "done"}

    class _Connected:
        async def start_workflow(self, *args, **kwargs):
            del args, kwargs
            return _Handle()

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs
            return _Connected()

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": True,
            "payload": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["run_id"] == "run-id-completed"
    assert payload["result"] == {"status": "done"}


def test_workflows_run_uses_stable_workflow_id_for_non_run_once_requests(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    captured: dict[str, object] = {}

    class _Handle:
        id = "provider_canary-workflow"
        run_id = "run-id-started"
        first_execution_run_id = "run-id-started"

    class _Connected:
        async def start_workflow(self, workflow_name, request_payload, **kwargs):
            captured["workflow_name"] = workflow_name
            captured["request_payload"] = request_payload
            captured["kwargs"] = kwargs
            return _Handle()

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs
            return _Connected()

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": False,
            "wait_for_result": False,
            "payload": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["workflow_id"] == "provider_canary-workflow"
    assert captured["workflow_name"] == "ProviderCanaryWorkflow"
    assert captured["request_payload"] == {"run_once": False}
    assert captured["kwargs"] == {
        "id": "provider_canary-workflow",
        "task_queue": "sourceharbor-worker",
    }


def test_workflows_run_supports_consume_pending_requests(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    captured: dict[str, object] = {}

    class _Handle:
        id = "consume_pending-workflow"
        run_id = "run-id-consume"
        first_execution_run_id = "run-id-consume"

    class _Connected:
        async def start_workflow(self, workflow_name, request_payload, **kwargs):
            captured["workflow_name"] = workflow_name
            captured["request_payload"] = request_payload
            captured["kwargs"] = kwargs
            return _Handle()

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs
            return _Connected()

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "consume_pending",
            "run_once": False,
            "payload": {"interval_minutes": 120, "timezone_name": "America/Los_Angeles"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["workflow_id"] == "consume_pending-workflow"
    assert captured["workflow_name"] == "ConsumePendingWorkflow"
    assert captured["request_payload"] == {
        "interval_minutes": 120,
        "timezone_name": "America/Los_Angeles",
        "run_once": False,
    }
    assert captured["kwargs"] == {
        "id": "consume_pending-workflow",
        "task_queue": "sourceharbor-worker",
    }
