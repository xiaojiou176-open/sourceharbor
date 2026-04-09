from __future__ import annotations

import base64
import importlib
from collections.abc import Callable
from typing import Any

from apps.mcp.tools._common import (
    DEFAULT_MAX_BASE64_BYTES,
    invalid_argument,
    is_error_payload,
    to_int,
    to_optional_bool,
    to_optional_dict,
    to_optional_int,
    to_optional_str,
    validate_base64_size,
)
from apps.mcp.tools.artifacts import _normalize_markdown_payload, register_artifact_tools
from apps.mcp.tools.computer_use import _normalize_action_item, register_computer_use_tools
from apps.mcp.tools.health import register_health_tools
from apps.mcp.tools.jobs import _normalize_job_payload, register_job_tools
from apps.mcp.tools.notifications import (
    _normalize_send_test_payload,
    _normalize_set_config_payload,
    register_notification_tools,
)
from apps.mcp.tools.reader import register_reader_tools
from apps.mcp.tools.retrieval import register_retrieval_tools
from apps.mcp.tools.subscriptions import register_subscription_tools
from apps.mcp.tools.ui_audit import register_ui_audit_tools
from apps.mcp.tools.workflows import _normalize_workflow_payload, register_workflow_tools

UUID_1 = "11111111-1111-1111-1111-111111111111"
UUID_2 = "22222222-2222-2222-2222-222222222222"


def test_common_normalizers_handle_basic_types() -> None:
    assert is_error_payload({"code": "E", "message": "bad", "details": {"x": 1}}) is True
    assert is_error_payload({"code": "E", "message": "bad"}) is False
    assert to_optional_str("abc") == "abc"
    assert to_optional_str(1) is None
    assert to_int("7", default=0) == 7
    assert to_int("x", default=3) == 3
    assert to_int(True, default=3) == 3
    assert to_optional_dict({"x": 1}) == {"x": 1}
    assert to_optional_dict("x") is None
    assert to_optional_bool(True) is True
    assert to_optional_bool(1) is None
    assert to_optional_int(5) == 5
    assert to_optional_int(True) is None
    assert to_optional_int("5") is None


def test_invalid_argument_masks_value_without_plaintext_leakage() -> None:
    value_parts = ("sk", "super", "secret", "token", "value", "1234567890")
    raw_value = (
        f"{value_parts[0]}-{value_parts[1]}-{value_parts[2]}-"
        f"{value_parts[3]}-{value_parts[4]}-{value_parts[5]}"
    )
    payload = invalid_argument(
        "bad input",
        method="POST",
        path="/api/v1/example",
        field="token",
        value=raw_value,
    )

    masked = payload["details"]["value"]
    assert isinstance(masked, str)
    assert masked.startswith("<redacted type=str len=")
    assert "sha256=" in masked
    assert raw_value not in masked


def test_default_max_base64_bytes_falls_back_when_env_invalid(monkeypatch) -> None:
    import apps.mcp.tools._common as common_module

    monkeypatch.setenv("SOURCE_HARBOR_MCP_MAX_BASE64_BYTES", "not-a-number")
    reloaded = importlib.reload(common_module)
    assert reloaded.DEFAULT_MAX_BASE64_BYTES == 2 * 1024 * 1024

    monkeypatch.delenv("SOURCE_HARBOR_MCP_MAX_BASE64_BYTES", raising=False)
    importlib.reload(common_module)


def test_validate_base64_size_fast_rejects_oversized_encoded_input() -> None:
    ok, message = validate_base64_size("A" * 9, max_bytes=4)
    assert ok is False
    assert message == "decoded payload exceeds 4 bytes"


def test_artifact_normalizer_marks_payload_found_when_markdown_present() -> None:
    payload = _normalize_markdown_payload(
        {
            "markdown": "# digest",
            "job_id": "job-1",
            "video_url": "https://example.com/video",
        }
    )

    assert payload["found"] is True
    assert payload["markdown"] == "# digest"
    assert payload["job_id"] == "job-1"


