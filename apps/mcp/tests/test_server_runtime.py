from __future__ import annotations

from typing import Any, Self

import httpx
import pytest

from apps.mcp import server
from apps.mcp.server import ApiClient, ApiConfig, ApiError


class _DummyClient:
    def __init__(
        self, response: httpx.Response | None = None, exc: Exception | None = None
    ) -> None:
        self._response = response
        self._exc = exc

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def request(self, **kwargs: Any) -> httpx.Response:
        if self._exc is not None:
            raise self._exc
        assert self._response is not None
        return self._response


def _response(
    *,
    status_code: int = 200,
    json_body: Any | None = None,
    text: str = "",
    content_type: str = "application/json",
) -> httpx.Response:
    request = httpx.Request("GET", "http://example.test/path")
    if json_body is not None:
        return httpx.Response(
            status_code=status_code,
            json=json_body,
            headers={"content-type": content_type},
            request=request,
        )
    return httpx.Response(
        status_code=status_code,
        text=text,
        headers={"content-type": content_type},
        request=request,
    )


def test_api_client_sets_authorization_and_maps_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_headers: dict[str, str] = {}

    class _CaptureClient(_DummyClient):
        def request(self, **kwargs: Any) -> httpx.Response:
            nonlocal captured_headers
            captured_headers = kwargs["headers"]
            return super().request(**kwargs)

    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _CaptureClient(exc=httpx.HTTPError("network down")),
    )
    client = ApiClient(ApiConfig(base_url="http://api", timeout_sec=2, api_key="secret-key"))

    with pytest.raises(ApiError) as exc_info:
        client.request("GET", "/healthz")

    assert captured_headers["Authorization"] == "Bearer secret-key"
    assert exc_info.value.code == "UPSTREAM_NETWORK_ERROR"


def test_api_client_handles_empty_and_binary_and_list_json(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        _response(status_code=204, text="", content_type="application/json"),
        _response(text="abc", content_type="application/octet-stream"),
        _response(json_body=[{"id": "item-1"}]),
    ]

    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(response=responses.pop(0)),
    )
    client = ApiClient(
        ApiConfig(base_url="http://api", timeout_sec=2, api_key=None, max_base64_bytes=8)
    )

    assert client.request("GET", "/empty") == {"ok": True}

    binary_payload = client.request("GET", "/asset", return_bytes_base64=True)
    assert binary_payload["base64"] == "YWJj"
    assert binary_payload["size_bytes"] == 3

    list_payload = client.request("GET", "/items")
    assert list_payload == {"items": [{"id": "item-1"}]}


def test_api_client_handles_invalid_json_and_path_control_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_json_response = httpx.Response(
        status_code=200,
        content=b"{",
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://example.test/path"),
    )
    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(response=invalid_json_response),
    )
    client = ApiClient(ApiConfig(base_url="http://api", timeout_sec=2, api_key=None))

    assert client.request("GET", "/broken-json") == {"text": "{"}

    with pytest.raises(ApiError) as exc_info:
        client.request("GET", "/api/v1/\njobs")
    assert exc_info.value.code == "INVALID_UPSTREAM_PATH"


def test_api_client_http_error_with_invalid_json_body_uses_text_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        status_code=500,
        content=b"{",
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://example.test/path"),
    )
    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(response=response),
    )
    client = ApiClient(ApiConfig(base_url="http://api", timeout_sec=2, api_key=None))

    with pytest.raises(ApiError) as exc_info:
        client.request("GET", "/broken-upstream")

    assert exc_info.value.code == "UPSTREAM_HTTP_ERROR"
    assert exc_info.value.details["body_preview"] == "{"


def test_classify_upstream_operation_uses_path_family_and_outcome() -> None:
    assert server._classify_upstream_operation("/api/v1/jobs/job-123", "json_dict") == (
        "jobs.json_dict"
    )
    assert server._classify_upstream_operation("/healthz", "timeout") == "health.timeout"


