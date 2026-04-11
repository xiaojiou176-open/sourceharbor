from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    parse_uuid,
    to_optional_bool,
    to_optional_dict,
    to_optional_int,
    to_optional_str,
)


def _normalize_reader_document(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "id": to_optional_str(source.get("id")),
        "stable_key": to_optional_str(source.get("stable_key")),
        "slug": to_optional_str(source.get("slug")),
        "window_id": to_optional_str(source.get("window_id")),
        "topic_key": to_optional_str(source.get("topic_key")),
        "topic_label": to_optional_str(source.get("topic_label")),
        "title": to_optional_str(source.get("title")),
        "summary": to_optional_str(source.get("summary")),
        "markdown": to_optional_str(source.get("markdown")),
        "materialization_mode": to_optional_str(source.get("materialization_mode")),
        "version": to_optional_int(source.get("version")),
        "publish_status": to_optional_str(source.get("publish_status")),
        "published_with_gap": to_optional_bool(source.get("published_with_gap")),
        "source_item_count": to_optional_int(source.get("source_item_count")),
        "warning": to_optional_dict(source.get("warning")),
        "coverage_ledger": to_optional_dict(source.get("coverage_ledger")),
        "traceability_pack": to_optional_dict(source.get("traceability_pack")),
        "source_refs": source.get("source_refs")
        if isinstance(source.get("source_refs"), list)
        else [],
        "sections": source.get("sections") if isinstance(source.get("sections"), list) else [],
        "created_at": to_optional_str(source.get("created_at")),
        "updated_at": to_optional_str(source.get("updated_at")),
    }


def register_reader_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.reader.documents.list",
        description="List current published reader documents with optional window filter.",
    )
    def list_reader_documents(
        window_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized_limit, limit_error = parse_bounded_int(
            limit,
            field="limit",
            min_value=1,
            max_value=50,
        )
        if limit_error is not None:
            return invalid_argument(
                limit_error,
                method="GET",
                path="/api/v1/reader/documents",
                field="limit",
                value=limit,
            )
        response = api_call(
            "GET",
            "/api/v1/reader/documents",
            params={"window_id": window_id, "limit": normalized_limit},
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response
        items = response if isinstance(response, list) else []
        return {"items": [_normalize_reader_document(item) for item in items]}

    @mcp.tool(
        name="sourceharbor.reader.documents.get",
        description="Fetch one published reader document by UUID.",
    )
    def get_reader_document(document_id: str) -> dict[str, Any]:
        normalized_id = parse_uuid(document_id)
        if normalized_id is None:
            return invalid_argument(
                "document_id must be a valid UUID",
                method="GET",
                path="/api/v1/reader/documents/{document_id}",
                field="document_id",
                value=document_id,
            )
        response = api_call("GET", f"/api/v1/reader/documents/{normalized_id}")
        if isinstance(response, dict) and is_error_payload(response):
            return response
        return _normalize_reader_document(response)

    @mcp.tool(
        name="sourceharbor.reader.navigation.get",
        description="Get the current reader navigation brief for one window.",
    )
    def get_reader_navigation_brief(
        window_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized_limit, limit_error = parse_bounded_int(
            limit,
            field="limit",
            min_value=1,
            max_value=24,
        )
        if limit_error is not None:
            return invalid_argument(
                limit_error,
                method="GET",
                path="/api/v1/reader/navigation-brief",
                field="limit",
                value=limit,
            )
        response = api_call(
            "GET",
            "/api/v1/reader/navigation-brief",
            params={"window_id": window_id, "limit": normalized_limit},
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response
        payload = response if isinstance(response, dict) else {}
        raw_items = payload.get("items")
        return {
            "brief_kind": to_optional_str(payload.get("brief_kind")),
            "generated_at": to_optional_str(payload.get("generated_at")),
            "window_id": to_optional_str(payload.get("window_id")),
            "document_count": to_optional_int(payload.get("document_count")),
            "published_with_gap_count": to_optional_int(payload.get("published_with_gap_count")),
            "summary": to_optional_str(payload.get("summary")),
            "items": raw_items if isinstance(raw_items, list) else [],
        }