def test_job_normalizer_keeps_extended_pipeline_fields() -> None:
    normalized = _normalize_job_payload(
        {
            "id": "job-1",
            "status": "running",
            "mode": "text_only",
            "pipeline_final_status": "degraded",
            "llm_required": True,
            "llm_gate_passed": False,
            "hard_fail_reason": "llm_provider_unavailable",
            "artifacts_index": {
                "digest_markdown": "/tmp/artifacts/digest.md",
                "step_json": "/tmp/artifacts/steps.json",
            },
            "step_summary": [
                {
                    "name": "fetch_metadata",
                    "status": "succeeded",
                    "attempt": 1,
                    "started_at": "2026-02-21T10:00:00Z",
                    "finished_at": "2026-02-21T10:00:03Z",
                }
            ],
            "steps": [
                {
                    "name": "llm_digest",
                    "status": "failed",
                    "attempt": 2,
                    "started_at": "2026-02-21T10:01:00Z",
                    "finished_at": "2026-02-21T10:01:02Z",
                    "error": {"detail": "upstream timeout"},
                    "error_kind": "timeout",
                    "retry_meta": {"max_attempts": 2},
                    "result": {"degraded": True, "provider": "gemini"},
                    "thought_metadata": {"provider": "gemini", "thought_tokens": 32},
                    "cache_key": "llm_digest:v1",
                }
            ],
        }
    )

    assert normalized["pipeline_final_status"] == "degraded"
    assert normalized["hard_fail_reason"] == "llm_provider_unavailable"
    assert normalized["steps"][0]["cache_key"] == "llm_digest:v1"


def test_notification_normalizers_return_expected_core_fields() -> None:
    send_test = _normalize_send_test_payload(
        {
            "delivery_id": "delivery-1",
            "status": "sent",
            "provider_message_id": "provider-1",
            "recipient_email": "demo@example.com",
            "subject": "hello",
            "created_at": "2026-02-21T10:00:00Z",
        }
    )
    set_config = _normalize_set_config_payload(
        {
            "enabled": True,
            "to_email": "demo@example.com",
            "daily_digest_enabled": False,
            "daily_digest_hour_utc": 8,
            "failure_alert_enabled": True,
            "updated_at": "2026-02-21T10:00:00Z",
        }
    )

    assert send_test["delivery_id"] == "delivery-1"
    assert set_config["enabled"] is True


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., dict[str, Any]]] = {}

    def tool(self, *, name: str, description: str):
        def _decorator(func: Callable[..., dict[str, Any]]):
            self.tools[name] = func
            return func

        return _decorator


def test_health_get_tool_merges_system_and_providers() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if path == "/healthz":
            return {"status": "ok"}
        assert path == "/api/v1/health/providers"
        assert kwargs["params"]["window_hours"] == 12
        return {
            "window_hours": 12,
            "providers": [{"provider": "rsshub", "ok": 1, "warn": 0, "fail": 0}],
        }

    register_health_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.health.get"](scope="all", window_hours=12)

    assert payload["system"]["status"] == "ok"
    assert payload["providers"]["window_hours"] == 12
    assert payload["providers"]["items"][0]["provider"] == "rsshub"


def test_subscriptions_manage_supports_list_upsert_remove() -> None:
    mcp = _FakeMCP()
    calls: list[dict[str, Any]] = []

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "kwargs": kwargs})
        return {"ok": True}

    register_subscription_tools(mcp, fake_api_call)
    assert (
        mcp.tools["sourceharbor.subscriptions.manage"](action="list", platform="youtube")["ok"]
        is True
    )
    assert (
        mcp.tools["sourceharbor.subscriptions.manage"](
            action="upsert",
            platform="youtube",
            source_type="url",
            source_value="https://youtube.com/@demo",
        )["ok"]
        is True
    )
    assert (
        mcp.tools["sourceharbor.subscriptions.manage"](
            action="batch_update_category",
            ids=[UUID_1, UUID_2],
            category="macro",
        )["ok"]
        is True
    )
    assert mcp.tools["sourceharbor.subscriptions.manage"](action="remove", id=UUID_1)["ok"] is True

    assert calls[0]["method"] == "GET"
    assert calls[1]["method"] == "POST"
    assert calls[2]["method"] == "POST"
    assert calls[3]["method"] == "DELETE"