def test_api_client_logs_binary_operation_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(
            response=_response(text="abc", content_type="application/octet-stream")
        ),
    )
    monkeypatch.setattr(server, "_log_mcp_api_event", lambda **kwargs: events.append(kwargs))
    client = ApiClient(
        ApiConfig(base_url="http://api", timeout_sec=2, api_key=None, max_base64_bytes=8)
    )

    payload = client.request("GET", "/api/v1/artifacts/file.bin", return_bytes_base64=True)

    assert payload["base64"] == "YWJj"
    assert events[-1]["upstream_operation"] == "artifacts.binary"


def test_api_client_timeout_error_includes_operation_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(exc=httpx.TimeoutException("timed out")),
    )
    monkeypatch.setattr(server, "_log_mcp_api_event", lambda **kwargs: events.append(kwargs))
    client = ApiClient(ApiConfig(base_url="http://api", timeout_sec=2, api_key=None))

    with pytest.raises(ApiError) as exc_info:
        client.request("GET", "/api/v1/jobs/run-1")

    assert exc_info.value.code == "UPSTREAM_TIMEOUT"
    assert exc_info.value.details["upstream_operation"] == "jobs.timeout"
    assert events[-1]["upstream_operation"] == "jobs.timeout"


def test_api_client_dict_response_uses_payload_correlation_for_log_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(
            response=_response(
                json_body={
                    "ok": True,
                    "run_id": "workflow-run-1",
                    "trace_id": "trace-1",
                    "request_id": "req-upstream-1",
                }
            )
        ),
    )
    monkeypatch.setattr(server, "_log_mcp_api_event", lambda **kwargs: events.append(kwargs))
    client = ApiClient(ApiConfig(base_url="http://api", timeout_sec=2, api_key=None))

    payload = client.request("GET", "/api/v1/workflows/run-1")

    assert payload["run_id"] == "workflow-run-1"
    assert events[-1]["event"] == "upstream_api_request_completed"
    assert events[-1]["run_id"] == "workflow-run-1"
    assert events[-1]["trace_id"] == "trace-1"
    assert events[-1]["request_id"]
    assert events[-1]["upstream_operation"] == "workflows.json_dict"


def test_api_client_error_payloads_carry_correlation_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apps.mcp.server.httpx.Client",
        lambda timeout: _DummyClient(
            response=_response(
                status_code=502,
                json_body={"message": "upstream down"},
            )
        ),
    )
    client = ApiClient(ApiConfig(base_url="http://api", timeout_sec=2, api_key=None))

    with pytest.raises(ApiError) as exc_info:
        client.request("GET", "/api/v1/jobs/job-1")

    assert exc_info.value.details["run_id"]
    assert exc_info.value.details["trace_id"]
    assert exc_info.value.details["request_id"]
    assert exc_info.value.details["upstream_operation"] == "jobs.http_error"


def test_extract_error_message_supports_detail_list() -> None:
    message = server._extract_error_message(
        {"detail": [{"msg": "bad request"}]}, fallback="fallback"
    )
    assert '"msg": "bad request"' in message


def test_extract_error_message_uses_string_and_fallback_paths() -> None:
    assert (
        server._extract_error_message(" upstream failed ", fallback="fallback") == "upstream failed"
    )
    assert server._extract_error_message(None, fallback="fallback") == "fallback"


def test_stringify_value_handles_none_and_non_serializable_data() -> None:
    assert server._stringify_value(None) == ""
    assert server._stringify_value({1}) == "{1}"


def test_api_config_from_env_reads_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_BASE_URL", "http://127.0.0.1:8000/")
    monkeypatch.setenv("SOURCE_HARBOR_API_TIMEOUT_SEC", "7")
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "test-key")
    monkeypatch.setenv("SOURCE_HARBOR_MCP_MAX_BASE64_BYTES", "0")

    config = ApiConfig.from_env()

    assert config.base_url == "http://127.0.0.1:8000"
    assert config.timeout_sec == 7.0
    assert config.api_key == "test-key"
    assert config.max_base64_bytes == 1


