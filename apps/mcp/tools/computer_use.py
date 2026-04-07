from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from apps.mcp.tools._common import (
    DEFAULT_MAX_BASE64_BYTES,
    ApiCall,
    invalid_argument,
    is_error_payload,
    parse_bool,
    parse_bounded_int,
    to_optional_bool,
    to_optional_dict,
    to_optional_str,
    validate_base64_size,
    validate_object_keys,
)


def _normalize_action_item(item: Any, default_step: int) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    step = source.get("step")
    if not isinstance(step, int) or step < 1:
        step = default_step
    action = to_optional_str(source.get("action")) or "observe"
    return {
        "step": step,
        "action": action,
        "target": to_optional_str(source.get("target")),
        "input_text": to_optional_str(source.get("input_text")),
        "reasoning": to_optional_str(source.get("reasoning")),
    }


def register_computer_use_tools(mcp: FastMCP, api_call: ApiCall) -> None:
    @mcp.tool(
        name="sourceharbor.computer_use.run",
        description="Plan computer-use actions from an instruction and screenshot with safety policy checks.",
    )
    def run_computer_use(
        instruction: str,
        screenshot_base64: str,
        safety: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_instruction = str(instruction or "").strip()
        if not normalized_instruction:
            return invalid_argument(
                "instruction must be a non-empty string",
                method="POST",
                path="/api/v1/computer-use/run",
                field="instruction",
            )
        screenshot_ok, screenshot_error = validate_base64_size(
            screenshot_base64,
            max_bytes=DEFAULT_MAX_BASE64_BYTES,
        )
        if not screenshot_ok:
            return invalid_argument(
                f"screenshot_base64 {screenshot_error or 'is invalid'}",
                method="POST",
                path="/api/v1/computer-use/run",
                field="screenshot_base64",
            )
        normalized_safety, safety_error = validate_object_keys(
            safety or {},
            allowed_keys={"confirm_before_execute", "blocked_actions", "max_actions"},
        )
        if safety_error is not None or normalized_safety is None:
            return invalid_argument(
                f"safety {safety_error or 'is invalid'}",
                method="POST",
                path="/api/v1/computer-use/run",
                field="safety",
            )
        confirm_before_execute, confirm_before_execute_error = parse_bool(
            normalized_safety.get("confirm_before_execute"),
            field="safety.confirm_before_execute",
        )
        if confirm_before_execute_error is not None:
            return invalid_argument(
                confirm_before_execute_error,
                method="POST",
                path="/api/v1/computer-use/run",
                field="safety.confirm_before_execute",
                value=normalized_safety.get("confirm_before_execute"),
            )
        max_actions, max_actions_error = parse_bounded_int(
            normalized_safety.get("max_actions"),
            field="safety.max_actions",
            min_value=1,
            max_value=20,
        )
        if max_actions_error is not None:
            return invalid_argument(
                max_actions_error,
                method="POST",
                path="/api/v1/computer-use/run",
                field="safety.max_actions",
                value=normalized_safety.get("max_actions"),
            )
        blocked_actions = normalized_safety.get("blocked_actions")
        if blocked_actions is not None and (
            not isinstance(blocked_actions, list)
            or any(not isinstance(item, str) or not item.strip() for item in blocked_actions)
        ):
            return invalid_argument(
                "safety.blocked_actions must be a list of non-empty strings",
                method="POST",
                path="/api/v1/computer-use/run",
                field="safety.blocked_actions",
            )
        normalized_safety_payload: dict[str, Any] = {}
        if confirm_before_execute is not None:
            normalized_safety_payload["confirm_before_execute"] = confirm_before_execute
        if blocked_actions is not None:
            normalized_safety_payload["blocked_actions"] = blocked_actions
        if max_actions is not None:
            normalized_safety_payload["max_actions"] = max_actions
        response = api_call(
            "POST",
            "/api/v1/computer-use/run",
            json_body={
                "instruction": normalized_instruction,
                "screenshot_base64": screenshot_base64,
                "safety": normalized_safety_payload,
            },
        )
        if is_error_payload(response):
            return response

        raw_actions = response.get("actions")
        raw_blocked_actions = response.get("blocked_actions")
        return {
            "actions": [
                _normalize_action_item(item, default_step=index)
                for index, item in enumerate(
                    raw_actions if isinstance(raw_actions, list) else [], start=1
                )
            ],
            "require_confirmation": bool(to_optional_bool(response.get("require_confirmation"))),
            "blocked_actions": [
                value
                for value in (
                    to_optional_str(item)
                    for item in (
                        raw_blocked_actions if isinstance(raw_blocked_actions, list) else []
                    )
                )
                if value is not None
            ],
            "final_text": to_optional_str(response.get("final_text")) or "",
            "thought_metadata": to_optional_dict(response.get("thought_metadata")) or {},
        }