def test_notifications_manage_supports_get_set_send_daily_and_category_send() -> None:
    mcp = _FakeMCP()
    calls: list[tuple[str, str]] = []

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((method, path))
        if path == "/api/v1/notifications/config" and method == "GET":
            return {"enabled": True, "daily_digest_hour_utc": 8}
        if path == "/api/v1/notifications/config" and method == "PUT":
            return {"enabled": True, "daily_digest_hour_utc": 8}
        if path == "/api/v1/notifications/test":
            return {"delivery_id": "d-1", "status": "sent"}
        if path == "/api/v1/reports/daily/send":
            return {"sent": True, "status": "sent", "delivery_id": "d-2"}
        if path == "/api/v1/notifications/category/send":
            return {"delivery_id": "d-3", "status": "sent"}
        raise AssertionError(f"unexpected call: {method} {path}")

    register_notification_tools(mcp, fake_api_call)
    assert mcp.tools["sourceharbor.notifications.manage"](action="get_config")["enabled"] is True
    assert (
        mcp.tools["sourceharbor.notifications.manage"](action="set_config", enabled=True)["enabled"]
        is True
    )
    assert mcp.tools["sourceharbor.notifications.manage"](action="send_test")["status"] == "sent"
    assert mcp.tools["sourceharbor.notifications.manage"](action="daily_send")["sent"] is True
    assert (
        mcp.tools["sourceharbor.notifications.manage"](
            action="category_send", category="tech", body="digest"
        )["status"]
        == "sent"
    )
    assert calls == [
        ("GET", "/api/v1/notifications/config"),
        ("PUT", "/api/v1/notifications/config"),
        ("POST", "/api/v1/notifications/test"),
        ("POST", "/api/v1/reports/daily/send"),
        ("POST", "/api/v1/notifications/category/send"),
    ]


def test_notifications_manage_rejects_invalid_action_with_standard_payload() -> None:
    mcp = _FakeMCP()
    register_notification_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.notifications.manage"](action="invalid")

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "action"
    assert payload["details"]["path"] == "sourceharbor.notifications.manage"


def test_reader_tools_cover_list_get_and_navigation() -> None:
    mcp = _FakeMCP()
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_api_call(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if path == "/api/v1/reader/documents":
            return [
                {
                    "id": UUID_1,
                    "stable_key": "topic-ai-agents-2026-04-09",
                    "slug": "topic-ai-agents-2026-04-09-v1",
                    "window_id": "2026-04-09@America/Los_Angeles",
                    "title": "AI Agents",
                    "markdown": "# AI Agents",
                    "materialization_mode": "merge_then_polish",
                    "version": 1,
                    "published_with_gap": False,
                    "source_item_count": 2,
                }
            ]
        if path == f"/api/v1/reader/documents/{UUID_1}":
            return {
                "id": UUID_1,
                "stable_key": "topic-ai-agents-2026-04-09",
                "slug": "topic-ai-agents-2026-04-09-v1",
                "window_id": "2026-04-09@America/Los_Angeles",
                "title": "AI Agents",
                "markdown": "# AI Agents",
                "materialization_mode": "merge_then_polish",
                "version": 1,
                "published_with_gap": True,
                "warning": {"published_with_gap": True, "reasons": ["1 source missing digest"]},
            }
        assert path == "/api/v1/reader/navigation-brief"
        return {
            "brief_kind": "sourceharbor_navigation_brief_v1",
            "generated_at": "2026-04-09T12:00:00Z",
            "window_id": "2026-04-09@America/Los_Angeles",
            "document_count": 1,
            "published_with_gap_count": 1,
            "summary": "Read 1 published reader documents.",
            "items": [{"document_id": UUID_1, "title": "AI Agents", "route": f"/reader/{UUID_1}"}],
        }

    register_reader_tools(mcp, fake_api_call)

    listed = mcp.tools["sourceharbor.reader.documents.list"](limit=5)
    fetched = mcp.tools["sourceharbor.reader.documents.get"](document_id=UUID_1)
    brief = mcp.tools["sourceharbor.reader.navigation.get"](limit=3)

    assert listed["items"][0]["stable_key"] == "topic-ai-agents-2026-04-09"
    assert fetched["warning"]["published_with_gap"] is True
    assert brief["document_count"] == 1
    assert calls[0][0] == "GET"
    assert calls[1][1] == f"/api/v1/reader/documents/{UUID_1}"
    assert calls[2][1] == "/api/v1/reader/navigation-brief"


def test_artifacts_get_supports_markdown_and_asset() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if path == "/api/v1/artifacts/markdown":
            return {"markdown": "# digest", "job_id": "job-1"}
        if path == "/api/v1/artifacts/assets":
            return {"mime_type": "image/png", "base64": "e30=", "size_bytes": 2}
        raise AssertionError(path)

    register_artifact_tools(mcp, fake_api_call)
    markdown = mcp.tools["sourceharbor.artifacts.get"](kind="markdown", job_id=UUID_1)
    asset = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id=UUID_1, path="frames/f1.png", include_base64=True
    )

    assert markdown["found"] is True
    assert asset["exists"] is True
    assert asset["mime_type"] == "image/png"


