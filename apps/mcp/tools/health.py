from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    to_int,
    to_optional_str,
)


def _normalize_provider_item(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "provider": to_optional_str(source.get("provider")) or "",
        "ok": to_int(source.get("ok"), default=0),
        "warn": to_int(source.get("warn"), default=0),
        "fail": to_int(source.get("fail"), default=0),
        "last_status": to_optional_str(source.get("last_status")),
        "last_checked_at": to_optional_str(source.get("last_checked_at")),
        "last_error_kind": to_optional_str(source.get("last_error_kind")),
        "last_message": to_optional_str(source.get("last_message")),
    }


def register_health_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.health.get",
        description="Get system/provider health in one call. scope=system|providers|all.",
    )
    def get_health(
        scope: str = "all",
        window_hours: int = 24,
    ) -> dict[str, Any]:
        normalized_scope = str(scope or "all").strip().lower()
        if normalized_scope not in {"system", "providers", "all"}:
            normalized_scope = "all"
        normalized_window_hours, window_hours_error = parse_bounded_int(
            window_hours,
            field="window_hours",
            min_value=1,
            max_value=24 * 30,
            required=True,
        )
        if window_hours_error is not None or normalized_window_hours is None:
            return invalid_argument(
                window_hours_error or "window_hours is invalid",
                method="GET",
                path="sourceharbor.health.get",
                field="window_hours",
                value=window_hours,
            )

        payload: dict[str, Any] = {"scope": normalized_scope}
        if normalized_scope in {"system", "all"}:
            system_response = api_call("GET", "/healthz")
            if is_error_payload(system_response):
                return system_response
            payload["system"] = {
                "status": to_optional_str(system_response.get("status")) or "unknown"
            }

        if normalized_scope in {"providers", "all"}:
            providers_response = api_call(
                "GET",
                "/api/v1/health/providers",
                params={"window_hours": normalized_window_hours},
            )
            if is_error_payload(providers_response):
                return providers_response
            items = providers_response.get("providers")
            providers = items if isinstance(items, list) else []
            payload["providers"] = {
                "window_hours": to_int(providers_response.get("window_hours"), default=24),
                "items": [_normalize_provider_item(item) for item in providers],
            }

        return payload
