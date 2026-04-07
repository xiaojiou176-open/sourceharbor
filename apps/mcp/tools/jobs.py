from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bounded_int,
    parse_uuid,
    to_int,
    to_optional_bool,
    to_optional_dict,
    to_optional_str,
    url_path_segment,
    validate_object_keys,
)


def _normalize_step(item: Any) -> dict[str, Any]:
    step = item if isinstance(item, dict) else {}
    error_value = step.get("error")
    return {
        "name": to_optional_str(step.get("name")) or "",
        "status": to_optional_str(step.get("status")) or "unknown",
        "attempt": to_int(step.get("attempt"), default=0),
        "started_at": to_optional_str(step.get("started_at")),
        "finished_at": to_optional_str(step.get("finished_at")),
        "error": None if error_value is None else str(error_value),
    }


def _normalize_step_detail(item: Any) -> dict[str, Any]:
    step = _normalize_step(item)
    source = item if isinstance(item, dict) else {}
    step["error_kind"] = to_optional_str(source.get("error_kind"))
    step["retry_meta"] = to_optional_dict(source.get("retry_meta"))
    step["result"] = to_optional_dict(source.get("result"))
    step["thought_metadata"] = to_optional_dict(source.get("thought_metadata"))
    step["cache_key"] = to_optional_str(source.get("cache_key"))
    return step


def _normalize_degradation(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "step": to_optional_str(source.get("step")),
        "status": to_optional_str(source.get("status")),
        "reason": to_optional_str(source.get("reason")),
        "error": source.get("error"),
        "error_kind": to_optional_str(source.get("error_kind")),
        "retry_meta": to_optional_dict(source.get("retry_meta")),
        "cache_meta": to_optional_dict(source.get("cache_meta")),
    }