def test_retrieval_search_tool_normalizes_payload() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/retrieval/search"
        return {
            "query": "timeout",
            "top_k": 2,
            "filters": {},
            "items": [{"job_id": "job-1", "source": "digest", "score": 1.2}],
        }

    register_retrieval_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.retrieval.search"](query="timeout", top_k=2)
    assert payload["top_k"] == 2
    assert payload["items"][0]["source"] == "digest"


def test_retrieval_search_supports_mode_parameter() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/retrieval/search"
        assert kwargs["json_body"]["mode"] == "semantic"
        return {
            "query": "timeout",
            "top_k": 3,
            "filters": {},
            "items": [{"job_id": "job-1", "source": "digest", "mode": "semantic", "score": 1.2}],
        }

    register_retrieval_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.retrieval.search"](query="timeout", top_k=3, mode="semantic")
    assert payload["top_k"] == 3
    assert payload["items"][0]["mode"] == "semantic"


def test_retrieval_search_rejects_invalid_top_k() -> None:
    mcp = _FakeMCP()
    register_retrieval_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.retrieval.search"](query="x", top_k=0)
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "top_k"


def test_retrieval_search_rejects_top_k_above_schema_limit() -> None:
    mcp = _FakeMCP()
    register_retrieval_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.retrieval.search"](query="x", top_k=51)
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "top_k"


def test_retrieval_search_rejects_invalid_mode() -> None:
    mcp = _FakeMCP()
    register_retrieval_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.retrieval.search"](query="x", top_k=10, mode="vector")
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "mode"


def test_retrieval_search_rejects_empty_query() -> None:
    mcp = _FakeMCP()
    call_count = 0

    def fake_api_call(_method: str, _path: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    register_retrieval_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.retrieval.search"](query="   ", top_k=10)

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "query"
    assert call_count == 0


def test_retrieval_search_normalizes_out_of_schema_upstream_values() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/retrieval/search"
        assert kwargs["json_body"]["query"] == "timeout"
        return {
            "query": "   ",
            "top_k": 999,
            "filters": "invalid",
            "items": [
                {
                    "job_id": "job-1",
                    "platform": "vimeo",
                    "source": "raw",
                    "score": True,
                }
            ],
        }

    register_retrieval_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.retrieval.search"](query=" timeout ", top_k=10)

    assert payload["query"] == "timeout"
    assert payload["top_k"] == 10
    assert payload["filters"] == {}
    assert payload["items"][0]["platform"] is None
    assert payload["items"][0]["source"] is None
    assert payload["items"][0]["score"] == 0.0


def test_retrieval_search_sanitizes_upstream_error_payload() -> None:
    mcp = _FakeMCP()

    def fake_api_call(_method: str, _path: str, **_kwargs: Any) -> dict[str, Any]:
        bearer_parts = ("super", "secret", "token")
        value_parts = ("sk", "top", "secret", "token", "value", "1234567890")
        api_key_parts = ("very", "secret", "value")
        bearer_token = f"{bearer_parts[0]}-{bearer_parts[1]}-{bearer_parts[2]}"
        redacted_value = (
            f"{value_parts[0]}-{value_parts[1]}-{value_parts[2]}-"
            f"{value_parts[3]}-{value_parts[4]}-{value_parts[5]}"
        )
        api_key_value = f"{api_key_parts[0]}-{api_key_parts[1]}-{api_key_parts[2]}"
        return {
            "code": "UPSTREAM_HTTP_ERROR",
            "message": f"Authorization: Bearer {bearer_token}",
            "details": {
                "method": "POST",
                "path": "/api/v1/retrieval/search",
                "status_code": 500,
                "value": redacted_value,
                "error": f"api_key={api_key_value}",
            },
        }

    register_retrieval_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.retrieval.search"](query="timeout", top_k=10)

    assert payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert "super-secret-token" not in payload["message"]
    assert payload["details"]["value"].startswith("<redacted type=str len=")
    assert "very-secret-value" not in payload["details"]["error"]
    assert "[REDACTED]" in payload["details"]["error"]


def test_notifications_manage_rejects_out_of_range_daily_digest_hour_utc() -> None:
    mcp = _FakeMCP()
    call_count = 0

    def fake_api_call(_method: str, _path: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    register_notification_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.notifications.manage"](
        action="set_config",
        daily_digest_hour_utc=24,
    )
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "daily_digest_hour_utc"
    assert call_count == 0


def test_notifications_manage_rejects_out_of_range_priority() -> None:
    mcp = _FakeMCP()
    call_count = 0

    def fake_api_call(_method: str, _path: str, **_kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"ok": True}

    register_notification_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.notifications.manage"](
        action="category_send",
        category="tech",
        priority=101,
    )
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "priority"
    assert call_count == 0


