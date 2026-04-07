from __future__ import annotations

import math
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    sanitize_error_payload,
    to_int,
    to_optional_dict,
    to_optional_str,
)

_ALLOWED_RETRIEVAL_MODES = {"keyword", "semantic", "hybrid"}
_ALLOWED_RETRIEVAL_PLATFORMS = {"youtube", "bilibili", "rss"}
_ALLOWED_RETRIEVAL_SOURCES = {
    "digest",
    "transcript",
    "outline",
    "knowledge_cards",
    "comments",
    "meta",
}


def _normalize_retrieval_item(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    platform = to_optional_str(source.get("platform"))
    normalized_platform = platform if platform in _ALLOWED_RETRIEVAL_PLATFORMS else None
    retrieval_source = to_optional_str(source.get("source"))
    normalized_source = retrieval_source if retrieval_source in _ALLOWED_RETRIEVAL_SOURCES else None
    score_value = source.get("score")
    score = (
        float(score_value)
        if isinstance(score_value, (int, float)) and not isinstance(score_value, bool)
        else 0.0
    )
    if not math.isfinite(score):
        score = 0.0

    return {
        "job_id": to_optional_str(source.get("job_id")),
        "video_id": to_optional_str(source.get("video_id")),
        "platform": normalized_platform,
        "video_uid": to_optional_str(source.get("video_uid")),
        "source_url": to_optional_str(source.get("source_url")),
        "title": to_optional_str(source.get("title")),
        "kind": to_optional_str(source.get("kind")),
        "mode": to_optional_str(source.get("mode")),
        "source": normalized_source,
        "snippet": to_optional_str(source.get("snippet")),
        "score": score,
    }


def register_retrieval_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.retrieval.search",
        description="Search retrieval index over generated artifacts (digest/transcript/outline/comments).",
    )
    def retrieval_search(
        query: str,
        top_k: int = 10,
        mode: Literal["keyword", "semantic", "hybrid"] = "keyword",
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_query = str(query or "").strip()
        if not normalized_query:
            return invalid_argument(
                "query must be a non-empty string",
                method="POST",
                path="/api/v1/retrieval/search",
                field="query",
                value=query,
            )
        normalized_top_k, top_k_error = parse_bounded_int(
            top_k,
            field="top_k",
            min_value=1,
            max_value=50,
            required=True,
        )
        if top_k_error is not None or normalized_top_k is None:
            return invalid_argument(
                top_k_error or "top_k is invalid",
                method="POST",
                path="/api/v1/retrieval/search",
                field="top_k",
                value=top_k,
            )
        normalized_mode = str(mode).strip().lower()
        if normalized_mode not in _ALLOWED_RETRIEVAL_MODES:
            return invalid_argument(
                "mode must be one of: keyword, semantic, hybrid",
                method="POST",
                path="/api/v1/retrieval/search",
                field="mode",
                value=mode,
            )
        response = api_call(
            "POST",
            "/api/v1/retrieval/search",
            json_body={
                "query": normalized_query,
                "top_k": normalized_top_k,
                "mode": normalized_mode,
                "filters": filters or {},
            },
        )
        if is_error_payload(response):
            return sanitize_error_payload(response)

        items = response.get("items")
        response_top_k = to_int(response.get("top_k"), default=normalized_top_k)
        normalized_response_top_k = (
            response_top_k if 1 <= response_top_k <= 50 else normalized_top_k
        )
        response_query = to_optional_str(response.get("query"))
        normalized_response_query = (
            response_query.strip() if isinstance(response_query, str) else normalized_query
        ) or normalized_query
        return {
            "query": normalized_response_query,
            "top_k": normalized_response_top_k,
            "filters": to_optional_dict(response.get("filters")) or (filters or {}),
            "items": [
                _normalize_retrieval_item(item)
                for item in (items if isinstance(items, list) else [])
            ],
        }
