from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    parse_uuid,
    to_optional_dict,
    to_optional_str,
)


def _normalize_knowledge_card(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "id": to_optional_str(source.get("id")),
        "job_id": to_optional_str(source.get("job_id")),
        "video_id": to_optional_str(source.get("video_id")),
        "card_type": to_optional_str(source.get("card_type")),
        "source_section": to_optional_str(source.get("source_section")),
        "title": to_optional_str(source.get("title")),
        "body": to_optional_str(source.get("body")),
        "order_index": source.get("order_index"),
        "metadata_json": to_optional_dict(source.get("metadata_json")) or {},
        "created_at": to_optional_str(source.get("created_at")),
        "updated_at": to_optional_str(source.get("updated_at")),
    }


def register_knowledge_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.knowledge.cards.list",
        description="List structured knowledge cards derived from digest outputs.",
    )
    def list_knowledge_cards(
        job_id: str | None = None,
        video_id: str | None = None,
        card_type: str | None = None,
        topic_key: str | None = None,
        claim_kind: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized_job_id: str | None = None
        normalized_video_id: str | None = None
        if job_id is not None:
            normalized_job_id = parse_uuid(job_id)
            if normalized_job_id is None:
                return invalid_argument(
                    "job_id must be a valid UUID",
                    method="GET",
                    path="/api/v1/knowledge/cards",
                    field="job_id",
                    value=job_id,
                )
        if video_id is not None:
            normalized_video_id = parse_uuid(video_id)
            if normalized_video_id is None:
                return invalid_argument(
                    "video_id must be a valid UUID",
                    method="GET",
                    path="/api/v1/knowledge/cards",
                    field="video_id",
                    value=video_id,
                )
        normalized_limit, limit_error = parse_bounded_int(
            limit,
            field="limit",
            min_value=1,
            max_value=200,
        )
        if limit_error is not None:
            return invalid_argument(
                limit_error,
                method="GET",
                path="/api/v1/knowledge/cards",
                field="limit",
                value=limit,
            )
        response = api_call(
            "GET",
            "/api/v1/knowledge/cards",
            params={
                "job_id": normalized_job_id,
                "video_id": normalized_video_id,
                "card_type": card_type,
                "topic_key": topic_key,
                "claim_kind": claim_kind,
                "limit": normalized_limit,
            },
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response
        items = response if isinstance(response, list) else []
        return {"items": [_normalize_knowledge_card(item) for item in items]}