def test_notifications_manage_sanitizes_upstream_error_payload() -> None:
    mcp = _FakeMCP()

    def fake_api_call(_method: str, path: str, **_kwargs: Any) -> dict[str, Any]:
        if path == "/api/v1/reports/daily/send":
            secret_parts = ("another", "secret")
            another_secret = f"{secret_parts[0]}-{secret_parts[1]}"
            return {
                "code": "UPSTREAM_HTTP_ERROR",
                "message": "token=daily-send-secret",
                "details": {
                    "method": "POST",
                    "path": "/api/v1/reports/daily/send",
                    "value": {"token": "json-secret-value"},
                    "error": f"Authorization: Bearer {another_secret}",
                },
            }
        raise AssertionError(path)

    register_notification_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.notifications.manage"](action="daily_send")

    assert payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert "daily-send-secret" not in payload["message"]
    assert payload["details"]["value"].startswith("<redacted type=dict len=")
    assert "another-secret" not in payload["details"]["error"]
    assert "[REDACTED]" in payload["details"]["error"]


def test_workflows_run_tool_posts_expected_body() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/workflows/run"
        return {"workflow": "daily_digest", "workflow_id": "wf-1", "status": "started"}

    register_workflow_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.workflows.run"](workflow="daily_digest")
    assert payload["workflow"] == "daily_digest"


def test_computer_use_run_tool_posts_expected_body_and_normalizes_result() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/computer-use/run"
        return {
            "actions": [{"step": 1, "action": "click", "target": "button"}],
            "require_confirmation": True,
            "blocked_actions": ["submit"],
            "final_text": "Need confirmation.",
            "thought_metadata": {"planner": "gemini_computer_use"},
        }

    register_computer_use_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click", screenshot_base64="ZmFrZQ=="
    )
    assert payload["actions"][0]["action"] == "click"
    assert payload["require_confirmation"] is True


