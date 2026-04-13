from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import invalid_argument, parse_uuid, url_path_segment

ApiCall = Callable[..., dict[str, Any]]


def register_subscription_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.subscriptions.manage",
        description=(
            "Manage subscriptions and inspect the shared template catalog for "
            "strong-supported YouTube/Bilibili lanes plus generalized RSSHub and RSS intake. "
            "action=list|list_templates|upsert|manual_intake|remove|batch_update_category."
        ),
    )
    def manage_subscriptions(
        action: str,
        id: str | None = None,
        platform: str | None = None,
        category: str | None = None,
        ids: list[str] | None = None,
        enabled_only: bool | None = None,
        source_type: str | None = None,
        source_value: str | None = None,
        adapter_type: str | None = None,
        source_url: str | None = None,
        rsshub_route: str | None = None,
        tags: list[str] | None = None,
        priority: int | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        normalized_action = str(action or "").strip().lower()
        if normalized_action == "list":
            return api_call(
                "GET",
                "/api/v1/subscriptions",
                params={
                    "platform": platform,
                    "category": category,
                    "enabled_only": enabled_only,
                },
            )
        if normalized_action == "list_templates":
            return api_call("GET", "/api/v1/subscriptions/templates")
        if normalized_action == "upsert":
            return api_call(
                "POST",
                "/api/v1/subscriptions",
                json_body={
                    "platform": platform,
                    "source_type": source_type,
                    "source_value": source_value,
                    "adapter_type": adapter_type,
                    "source_url": source_url,
                    "rsshub_route": rsshub_route,
                    "category": category,
                    "tags": tags or [],
                    "priority": priority,
                    "enabled": enabled,
                },
            )
        if normalized_action == "manual_intake":
            raw_input = str(source_value or "").strip()
            if not raw_input:
                return invalid_argument(
                    "source_value is required when action=manual_intake",
                    method="POST",
                    path="/api/v1/subscriptions/manual-intake",
                    field="source_value",
                    value=source_value,
                )
            return api_call(
                "POST",
                "/api/v1/subscriptions/manual-intake",
                json_body={
                    "raw_input": raw_input,
                    "category": category or "misc",
                    "tags": tags or [],
                    "priority": priority if priority is not None else 50,
                    "enabled": enabled,
                },
            )
        if normalized_action == "batch_update_category":
            normalized_ids: list[str] = []
            for item in ids or []:
                normalized = parse_uuid(item)
                if normalized is None:
                    return invalid_argument(
                        "ids must contain only UUID values",
                        method="POST",
                        path="/api/v1/subscriptions/batch-update-category",
                        field="ids",
                        value=item,
                    )
                normalized_ids.append(normalized)
            return api_call(
                "POST",
                "/api/v1/subscriptions/batch-update-category",
                json_body={
                    "ids": normalized_ids,
                    "category": category,
                },
            )
        if normalized_action == "remove":
            if not id:
                return invalid_argument(
                    "id is required when action=remove",
                    method="DELETE",
                    path="/api/v1/subscriptions/{id}",
                    field="id",
                )
            normalized_id = parse_uuid(id)
            if normalized_id is None:
                return invalid_argument(
                    "id must be a valid UUID when action=remove",
                    method="DELETE",
                    path="/api/v1/subscriptions/{id}",
                    field="id",
                    value=id,
                )
            return api_call("DELETE", f"/api/v1/subscriptions/{url_path_segment(normalized_id)}")
        return invalid_argument(
            "action must be one of: list, list_templates, upsert, manual_intake, remove, batch_update_category",
            method="POST",
            path="sourceharbor.subscriptions.manage",
            field="action",
            value=action,
        )