def test_api_config_from_env_falls_back_for_invalid_numeric_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_BASE_URL", raising=False)
    monkeypatch.setenv("SOURCE_HARBOR_API_TIMEOUT_SEC", "oops")
    monkeypatch.setenv("SOURCE_HARBOR_MCP_MAX_BASE64_BYTES", "invalid")

    config = ApiConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9000"
    assert config.timeout_sec == 20.0
    assert config.max_base64_bytes == 2 * 1024 * 1024


def test_create_server_registers_tools_and_normalizes_error_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder: dict[str, Any] = {"api_call": None, "request_calls": []}

    class FakeFastMCP:
        def __init__(self, name: str) -> None:
            self.name = name
            self.ran = False

        def run(self) -> None:
            self.ran = True

    class FakeApiClient:
        def __init__(self, config: ApiConfig) -> None:
            self.config = config

        def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
            recorder["request_calls"].append({"method": method, "path": path, "kwargs": kwargs})
            if path == "/raise/apierror":
                raise ApiError(
                    "UPSTREAM_HTTP_ERROR",
                    "token=abc123",
                    {"method": method, "path": path, "status_code": 502},
                )
            if path == "/raise/unexpected":
                raise RuntimeError("boom with api_key=leak")
            return {"ok": True}

    def _register_tool(_mcp: Any, api_call: Any) -> None:
        recorder["api_call"] = api_call

    monkeypatch.setattr(server, "FastMCP", FakeFastMCP)
    monkeypatch.setattr(
        server,
        "ApiConfig",
        type("_C", (), {"from_env": staticmethod(lambda: ApiConfig("http://api", 1, None))}),
    )
    monkeypatch.setattr(server, "ApiClient", FakeApiClient)
    monkeypatch.setattr(server, "register_subscription_tools", _register_tool)
    monkeypatch.setattr(server, "register_ingest_tools", _register_tool)
    monkeypatch.setattr(server, "register_job_tools", _register_tool)
    monkeypatch.setattr(server, "register_feed_tools", _register_tool)
    monkeypatch.setattr(server, "register_knowledge_tools", _register_tool)
    monkeypatch.setattr(server, "register_artifact_tools", _register_tool)
    monkeypatch.setattr(server, "register_notification_tools", _register_tool)
    monkeypatch.setattr(server, "register_reader_tools", _register_tool)
    monkeypatch.setattr(server, "register_report_tools", _register_tool)
    monkeypatch.setattr(server, "register_health_tools", _register_tool)
    monkeypatch.setattr(server, "register_workflow_tools", _register_tool)
    monkeypatch.setattr(server, "register_retrieval_tools", _register_tool)
    monkeypatch.setattr(server, "register_computer_use_tools", _register_tool)
    monkeypatch.setattr(server, "register_ui_audit_tools", _register_tool)

    mcp = server.create_server()
    assert isinstance(mcp, FakeFastMCP)
    assert mcp.name == "sourceharbor"
    api_call = recorder["api_call"]
    assert api_call is not None

    ok_payload = api_call(
        "POST",
        "/ok",
        params={"include": "yes", "skip": None},
        json_body={"name": "demo", "optional": None},
        return_bytes_base64=True,
    )
    assert ok_payload == {"ok": True}
    assert recorder["request_calls"][0]["kwargs"]["params"] == {"include": "yes"}
    assert recorder["request_calls"][0]["kwargs"]["json_body"] == {"name": "demo"}

    api_error_payload = api_call("GET", "/raise/apierror")
    assert api_error_payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert "abc123" not in api_error_payload["message"]

    internal_error_payload = api_call("GET", "/raise/unexpected")
    assert internal_error_payload["code"] == "MCP_INTERNAL_ERROR"
    assert internal_error_payload["details"]["path"] == "/raise/unexpected"
    assert "leak" not in internal_error_payload["details"]["error"]


def test_main_runs_server(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Runnable:
        def __init__(self) -> None:
            self.called = False

        def run(self) -> None:
            self.called = True

    runnable = _Runnable()
    monkeypatch.setattr(server, "create_server", lambda: runnable)

    server.main()

    assert runnable.called is True


def test_api_config_from_env_defaults_to_local_9000(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_BASE_URL", raising=False)

    config = server.ApiConfig.from_env()

    assert config.base_url == "http://127.0.0.1:9000"