def test_ui_audit_run_and_read_tools() -> None:
    mcp = _FakeMCP()
    run_id = UUID_1

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if path == "/api/v1/ui-audit/run":
            return {
                "run_id": run_id,
                "status": "completed",
                "summary": {
                    "artifact_count": 1,
                    "finding_count": 1,
                    "severity_counts": {"high": 1},
                },
            }
        if path == f"/api/v1/ui-audit/{run_id}":
            return {
                "run_id": run_id,
                "status": "completed",
                "summary": {
                    "artifact_count": 1,
                    "finding_count": 1,
                    "severity_counts": {"high": 1},
                },
            }
        if path == f"/api/v1/ui-audit/{run_id}/findings":
            return {
                "items": [{"id": "f-1", "severity": "high", "title": "contrast", "message": "bad"}]
            }
        if path == f"/api/v1/ui-audit/{run_id}/artifact":
            return {
                "key": "axe.json",
                "path": "/tmp/axe.json",
                "mime_type": "application/json",
                "size_bytes": 10,
                "category": "playwright",
                "exists": True,
                "base64": "e30=",
            }
        if path == f"/api/v1/ui-audit/{run_id}/autofix":
            return {
                "run_id": run_id,
                "mode": "apply",
                "autofix_applied": False,
                "summary": {"finding_count": 1, "high_or_worse_count": 1},
                "guardrails": {
                    "max_files": 2,
                    "max_changed_lines": 80,
                    "requested_mode": "apply",
                    "effective_mode": "dry-run",
                },
                "suggested_actions": ["Fix high severity"],
            }
        raise AssertionError(path)

    register_ui_audit_tools(mcp, fake_api_call)
    run_payload = mcp.tools["sourceharbor.ui_audit.run"](artifact_root="/tmp")
    get_payload = mcp.tools["sourceharbor.ui_audit.read"](action="get", run_id=run_id)
    findings_payload = mcp.tools["sourceharbor.ui_audit.read"](
        action="list_findings", run_id=run_id
    )
    artifact_payload = mcp.tools["sourceharbor.ui_audit.read"](
        action="get_artifact", run_id=run_id, key="axe.json", include_base64=True
    )
    autofix_payload = mcp.tools["sourceharbor.ui_audit.read"](
        action="autofix", run_id=run_id, max_files=2
    )

    assert run_payload["run_id"] == run_id
    assert get_payload["run_id"] == run_id
    assert findings_payload["items"][0]["severity"] == "high"
    assert artifact_payload["exists"] is True
    assert autofix_payload["mode"] == "dry-run"
    assert "plan-only dry-run" in autofix_payload["guardrails"]["note"]
    assert autofix_payload["summary"]["high_or_worse_count"] == 1


def test_videos_process_normalizes_missing_overrides_to_empty_object() -> None:
    mcp = _FakeMCP()
    calls: list[dict[str, Any]] = []

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "kwargs": kwargs})
        return {"ok": True}

    register_job_tools(mcp, fake_api_call)
    response = mcp.tools["sourceharbor.videos.process"](
        video={
            "platform": "youtube",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }
    )

    assert response["ok"] is True
    assert calls[0]["kwargs"]["json_body"]["overrides"] == {}


def test_artifacts_get_rejects_path_traversal_and_invalid_job_id() -> None:
    mcp = _FakeMCP()
    register_artifact_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    invalid_id = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id="job-1", path="frames/a.png"
    )
    traversal = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id=UUID_1, path="../secret.txt"
    )
    absolute = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id=UUID_1, path="/etc/passwd"
    )
    scheme = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id=UUID_1, path="file:///tmp/x"
    )

    assert invalid_id["code"] == "INVALID_ARGUMENT"
    assert traversal["code"] == "INVALID_ARGUMENT"
    assert absolute["code"] == "INVALID_ARGUMENT"
    assert scheme["code"] == "INVALID_ARGUMENT"


def test_artifacts_get_preserves_non_404_errors_for_asset_reads() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "GET"
        assert path == "/api/v1/artifacts/assets"
        return {
            "code": "UPSTREAM_HTTP_ERROR",
            "message": "Unauthorized",
            "details": {"method": "GET", "path": path, "status_code": 401},
        }

    register_artifact_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id=UUID_1, path="frames/a.png"
    )

    assert payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert payload["details"]["status_code"] == 401
    assert "exists" not in payload


def test_artifacts_get_maps_404_asset_reads_to_exists_false() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "GET"
        assert path == "/api/v1/artifacts/assets"
        return {
            "code": "UPSTREAM_HTTP_ERROR",
            "message": "Not Found",
            "details": {"method": "GET", "path": path, "status_code": 404},
        }

    register_artifact_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.artifacts.get"](
        kind="asset", job_id=UUID_1, path="frames/missing.png"
    )

    assert payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert payload["exists"] is False
    assert payload["asset_url"] is None


def test_jobs_get_rejects_invalid_job_id() -> None:
    mcp = _FakeMCP()
    register_job_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.jobs.get"](job_id="not-a-uuid")
    assert payload["code"] == "INVALID_ARGUMENT"


def test_workflows_run_rejects_unknown_payload_keys() -> None:
    mcp = _FakeMCP()
    register_workflow_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.workflows.run"](
        workflow="daily_digest",
        payload={"timezone_name": "UTC", "evil": True},
    )
    assert payload["code"] == "INVALID_ARGUMENT"