def _normalize_artifacts_index(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            normalized[key] = item
    return normalized


def _normalize_notification_retry(value: Any) -> dict[str, Any] | None:
    source = value if isinstance(value, dict) else None
    if source is None:
        return None
    return {
        "delivery_id": to_optional_str(source.get("delivery_id")),
        "status": to_optional_str(source.get("status")),
        "attempt_count": to_int(source.get("attempt_count"), default=0),
        "next_retry_at": to_optional_str(source.get("next_retry_at")),
        "last_error_kind": to_optional_str(source.get("last_error_kind")),
    }


def _normalize_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return payload

    job = payload.get("job")
    source = job if isinstance(job, dict) else payload
    step_summary = source.get("step_summary")
    step_summary_items = step_summary if isinstance(step_summary, list) else []
    steps = source.get("steps")
    step_items = steps if isinstance(steps, list) else []
    degradations = source.get("degradations")
    degradation_items = degradations if isinstance(degradations, list) else []

    return {
        "id": to_optional_str(source.get("id")),
        "video_id": to_optional_str(source.get("video_id")),
        "kind": to_optional_str(source.get("kind")),
        "status": to_optional_str(source.get("status")),
        "idempotency_key": to_optional_str(source.get("idempotency_key")),
        "error_message": to_optional_str(source.get("error_message")),
        "artifact_digest_md": to_optional_str(source.get("artifact_digest_md")),
        "artifact_root": to_optional_str(source.get("artifact_root")),
        "llm_required": to_optional_bool(source.get("llm_required")),
        "llm_gate_passed": to_optional_bool(source.get("llm_gate_passed")),
        "hard_fail_reason": to_optional_str(source.get("hard_fail_reason")),
        "created_at": to_optional_str(source.get("created_at")),
        "updated_at": to_optional_str(source.get("updated_at")),
        "step_summary": [_normalize_step(item) for item in step_summary_items],
        "steps": [_normalize_step_detail(item) for item in step_items],
        "degradations": [_normalize_degradation(item) for item in degradation_items],
        "pipeline_final_status": to_optional_str(source.get("pipeline_final_status")),
        "artifacts_index": _normalize_artifacts_index(source.get("artifacts_index")),
        "mode": to_optional_str(source.get("mode")),
        "notification_retry": _normalize_notification_retry(source.get("notification_retry")),
    }


def _normalize_job_compare_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return payload
    return {
        "job_id": to_optional_str(payload.get("job_id")),
        "previous_job_id": to_optional_str(payload.get("previous_job_id")),
        "has_previous": to_optional_bool(payload.get("has_previous")),
        "current_digest": to_optional_str(payload.get("current_digest")),
        "previous_digest": to_optional_str(payload.get("previous_digest")),
        "diff_markdown": to_optional_str(payload.get("diff_markdown")) or "",
        "stats": to_optional_dict(payload.get("stats")) or {},
    }


def register_job_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(name="sourceharbor.jobs.get", description="Get one job by id.")
    def get_job(job_id: str) -> dict[str, Any]:
        normalized_job_id = parse_uuid(job_id)
        if normalized_job_id is None:
            return invalid_argument(
                "job_id must be a valid UUID",
                method="GET",
                path="/api/v1/jobs/{job_id}",
                field="job_id",
                value=job_id,
            )
        response = api_call("GET", f"/api/v1/jobs/{url_path_segment(normalized_job_id)}")
        return _normalize_job_payload(response)

    @mcp.tool(
        name="sourceharbor.jobs.compare",
        description="Compare one job against its previous successful run.",
    )
    def compare_job(job_id: str) -> dict[str, Any]:
        normalized_job_id = parse_uuid(job_id)
        if normalized_job_id is None:
            return invalid_argument(
                "job_id must be a valid UUID",
                method="GET",
                path="/api/v1/jobs/{job_id}/compare",
                field="job_id",
                value=job_id,
            )
        response = api_call("GET", f"/api/v1/jobs/{url_path_segment(normalized_job_id)}/compare")
        return _normalize_job_compare_payload(response)

    @mcp.tool(name="sourceharbor.videos.list", description="List ingested videos.")
    def list_videos(
        platform: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized_limit, limit_error = parse_bounded_int(
            limit,
            field="limit",
            min_value=1,
            max_value=500,
        )
        if limit_error is not None:
            return invalid_argument(
                limit_error,
                method="GET",
                path="/api/v1/videos",
                field="limit",
                value=limit,
            )
        return api_call(
            "GET",
            "/api/v1/videos",
            params={
                "platform": platform,
                "status": status,
                "limit": normalized_limit,
            },
        )

    @mcp.tool(
        name="sourceharbor.videos.process", description="Trigger ProcessJobWorkflow for one video."
    )
    def process_video(
        video: dict[str, Any],
        mode: str = "full",
        overrides: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        normalized_video, video_error = validate_object_keys(
            video,
            allowed_keys={"platform", "url", "video_id"},
        )
        if video_error is not None or normalized_video is None:
            return invalid_argument(
                f"video {video_error or 'is invalid'}",
                method="POST",
                path="/api/v1/videos/process",
                field="video",
            )
        platform = normalized_video.get("platform")
        url = normalized_video.get("url")
        if not isinstance(platform, str) or not platform.strip():
            return invalid_argument(
                "video.platform is required",
                method="POST",
                path="/api/v1/videos/process",
                field="video.platform",
            )
        if not isinstance(url, str) or not url.strip():
            return invalid_argument(
                "video.url is required",
                method="POST",
                path="/api/v1/videos/process",
                field="video.url",
            )
        normalized_overrides, overrides_error = validate_object_keys(
            overrides or {},
            allowed_keys={"comments", "frames", "llm", "llm_outline", "llm_digest"},
        )
        if overrides_error is not None or normalized_overrides is None:
            return invalid_argument(
                f"overrides {overrides_error or 'is invalid'}",
                method="POST",
                path="/api/v1/videos/process",
                field="overrides",
            )
        if any(not isinstance(value, dict) for value in normalized_overrides.values()):
            return invalid_argument(
                "overrides values must be objects",
                method="POST",
                path="/api/v1/videos/process",
                field="overrides",
            )
        return api_call(
            "POST",
            "/api/v1/videos/process",
            json_body={
                "video": normalized_video,
                "mode": mode,
                "overrides": normalized_overrides,
                "force": force,
            },
        )
