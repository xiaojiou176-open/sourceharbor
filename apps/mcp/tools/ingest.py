from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    parse_uuid,
    to_int,
    to_optional_str,
    url_path_segment,
)

ApiCall = Callable[..., dict[str, Any]]


def _normalize_ingest_candidate(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "video_id": to_optional_str(source.get("video_id")),
        "platform": to_optional_str(source.get("platform")),
        "video_uid": to_optional_str(source.get("video_uid")),
        "source_url": to_optional_str(source.get("source_url")),
        "title": to_optional_str(source.get("title")),
        "published_at": to_optional_str(source.get("published_at")),
        "job_id": to_optional_str(source.get("job_id")),
    }


def _normalize_ingest_run_item(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "id": to_optional_str(source.get("id")),
        "subscription_id": to_optional_str(source.get("subscription_id")),
        "video_id": to_optional_str(source.get("video_id")),
        "job_id": to_optional_str(source.get("job_id")),
        "ingest_event_id": to_optional_str(source.get("ingest_event_id")),
        "platform": to_optional_str(source.get("platform")),
        "video_uid": to_optional_str(source.get("video_uid")),
        "source_url": to_optional_str(source.get("source_url")),
        "title": to_optional_str(source.get("title")),
        "published_at": to_optional_str(source.get("published_at")),
        "entry_hash": to_optional_str(source.get("entry_hash")),
        "pipeline_mode": to_optional_str(source.get("pipeline_mode")),
        "content_type": to_optional_str(source.get("content_type")),
        "item_status": to_optional_str(source.get("item_status")),
        "created_at": to_optional_str(source.get("created_at")),
        "updated_at": to_optional_str(source.get("updated_at")),
    }


def _normalize_ingest_run_summary(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "id": to_optional_str(source.get("id")),
        "subscription_id": to_optional_str(source.get("subscription_id")),
        "workflow_id": to_optional_str(source.get("workflow_id")),
        "platform": to_optional_str(source.get("platform")),
        "max_new_videos": to_int(source.get("max_new_videos"), default=0),
        "status": to_optional_str(source.get("status")),
        "jobs_created": to_int(source.get("jobs_created"), default=0),
        "candidates_count": to_int(source.get("candidates_count"), default=0),
        "feeds_polled": to_int(source.get("feeds_polled"), default=0),
        "entries_fetched": to_int(source.get("entries_fetched"), default=0),
        "entries_normalized": to_int(source.get("entries_normalized"), default=0),
        "ingest_events_created": to_int(source.get("ingest_events_created"), default=0),
        "ingest_event_duplicates": to_int(source.get("ingest_event_duplicates"), default=0),
        "job_duplicates": to_int(source.get("job_duplicates"), default=0),
        "error_message": to_optional_str(source.get("error_message")),
        "created_at": to_optional_str(source.get("created_at")),
        "updated_at": to_optional_str(source.get("updated_at")),
        "completed_at": to_optional_str(source.get("completed_at")),
    }


def _normalize_ingest_run(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    payload = _normalize_ingest_run_summary(source)
    payload["requested_by"] = to_optional_str(source.get("requested_by"))
    payload["requested_trace_id"] = to_optional_str(source.get("requested_trace_id"))
    payload["filters_json"] = (
        source.get("filters_json") if isinstance(source.get("filters_json"), dict) else None
    )
    items = source.get("items")
    payload["items"] = [
        _normalize_ingest_run_item(candidate)
        for candidate in (items if isinstance(items, list) else [])
    ]
    return payload


def register_ingest_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(name="sourceharbor.ingest.poll", description="Trigger one ingest poll cycle.")
    def ingest_poll(
        subscription_id: str | None = None,
        platform: str | None = None,
        max_new_videos: int | None = None,
    ) -> dict[str, Any]:
        normalized_subscription_id: str | None = None
        if subscription_id is not None:
            normalized_subscription_id = parse_uuid(subscription_id)
            if normalized_subscription_id is None:
                return invalid_argument(
                    "subscription_id must be a valid UUID",
                    method="POST",
                    path="/api/v1/ingest/poll",
                    field="subscription_id",
                    value=subscription_id,
                )
        normalized_max_new_videos, max_new_videos_error = parse_bounded_int(
            max_new_videos,
            field="max_new_videos",
            min_value=1,
            max_value=500,
        )
        if max_new_videos_error is not None:
            return invalid_argument(
                max_new_videos_error,
                method="POST",
                path="/api/v1/ingest/poll",
                field="max_new_videos",
                value=max_new_videos,
            )
        response = api_call(
            "POST",
            "/api/v1/ingest/poll",
            json_body={
                "subscription_id": normalized_subscription_id,
                "platform": platform,
                "max_new_videos": normalized_max_new_videos,
            },
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response
        return {
            "run_id": to_optional_str(response.get("run_id")),
            "workflow_id": to_optional_str(response.get("workflow_id")),
            "status": to_optional_str(response.get("status")),
            "enqueued": to_int(response.get("enqueued"), default=0),
            "candidates": [
                _normalize_ingest_candidate(item)
                for item in (
                    response.get("candidates")
                    if isinstance(response.get("candidates"), list)
                    else []
                )
            ],
        }

    @mcp.tool(
        name="sourceharbor.ingest.runs.list",
        description="List recent ingest runs.",
    )
    def list_ingest_runs(
        status: str | None = None,
        platform: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
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
                path="/api/v1/ingest/runs",
                field="limit",
                value=limit,
            )
        response = api_call(
            "GET",
            "/api/v1/ingest/runs",
            params={
                "status": status,
                "platform": platform,
                "limit": normalized_limit,
            },
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response
        items = response if isinstance(response, list) else []
        return {
            "items": [_normalize_ingest_run_summary(item) for item in items],
        }

    @mcp.tool(
        name="sourceharbor.ingest.runs.get",
        description="Get one ingest run by id.",
    )
    def get_ingest_run(run_id: str) -> dict[str, Any]:
        normalized_run_id = parse_uuid(run_id)
        if normalized_run_id is None:
            return invalid_argument(
                "run_id must be a valid UUID",
                method="GET",
                path="/api/v1/ingest/runs/{run_id}",
                field="run_id",
                value=run_id,
            )
        response = api_call(
            "GET",
            f"/api/v1/ingest/runs/{url_path_segment(normalized_run_id)}",
        )
        if isinstance(response, dict) and is_error_payload(response):
            return response
        return _normalize_ingest_run(response)