def test_videos_process_rejects_unknown_overrides_keys() -> None:
    mcp = _FakeMCP()
    register_job_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.videos.process"](
        video={"platform": "youtube", "url": "https://example.com"},
        overrides={"llm": {}, "unexpected": {}},
    )
    assert payload["code"] == "INVALID_ARGUMENT"


def test_subscriptions_remove_rejects_invalid_id() -> None:
    mcp = _FakeMCP()
    register_subscription_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.subscriptions.manage"](action="remove", id="sub-1")
    assert payload["code"] == "INVALID_ARGUMENT"


def test_ui_audit_read_rejects_invalid_run_id_and_oversized_base64() -> None:
    mcp = _FakeMCP()
    run_id = UUID_2
    oversized_base64 = base64.b64encode(b"a" * (DEFAULT_MAX_BASE64_BYTES + 1)).decode("ascii")

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "GET"
        assert path == f"/api/v1/ui-audit/{run_id}/artifact"
        return {
            "key": "axe.json",
            "path": "/tmp/axe.json",
            "mime_type": "application/json",
            "size_bytes": DEFAULT_MAX_BASE64_BYTES + 1,
            "category": "playwright",
            "exists": True,
            "base64": oversized_base64,
        }

    register_ui_audit_tools(mcp, fake_api_call)
    invalid_id = mcp.tools["sourceharbor.ui_audit.read"](action="get", run_id="run-1")
    oversized = mcp.tools["sourceharbor.ui_audit.read"](
        action="get_artifact",
        run_id=run_id,
        key="axe.json",
        include_base64=True,
    )

    assert invalid_id["code"] == "INVALID_ARGUMENT"
    assert oversized["code"] == "PAYLOAD_TOO_LARGE"


def test_computer_use_rejects_unknown_safety_fields() -> None:
    mcp = _FakeMCP()
    register_computer_use_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click",
        screenshot_base64="ZmFrZQ==",
        safety={"confirm_before_execute": True, "bad_field": True},
    )
    assert payload["code"] == "INVALID_ARGUMENT"


def test_health_get_rejects_invalid_window_hours() -> None:
    mcp = _FakeMCP()
    register_health_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.health.get"](scope="providers", window_hours=0)
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "window_hours"


def test_ui_audit_read_autofix_rejects_invalid_limits() -> None:
    mcp = _FakeMCP()
    register_ui_audit_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.ui_audit.read"](
        action="autofix",
        run_id=UUID_1,
        max_files=0,
    )
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "max_files"


def test_jobs_list_videos_rejects_invalid_limit() -> None:
    mcp = _FakeMCP()
    register_job_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    payload = mcp.tools["sourceharbor.videos.list"](limit=0)
    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "limit"


def test_computer_use_rejects_invalid_screenshot_and_safety_values() -> None:
    mcp = _FakeMCP()
    register_computer_use_tools(mcp, lambda *_args, **_kwargs: {"ok": True})
    invalid_screenshot = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click",
        screenshot_base64="not-base64",
    )
    invalid_safety_max_actions = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click",
        screenshot_base64="ZmFrZQ==",
        safety={"max_actions": 0},
    )

    assert invalid_screenshot["code"] == "INVALID_ARGUMENT"
    assert invalid_screenshot["details"]["field"] == "screenshot_base64"
    assert invalid_safety_max_actions["code"] == "INVALID_ARGUMENT"
    assert invalid_safety_max_actions["details"]["field"] == "safety.max_actions"


def test_computer_use_rejects_invalid_blocked_actions_shape() -> None:
    mcp = _FakeMCP()
    register_computer_use_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    invalid_blocked_actions = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click",
        screenshot_base64="ZmFrZQ==",
        safety={"blocked_actions": ["click", "", 1]},  # type: ignore[list-item]
    )

    assert invalid_blocked_actions["code"] == "INVALID_ARGUMENT"
    assert invalid_blocked_actions["details"]["field"] == "safety.blocked_actions"


