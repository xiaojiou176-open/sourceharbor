from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    sanitize_error_payload,
    to_optional_bool,
    to_optional_int,
    to_optional_str,
)


def _normalize_send_test_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return sanitize_error_payload(payload)
    return {
        "delivery_id": to_optional_str(payload.get("delivery_id")),
        "status": to_optional_str(payload.get("status")),
        "provider_message_id": to_optional_str(payload.get("provider_message_id")),
        "error_message": to_optional_str(payload.get("error_message")),
        "recipient_email": to_optional_str(payload.get("recipient_email")),
        "subject": to_optional_str(payload.get("subject")),
        "sent_at": to_optional_str(payload.get("sent_at")),
        "created_at": to_optional_str(payload.get("created_at")),
    }


def _normalize_set_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return sanitize_error_payload(payload)
    return {
        "enabled": to_optional_bool(payload.get("enabled")),
        "to_email": to_optional_str(payload.get("to_email")),
        "daily_digest_enabled": to_optional_bool(payload.get("daily_digest_enabled")),
        "daily_digest_hour_utc": to_optional_int(payload.get("daily_digest_hour_utc")),
        "failure_alert_enabled": to_optional_bool(payload.get("failure_alert_enabled")),
        "category_rules": payload.get("category_rules")
        if isinstance(payload.get("category_rules"), dict)
        else {},
        "created_at": to_optional_str(payload.get("created_at")),
        "updated_at": to_optional_str(payload.get("updated_at")),
    }


def register_notification_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.notifications.manage",
        description="Manage notifications. action=get_config|set_config|send_test|daily_send|category_send.",
    )
    def manage_notifications(
        action: str,
        date: str | None = None,
        to_email: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        category: str | None = None,
        priority: int | None = None,
        dispatch_key: str | None = None,
        enabled: bool = True,
        daily_digest_enabled: bool = False,
        daily_digest_hour_utc: int | None = None,
        failure_alert_enabled: bool = True,
        category_rules: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_daily_digest_hour_utc, digest_hour_error = parse_bounded_int(
            daily_digest_hour_utc,
            field="daily_digest_hour_utc",
            min_value=0,
            max_value=23,
            required=False,
        )
        if digest_hour_error is not None:
            return invalid_argument(
                digest_hour_error,
                method="POST",
                path="sourceharbor.notifications.manage",
                field="daily_digest_hour_utc",
                value=daily_digest_hour_utc,
            )

        normalized_priority, priority_error = parse_bounded_int(
            priority,
            field="priority",
            min_value=0,
            max_value=100,
            required=False,
        )
        if priority_error is not None:
            return invalid_argument(
                priority_error,
                method="POST",
                path="sourceharbor.notifications.manage",
                field="priority",
                value=priority,
            )

        normalized_action = str(action or "").strip().lower()
        if normalized_action == "get_config":
            response = api_call("GET", "/api/v1/notifications/config")
            return _normalize_set_config_payload(response)

        if normalized_action == "set_config":
            response = api_call(
                "PUT",
                "/api/v1/notifications/config",
                json_body={
                    "enabled": enabled,
                    "to_email": to_email,
                    "daily_digest_enabled": daily_digest_enabled,
                    "daily_digest_hour_utc": normalized_daily_digest_hour_utc,
                    "failure_alert_enabled": failure_alert_enabled,
                    "category_rules": category_rules,
                },
            )
            return _normalize_set_config_payload(response)

        if normalized_action == "send_test":
            response = api_call(
                "POST",
                "/api/v1/notifications/test",
                json_body={
                    "to_email": to_email,
                    "subject": subject,
                    "body": body,
                },
            )
            return _normalize_send_test_payload(response)

        if normalized_action == "daily_send":
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
                return sanitize_error_payload(response)
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

        if normalized_action == "category_send":
            response = api_call(
                "POST",
                "/api/v1/notifications/category/send",
                json_body={
                    "category": category,
                    "body": body,
                    "to_email": to_email,
                    "subject": subject,
                    "priority": normalized_priority,
                    "dispatch_key": dispatch_key,
                },
            )
            return _normalize_send_test_payload(response)

        return invalid_argument(
            "action must be one of: get_config, set_config, send_test, daily_send, category_send",
            method="POST",
            path="sourceharbor.notifications.manage",
            field="action",
            value=action,
        )
