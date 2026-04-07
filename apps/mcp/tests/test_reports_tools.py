from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.mcp.tools.reports import register_report_tools


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Callable[..., dict[str, Any]]] = {}

    def tool(self, *, name: str, description: str):
        del description

        def _decorator(func: Callable[..., dict[str, Any]]):
            self.tools[name] = func
            return func

        return _decorator


def test_reports_daily_send_normalizes_success_payload_and_date_fallback() -> None:
    mcp = _FakeMCP()

    def fake_api_call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/api/v1/reports/daily/send"
        assert kwargs["json_body"]["to_email"] == "demo@example.com"
        return {
            "sent": 1,
            "status": "sent",
            "delivery_id": "delivery-1",
            "recipient_email": "demo@example.com",
            "subject": "Daily",
            "error_message": None,
            "sent_at": "2026-02-25T10:00:00Z",
            "created_at": "2026-02-25T10:00:00Z",
        }

    register_report_tools(mcp, fake_api_call)
    payload = mcp.tools["sourceharbor.reports.daily_send"](
        date="2026-02-25",
        to_email="demo@example.com",
        subject="Daily",
        body="digest",
    )

    assert payload["sent"] is True
    assert payload["date"] == "2026-02-25"
    assert payload["delivery_id"] == "delivery-1"
    assert payload["recipient_email"] == "demo@example.com"


def test_reports_daily_send_passes_error_payload_through() -> None:
    mcp = _FakeMCP()
    error_payload = {
        "code": "UPSTREAM_TIMEOUT",
        "message": "timeout",
        "details": {"path": "/api/v1/reports/daily/send"},
    }

    register_report_tools(mcp, lambda *_args, **_kwargs: error_payload)
    payload = mcp.tools["sourceharbor.reports.daily_send"](date="2026-02-25")

    assert payload == error_payload