def test_workflow_payload_normalizer_rejects_invalid_boolean_and_parses_ranges() -> None:
    invalid_payload, field, error = _normalize_workflow_payload("poll_feeds", {"run_once": "yes"})
    assert invalid_payload is None
    assert field == "run_once"
    assert error is not None

    poll_feeds, field, error = _normalize_workflow_payload("poll_feeds", {"max_new_videos": 10})
    assert error is None and field is None
    assert poll_feeds == {"max_new_videos": 10}

    poll_feeds_with_run_once, field, error = _normalize_workflow_payload(
        "poll_feeds", {"run_once": True, "max_new_videos": 5}
    )
    assert error is None and field is None
    assert poll_feeds_with_run_once == {"run_once": True, "max_new_videos": 5}

    poll_feeds_with_interval, field, error = _normalize_workflow_payload(
        "poll_feeds", {"run_once": False, "interval_minutes": 15}
    )
    assert error is None and field is None
    assert poll_feeds_with_interval == {"run_once": False, "interval_minutes": 15}

    daily_digest, field, error = _normalize_workflow_payload(
        "daily_digest",
        {"timezone_offset_minutes": -60, "local_hour": 9},
    )
    assert error is None and field is None
    assert daily_digest == {"timezone_offset_minutes": -60, "local_hour": 9}

    notification_retry, field, error = _normalize_workflow_payload(
        "notification_retry",
        {"interval_minutes": 30, "retry_batch_limit": 20},
    )
    assert error is None and field is None
    assert notification_retry == {"interval_minutes": 30, "retry_batch_limit": 20}

    cleanup, field, error = _normalize_workflow_payload(
        "cleanup",
        {
            "interval_hours": 4,
            "older_than_hours": 72,
            "cache_older_than_hours": 24,
            "cache_max_size_mb": 128,
        },
    )
    assert error is None and field is None
    assert cleanup == {
        "interval_hours": 4,
        "older_than_hours": 72,
        "cache_older_than_hours": 24,
        "cache_max_size_mb": 128,
    }

    provider_canary, field, error = _normalize_workflow_payload(
        "provider_canary",
        {"interval_hours": 6, "timeout_seconds": 120},
    )
    assert error is None and field is None
    assert provider_canary == {"interval_hours": 6, "timeout_seconds": 120}


def test_workflows_run_reports_invalid_payload_value_with_original_input() -> None:
    mcp = _FakeMCP()
    register_workflow_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.workflows.run"](
        workflow="cleanup",
        payload={"cache_max_size_mb": 0},
    )

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "payload.cache_max_size_mb"
    assert str(payload["details"]["value"]).startswith("<redacted type=int")


def test_normalize_action_item_applies_defaults() -> None:
    assert _normalize_action_item("bad-shape", default_step=3) == {
        "step": 3,
        "action": "observe",
        "target": None,
        "input_text": None,
        "reasoning": None,
    }
    assert _normalize_action_item({"step": -1, "action": "   "}, default_step=2)["step"] == 2
    assert _normalize_action_item({"step": -1, "action": "   "}, default_step=2)["action"] == "   "


def test_computer_use_rejects_invalid_confirm_before_execute_type() -> None:
    mcp = _FakeMCP()
    register_computer_use_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click",
        screenshot_base64="ZmFrZQ==",
        safety={"confirm_before_execute": "true"},
    )

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "safety.confirm_before_execute"


def test_computer_use_rejects_blank_instruction() -> None:
    mcp = _FakeMCP()
    register_computer_use_tools(mcp, lambda *_args, **_kwargs: {"ok": True})

    payload = mcp.tools["sourceharbor.computer_use.run"](
        instruction="   ",
        screenshot_base64="ZmFrZQ==",
    )

    assert payload["code"] == "INVALID_ARGUMENT"
    assert payload["details"]["field"] == "instruction"


def test_computer_use_includes_all_safety_fields_and_passes_upstream_errors() -> None:
    mcp = _FakeMCP()
    calls: list[dict[str, Any]] = []

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append({"method": method, "path": path, "kwargs": kwargs})
        return {
            "code": "UPSTREAM_HTTP_ERROR",
            "message": "downstream",
            "details": {"status_code": 502},
        }

    register_computer_use_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.computer_use.run"](
        instruction="click submit",
        screenshot_base64="ZmFrZQ==",
        safety={
            "confirm_before_execute": True,
            "blocked_actions": ["submit"],
            "max_actions": 4,
        },
    )

    assert payload["code"] == "UPSTREAM_HTTP_ERROR"
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/api/v1/computer-use/run"
    assert calls[0]["kwargs"]["json_body"]["safety"] == {
        "confirm_before_execute": True,
        "blocked_actions": ["submit"],
        "max_actions": 4,
    }
