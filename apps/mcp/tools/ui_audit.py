from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    DEFAULT_MAX_BASE64_BYTES,
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_artifact_relative_path,
    parse_bounded_int,
    parse_uuid,
    to_int,
    to_optional_bool,
    to_optional_str,
    url_path_segment,
    validate_base64_size,
)


def _normalize_summary(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    severity_counts = source.get("severity_counts")
    normalized_counts: dict[str, int] = {}
    if isinstance(severity_counts, dict):
        for key, item in severity_counts.items():
            if isinstance(key, str):
                normalized_counts[key] = to_int(item, default=0)
    return {
        "artifact_count": to_int(source.get("artifact_count"), default=0),
        "finding_count": to_int(source.get("finding_count"), default=0),
        "severity_counts": normalized_counts,
    }


def _normalize_run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return payload

    source = payload.get("run") if isinstance(payload.get("run"), dict) else payload
    return {
        "run_id": to_optional_str(source.get("run_id")),
        "job_id": to_optional_str(source.get("job_id")),
        "artifact_root": to_optional_str(source.get("artifact_root")),
        "status": to_optional_str(source.get("status")) or "unknown",
        "created_at": to_optional_str(source.get("created_at")),
        "summary": _normalize_summary(source.get("summary")),
        "gemini_review": _normalize_gemini_review(source.get("gemini_review")),
    }


def _normalize_gemini_review(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    provider_status: int | None = None
    raw_provider_status = value.get("provider_status")
    if raw_provider_status is not None:
        parsed_status = to_int(raw_provider_status, default=0)
        if 100 <= parsed_status <= 599:
            provider_status = parsed_status
    return {
        "status": to_optional_str(value.get("status")) or "unknown",
        "reason_code": to_optional_str(value.get("reason_code")) or "unknown",
        "provider_status": provider_status,
        "model": to_optional_str(value.get("model")),
        "timeout_seconds": value.get("timeout_seconds"),
        "max_retries": to_int(value.get("max_retries"), default=0)
        if value.get("max_retries") is not None
        else None,
    }


def _normalize_finding(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "id": to_optional_str(source.get("id")) or "",
        "severity": to_optional_str(source.get("severity")) or "info",
        "title": to_optional_str(source.get("title")) or "",
        "message": to_optional_str(source.get("message")) or "",
        "rule": to_optional_str(source.get("rule")),
        "artifact_key": to_optional_str(source.get("artifact_key")),
    }


def _normalize_artifact(item: Any) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    return {
        "key": to_optional_str(source.get("key")) or "",
        "path": to_optional_str(source.get("path")) or "",
        "mime_type": to_optional_str(source.get("mime_type")) or "application/octet-stream",
        "size_bytes": to_int(source.get("size_bytes"), default=0),
        "category": to_optional_str(source.get("category")) or "artifact",
    }


def _normalize_autofix_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if is_error_payload(payload):
        return payload

    summary_source = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    guardrails_source = (
        payload.get("guardrails") if isinstance(payload.get("guardrails"), dict) else {}
    )
    guardrails = dict(guardrails_source)
    actions = payload.get("suggested_actions")
    raw_actions = actions if isinstance(actions, list) else []
    mode_value = to_optional_str(payload.get("mode")) or "dry-run"
    autofix_applied = bool(to_optional_bool(payload.get("autofix_applied")))
    if mode_value == "apply" and not autofix_applied:
        mode_value = "dry-run"
        upstream_note = to_optional_str(guardrails.get("note")) or ""
        honesty_note = "Apply mode is not supported; this result is a plan-only dry-run."
        guardrails["note"] = (
            f"{upstream_note} {honesty_note}".strip() if upstream_note else honesty_note
        )
    return {
        "run_id": to_optional_str(payload.get("run_id")),
        "mode": mode_value,
        "autofix_applied": autofix_applied,
        "summary": {
            "finding_count": to_int(summary_source.get("finding_count"), default=0),
            "high_or_worse_count": to_int(summary_source.get("high_or_worse_count"), default=0),
        },
        "guardrails": guardrails,
        "suggested_actions": [str(item) for item in raw_actions],
    }


def register_ui_audit_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.ui_audit.run",
        description="Run UI audit from artifact directory evidence and persist the run snapshot.",
    )
    def ui_audit_run(
        job_id: str | None = None,
        artifact_root: str | None = None,
    ) -> dict[str, Any]:
        normalized_job_id: str | None = None
        if job_id is not None:
            normalized_job_id = parse_uuid(job_id)
            if normalized_job_id is None:
                return invalid_argument(
                    "job_id must be a valid UUID",
                    method="POST",
                    path="/api/v1/ui-audit/run",
                    field="job_id",
                    value=job_id,
                )
        response = api_call(
            "POST",
            "/api/v1/ui-audit/run",
            json_body={
                "job_id": normalized_job_id,
                "artifact_root": artifact_root,
            },
        )
        return _normalize_run_payload(response)

    @mcp.tool(
        name="sourceharbor.ui_audit.read",
        description=(
            "Read UI audit results. action=get|list_findings|get_artifact|autofix. "
            "autofix currently returns a plan-only dry-run summary."
        ),
    )
    def ui_audit_read(
        action: str,
        run_id: str,
        severity: str | None = None,
        key: str | None = None,
        include_base64: bool = False,
        mode: str = "dry-run",
        max_files: int = 3,
        max_changed_lines: int = 120,
    ) -> dict[str, Any]:
        normalized_action = str(action or "").strip().lower()
        normalized_run_id = parse_uuid(run_id)
        if normalized_run_id is None:
            return invalid_argument(
                "run_id must be a valid UUID",
                method="POST",
                path="sourceharbor.ui_audit.read",
                field="run_id",
                value=run_id,
            )
        encoded_run_id = url_path_segment(normalized_run_id)

        if normalized_action == "get":
            response = api_call("GET", f"/api/v1/ui-audit/{encoded_run_id}")
            return _normalize_run_payload(response)

        if normalized_action == "list_findings":
            response = api_call(
                "GET",
                f"/api/v1/ui-audit/{encoded_run_id}/findings",
                params={"severity": severity},
            )
            if is_error_payload(response):
                return response
            items = response.get("items")
            raw_items = items if isinstance(items, list) else []
            return {
                "run_id": normalized_run_id,
                "severity": severity,
                "items": [_normalize_finding(item) for item in raw_items],
            }

        if normalized_action == "get_artifact":
            if not key:
                return invalid_argument(
                    "key is required when action=get_artifact",
                    method="GET",
                    path="/api/v1/ui-audit/{run_id}/artifact",
                    field="key",
                )
            normalized_key = parse_artifact_relative_path(key)
            if normalized_key is None:
                return invalid_argument(
                    "key must be a safe relative artifact path",
                    method="GET",
                    path="/api/v1/ui-audit/{run_id}/artifact",
                    field="key",
                    value=key,
                )
            response = api_call(
                "GET",
                f"/api/v1/ui-audit/{encoded_run_id}/artifact",
                params={
                    "key": normalized_key,
                    "include_base64": include_base64,
                },
            )
            if is_error_payload(response):
                return response
            payload = _normalize_artifact(response)
            payload["exists"] = bool(response.get("exists", False))
            if include_base64:
                encoded = to_optional_str(response.get("base64"))
                if encoded is not None:
                    valid, error_message = validate_base64_size(
                        encoded, max_bytes=DEFAULT_MAX_BASE64_BYTES
                    )
                    if not valid:
                        return {
                            "code": "PAYLOAD_TOO_LARGE",
                            "message": error_message or "base64 payload exceeds configured limit",
                            "details": {
                                "method": "GET",
                                "path": "/api/v1/ui-audit/{run_id}/artifact",
                                "field": "base64",
                                "max_size_bytes": DEFAULT_MAX_BASE64_BYTES,
                            },
                        }
                payload["base64"] = encoded
            else:
                payload["base64"] = None
            return payload

        if normalized_action == "autofix":
            normalized_max_files, max_files_error = parse_bounded_int(
                max_files,
                field="max_files",
                min_value=1,
                max_value=20,
                required=True,
            )
            if max_files_error is not None or normalized_max_files is None:
                return invalid_argument(
                    max_files_error or "max_files is invalid",
                    method="POST",
                    path=f"/api/v1/ui-audit/{encoded_run_id}/autofix",
                    field="max_files",
                    value=max_files,
                )
            normalized_max_changed_lines, max_changed_lines_error = parse_bounded_int(
                max_changed_lines,
                field="max_changed_lines",
                min_value=1,
                max_value=2000,
                required=True,
            )
            if max_changed_lines_error is not None or normalized_max_changed_lines is None:
                return invalid_argument(
                    max_changed_lines_error or "max_changed_lines is invalid",
                    method="POST",
                    path=f"/api/v1/ui-audit/{encoded_run_id}/autofix",
                    field="max_changed_lines",
                    value=max_changed_lines,
                )
            response = api_call(
                "POST",
                f"/api/v1/ui-audit/{encoded_run_id}/autofix",
                json_body={
                    "mode": mode,
                    "max_files": normalized_max_files,
                    "max_changed_lines": normalized_max_changed_lines,
                },
            )
            return _normalize_autofix_payload(response)

        return invalid_argument(
            "action must be one of: get, list_findings, get_artifact, autofix",
            method="POST",
            path="sourceharbor.ui_audit.read",
            field="action",
            value=action,
        )
