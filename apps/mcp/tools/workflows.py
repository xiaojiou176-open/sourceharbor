from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bool,
    parse_bounded_int,
    parse_workflow_id,
    to_optional_dict,
    to_optional_str,
    validate_object_keys,
)

_WORKFLOW_PAYLOAD_ALLOWLIST: dict[str, set[str]] = {
    "poll_feeds": {"run_once", "subscription_id", "platform", "max_new_videos", "interval_minutes"},
    "consume_pending": {"run_once", "interval_minutes", "timezone_name", "window_id"},
    "daily_digest": {"run_once", "timezone_name", "timezone_offset_minutes", "local_hour"},
    "notification_retry": {"run_once", "interval_minutes", "retry_batch_limit"},
    "cleanup": {
        "run_once",
        "interval_hours",
        "workspace_dir",
        "older_than_hours",
        "cache_dir",
        "cache_older_than_hours",
        "cache_max_size_mb",
    },
    "provider_canary": {"run_once", "interval_hours", "timeout_seconds"},
}


def _normalize_workflow_payload(
    workflow: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    normalized = dict(payload)
    for bool_key in ("run_once",):
        if bool_key in normalized:
            value, error = parse_bool(normalized.get(bool_key), field=f"payload.{bool_key}")
            if error is not None:
                return None, bool_key, error
            normalized[bool_key] = value

    int_ranges: dict[str, tuple[int, int]] = {}
    if workflow == "poll_feeds":
        int_ranges["max_new_videos"] = (1, 500)
        int_ranges["interval_minutes"] = (1, 24 * 60)
    elif workflow == "consume_pending":
        int_ranges["interval_minutes"] = (60, 24 * 7)
    elif workflow == "daily_digest":
        int_ranges["timezone_offset_minutes"] = (-720, 840)
        int_ranges["local_hour"] = (0, 23)
    elif workflow == "notification_retry":
        int_ranges["interval_minutes"] = (1, 1440)
        int_ranges["retry_batch_limit"] = (1, 500)
    elif workflow == "cleanup":
        int_ranges["interval_hours"] = (1, 24 * 30)
        int_ranges["older_than_hours"] = (1, 24 * 365)
        int_ranges["cache_older_than_hours"] = (1, 24 * 365)
        int_ranges["cache_max_size_mb"] = (1, 1024 * 50)
    elif workflow == "provider_canary":
        int_ranges["interval_hours"] = (1, 24 * 30)
        int_ranges["timeout_seconds"] = (1, 1800)

    for key, (min_value, max_value) in int_ranges.items():
        if key not in normalized:
            continue
        parsed_value, error = parse_bounded_int(
            normalized.get(key),
            field=f"payload.{key}",
            min_value=min_value,
            max_value=max_value,
            required=True,
        )
        if error is not None or parsed_value is None:
            return None, key, error or f"payload.{key} is invalid"
        normalized[key] = parsed_value
    return normalized, None, None


def register_workflow_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.workflows.run",
        description="Start operational Temporal workflows via API gateway.",
    )
    def run_workflow(
        workflow: str,
        run_once: bool = True,
        wait_for_result: bool = False,
        workflow_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_workflow = str(workflow or "").strip()
        allowed_payload_keys = _WORKFLOW_PAYLOAD_ALLOWLIST.get(normalized_workflow)
        if allowed_payload_keys is None:
            return invalid_argument(
                "workflow must be one of: poll_feeds, consume_pending, daily_digest, notification_retry, cleanup, provider_canary",
                method="POST",
                path="/api/v1/workflows/run",
                field="workflow",
                value=workflow,
            )
        normalized_workflow_id: str | None = None
        if workflow_id is not None:
            normalized_workflow_id = parse_workflow_id(workflow_id)
            if normalized_workflow_id is None:
                return invalid_argument(
                    "workflow_id must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$",
                    method="POST",
                    path="/api/v1/workflows/run",
                    field="workflow_id",
                    value=workflow_id,
                )
        normalized_payload, payload_error = validate_object_keys(
            payload or {},
            allowed_keys=allowed_payload_keys,
        )
        if payload_error is not None or normalized_payload is None:
            return invalid_argument(
                f"payload {payload_error or 'is invalid'}",
                method="POST",
                path="/api/v1/workflows/run",
                field="payload",
            )
        normalized_run_once, run_once_error = parse_bool(run_once, field="run_once", required=True)
        if run_once_error is not None or normalized_run_once is None:
            return invalid_argument(
                run_once_error or "run_once is invalid",
                method="POST",
                path="/api/v1/workflows/run",
                field="run_once",
                value=run_once,
            )
        normalized_wait_for_result, wait_error = parse_bool(
            wait_for_result, field="wait_for_result", required=True
        )
        if wait_error is not None or normalized_wait_for_result is None:
            return invalid_argument(
                wait_error or "wait_for_result is invalid",
                method="POST",
                path="/api/v1/workflows/run",
                field="wait_for_result",
                value=wait_for_result,
            )
        normalized_payload, invalid_payload_field, invalid_payload_error = (
            _normalize_workflow_payload(
                normalized_workflow,
                normalized_payload,
            )
        )
        if (
            invalid_payload_error is not None
            or invalid_payload_field is not None
            or normalized_payload is None
        ):
            return invalid_argument(
                invalid_payload_error or "payload is invalid",
                method="POST",
                path="/api/v1/workflows/run",
                field=f"payload.{invalid_payload_field}" if invalid_payload_field else "payload",
                value=payload.get(invalid_payload_field)
                if isinstance(payload, dict) and invalid_payload_field
                else None,
            )
        response = api_call(
            "POST",
            "/api/v1/workflows/run",
            json_body={
                "workflow": normalized_workflow,
                "run_once": normalized_run_once,
                "wait_for_result": normalized_wait_for_result,
                "workflow_id": normalized_workflow_id,
                "payload": normalized_payload,
            },
        )
        if is_error_payload(response):
            return response
        return {
            "workflow": to_optional_str(response.get("workflow")),
            "workflow_name": to_optional_str(response.get("workflow_name")),
            "workflow_id": to_optional_str(response.get("workflow_id")),
            "run_id": to_optional_str(response.get("run_id")),
            "status": to_optional_str(response.get("status")),
            "started_at": to_optional_str(response.get("started_at")),
            "result": to_optional_dict(response.get("result")),
        }
