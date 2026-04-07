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
    to_optional_str,
)

_ALLOWED_CATEGORIES = {"tech", "creator", "macro", "ops", "misc"}
_ALLOWED_FEEDBACK = {"saved", "useful", "noisy", "dismissed", "archived"}
_ALLOWED_SORT = {"recent", "curated"}


def _normalize_feed_item(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "feed_id": to_optional_str(source.get("feed_id")),
        "job_id": to_optional_str(source.get("job_id")),
        "video_url": to_optional_str(source.get("video_url")),
        "title": to_optional_str(source.get("title")),
        "source": to_optional_str(source.get("source")),
        "source_name": to_optional_str(source.get("source_name")),
        "category": to_optional_str(source.get("category")),
        "published_at": to_optional_str(source.get("published_at")),
        "summary_md": to_optional_str(source.get("summary_md")),
        "artifact_type": to_optional_str(source.get("artifact_type")),
        "content_type": to_optional_str(source.get("content_type")),
        "saved": to_optional_bool(source.get("saved")),
        "feedback_label": to_optional_str(source.get("feedback_label")),
    }


def register_feed_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.feed.digests.list",
        description="List digest feed entries with optional feedback and sort filters.",
    )
    def list_digest_feed(
        source: str | None = None,
        category: str | None = None,
        feedback: str | None = None,
        sort: str | None = None,
        subscription_id: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        normalized_category: str | None = None
        if category is not None:
            normalized_category = str(category).strip().lower()
            if normalized_category not in _ALLOWED_CATEGORIES:
                return invalid_argument(
                    "category must be one of: tech, creator, macro, ops, misc",
                    method="GET",
                    path="/api/v1/feed/digests",
                    field="category",
                    value=category,
                )

        normalized_feedback: str | None = None
        if feedback is not None:
            normalized_feedback = str(feedback).strip().lower()
            if normalized_feedback not in _ALLOWED_FEEDBACK:
                return invalid_argument(
                    "feedback must be one of: saved, useful, noisy, dismissed, archived",
                    method="GET",
                    path="/api/v1/feed/digests",
                    field="feedback",
                    value=feedback,
                )

        normalized_sort: str | None = None
        if sort is not None:
            normalized_sort = str(sort).strip().lower()
            if normalized_sort not in _ALLOWED_SORT:
                return invalid_argument(
                    "sort must be one of: recent, curated",
                    method="GET",
                    path="/api/v1/feed/digests",
                    field="sort",
                    value=sort,
                )

        normalized_subscription_id: str | None = None
        if subscription_id is not None:
            normalized_subscription_id = parse_uuid(subscription_id)
            if normalized_subscription_id is None:
                return invalid_argument(
                    "subscription_id must be a valid UUID",
                    method="GET",
                    path="/api/v1/feed/digests",
                    field="subscription_id",
                    value=subscription_id,
                )

        normalized_limit, limit_error = parse_bounded_int(
            limit,
            field="limit",
            min_value=1,
            max_value=100,
        )
        if limit_error is not None:
            return invalid_argument(
                limit_error,
                method="GET",
                path="/api/v1/feed/digests",
                field="limit",
                value=limit,
            )

        response = api_call(
            "GET",
            "/api/v1/feed/digests",
            params={
                "source": source,
                "category": normalized_category,
                "feedback": normalized_feedback,
                "sort": normalized_sort,
                "sub": normalized_subscription_id,
                "limit": normalized_limit,
                "cursor": cursor,
                "since": since,
            },
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response

        payload = response if isinstance(response, dict) else {}
        raw_items = payload.get("items")
        items = raw_items if isinstance(raw_items, list) else []
        return {
            "items": [_normalize_feed_item(item) for item in items],
            "has_more": bool(payload.get("has_more")),
            "next_cursor": to_optional_str(payload.get("next_cursor")),
        }
