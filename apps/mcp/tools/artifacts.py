from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_artifact_relative_path,
    parse_uuid,
    to_optional_str,
)


def _normalize_markdown_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return payload

    markdown = payload.get("markdown")
    if not isinstance(markdown, str):
        text = payload.get("text")
        markdown = text if isinstance(text, str) else ""

    return {
        "markdown": markdown,
        "job_id": to_optional_str(payload.get("job_id")),
        "video_url": to_optional_str(payload.get("video_url")),
        "found": bool(markdown),
    }


def _is_not_found_error(payload: dict[str, Any]) -> bool:
    details = payload.get("details")
    if not isinstance(details, dict):
        return False
    status_code = details.get("status_code")
    return isinstance(status_code, int) and status_code == 404


def register_artifact_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.artifacts.get",
        description="Get artifacts. kind=markdown|asset.",
    )
    def get_artifact(
        kind: str,
        job_id: str | None = None,
        video_url: str | None = None,
        path: str | None = None,
        include_base64: bool = False,
    ) -> dict[str, Any]:
        normalized_kind = str(kind or "").strip().lower()
        if normalized_kind == "markdown":
            normalized_job_id: str | None = None
            if job_id is not None:
                normalized_job_id = parse_uuid(job_id)
                if normalized_job_id is None:
                    return invalid_argument(
                        "job_id must be a valid UUID when kind=markdown",
                        method="GET",
                        path="/api/v1/artifacts/markdown",
                        field="job_id",
                        value=job_id,
                    )
            response = api_call(
                "GET",
                "/api/v1/artifacts/markdown",
                params={
                    "job_id": normalized_job_id,
                    "video_url": video_url,
                },
            )
            return _normalize_markdown_payload(response)

        if normalized_kind == "asset":
            if not job_id or not path:
                return invalid_argument(
                    "job_id and path are required when kind=asset",
                    method="GET",
                    path="/api/v1/artifacts/assets",
                )
            normalized_job_id = parse_uuid(job_id)
            if normalized_job_id is None:
                return invalid_argument(
                    "job_id must be a valid UUID when kind=asset",
                    method="GET",
                    path="/api/v1/artifacts/assets",
                    field="job_id",
                    value=job_id,
                )
            normalized_path = parse_artifact_relative_path(path)
            if normalized_path is None:
                return invalid_argument(
                    "path must be a safe relative artifact path",
                    method="GET",
                    path="/api/v1/artifacts/assets",
                    field="path",
                    value=path,
                )
            response = api_call(
                "GET",
                "/api/v1/artifacts/assets",
                params={"job_id": normalized_job_id, "path": normalized_path},
                return_bytes_base64=include_base64,
            )
            if is_error_payload(response):
                if not _is_not_found_error(response):
                    return response
                return {
                    **response,
                    "exists": False,
                    "asset_url": None,
                    "mime_type": None,
                    "base64": None,
                    "size_bytes": None,
                }
            query = urlencode({"job_id": normalized_job_id, "path": normalized_path})
            return {
                "exists": True,
                "asset_url": f"/api/v1/artifacts/assets?{query}",
                "mime_type": to_optional_str(response.get("mime_type"))
                or "application/octet-stream",
                "base64": to_optional_str(response.get("base64")) if include_base64 else None,
                "size_bytes": response.get("size_bytes") if include_base64 else None,
            }

        return invalid_argument(
            "kind must be one of: markdown, asset",
            method="GET",
            path="sourceharbor.artifacts.get",
            field="kind",
            value=kind,
        )
