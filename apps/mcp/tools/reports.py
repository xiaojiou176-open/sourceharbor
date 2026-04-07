from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import ApiCall, is_error_payload, to_optional_str


def register_report_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(name="sourceharbor.reports.daily_send", description="Send daily report notification.")
    def send_daily_report(
        date: str | None = None,
        to_email: str | None = None,
        subject: str | None = None,
        body: str | None = None,
    ) -> dict[str, Any]:
        response = api_call(
            "POST",
            "/api/v1/reports/daily/send",
            json_body={
                "date": date,
                "to_email": to_email,
                "subject": subject,
                "body": body,
            },
        )

        if is_error_payload(response):
            return response

        return {
            "sent": bool(response.get("sent", False)),
            "status": to_optional_str(response.get("status")),
            "delivery_id": to_optional_str(response.get("delivery_id")),
            "date": to_optional_str(response.get("date")) or date,
            "recipient_email": to_optional_str(response.get("recipient_email")),
            "subject": to_optional_str(response.get("subject")),
            "error_message": to_optional_str(response.get("error_message")),
            "sent_at": to_optional_str(response.get("sent_at")),
            "created_at": to_optional_str(response.get("created_at")),
        }
