from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

from worker.pipeline.steps.llm_client_helpers import ComputerUseHandler

ComputerUseExecutor = Callable[[dict[str, Any]], dict[str, Any]]


def _coerce_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _base64_png(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _resolve_computer_use_payload(
    *,
    state: dict[str, Any],
    llm_policy: dict[str, Any],
    section_policy: dict[str, Any],
) -> dict[str, Any]:
    metadata = _coerce_dict(state.get("metadata"))
    state_payload = _coerce_dict(state.get("computer_use"))
    llm_payload = _coerce_dict(llm_policy.get("computer_use"))
    section_payload = _coerce_dict(section_policy.get("computer_use"))
    return {
        "executor": (
            section_payload.get("executor")
            or section_policy.get("computer_use_executor")
            or llm_payload.get("executor")
            or llm_policy.get("computer_use_executor")
            or state_payload.get("executor")
            or "playwright"
        ),
        "url": (
            section_payload.get("url")
            or section_policy.get("computer_use_url")
            or llm_payload.get("url")
            or llm_policy.get("computer_use_url")
            or state_payload.get("url")
            or state.get("source_url")
            or metadata.get("webpage_url")
            or ""
        ),
        "screenshot": (
            section_payload.get("screenshot")
            or section_policy.get("computer_use_screenshot")
            or llm_payload.get("screenshot")
            or llm_policy.get("computer_use_screenshot")
            or state_payload.get("screenshot")
            or ""
        ),
        "context": (
            section_payload.get("context")
            or section_policy.get("computer_use_context")
            or llm_payload.get("context")
            or llm_policy.get("computer_use_context")
            or state_payload.get("context")
            or {}
        ),
    }


def _normalize_action(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    action_name = (
        str(payload.get("action") or payload.get("type") or payload.get("name") or "")
        .strip()
        .lower()
    )
    action_args = {
        key: value
        for key, value in payload.items()
        if key not in {"action", "type", "name", "url", "screenshot", "context"}
    }
    return action_name, action_args


def _execute_noop(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
    if not action_name:
        return {"ok": False, "status": "error", "error": "computer_use_action_missing"}
    return {
        "ok": False,
        "status": "unsupported",
        "message": "computer_use_noop_blocked",
        "action": {"name": action_name, "args": action_args},
    }


def _execute_browser_stub(action_name: str, action_args: dict[str, Any]) -> dict[str, Any]:
    if not action_name:
        return {"ok": False, "status": "error", "error": "computer_use_action_missing"}
    return {
        "ok": False,
        "status": "degraded",
        "message": "computer_use_browser_stub_simulated",
        "action": {"name": action_name, "args": action_args},
    }


def _execute_playwright(
    *,
    action_name: str,
    action_args: dict[str, Any],
    url: str,
) -> dict[str, Any]:
    if not action_name:
        return {"ok": False, "status": "error", "error": "computer_use_action_missing"}
    if not url:
        return {"ok": False, "status": "error", "error": "computer_use_target_url_missing"}

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return {
            "ok": False,
            "status": "error",
            "error": f"computer_use_playwright_unavailable:{exc}",
        }

    selector = str(
        action_args.get("selector") or action_args.get("target") or action_args.get("element") or ""
    ).strip()
    text_value = str(action_args.get("text") or action_args.get("input_text") or "").strip()
    wait_ms = int(action_args.get("wait_ms") or 800)
    timeout_ms = int(action_args.get("timeout_ms") or 8000)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            normalized = action_name.lower()
            if normalized in {"click", "tap"}:
                page.click(selector, timeout=timeout_ms)
            elif normalized in {"type", "fill", "input"}:
                page.fill(selector, text_value, timeout=timeout_ms)
            elif normalized in {"navigate", "goto"}:
                next_url = str(action_args.get("url") or "").strip()
                if not next_url:
                    raise ValueError("navigate action requires url")
                page.goto(next_url, timeout=timeout_ms, wait_until="domcontentloaded")
            elif normalized in {"wait", "sleep"}:
                page.wait_for_timeout(wait_ms)
            elif normalized in {"scroll"}:
                page.evaluate("window.scrollBy(0, Math.max(200, window.innerHeight * 0.8));")
            else:
                page.wait_for_timeout(100)
            screenshot_bytes = page.screenshot(type="png", full_page=False)
            current_url = page.url
            browser.close()
            return {
                "ok": True,
                "status": "ok",
                "message": "computer_use_playwright_executed",
                "action": {"name": action_name, "args": action_args},
                "current_url": current_url,
                "screenshot_base64": _base64_png(screenshot_bytes),
            }
    except Exception as exc:
        return {"ok": False, "status": "error", "error": f"computer_use_playwright_failed:{exc}"}


def _executor_name(raw: Any) -> str:
    if raw is None:
        return "no_op"
    candidate = str(raw).strip().lower()
    if candidate in {"playwright", "browser_playwright"}:
        return "playwright"
    if candidate in {"browser", "browser_stub"}:
        return "browser_stub"
    return "no_op"


def build_default_computer_use_handler(
    *,
    state: dict[str, Any],
    llm_policy: dict[str, Any],
    section_policy: dict[str, Any],
) -> ComputerUseHandler:
    base_payload = _resolve_computer_use_payload(
        state=state,
        llm_policy=llm_policy,
        section_policy=section_policy,
    )
    executor = _executor_name(base_payload.get("executor"))

    def _handler(**payload: Any) -> dict[str, Any]:
        incoming = dict(payload or {})
        action_name, action_args = _normalize_action(incoming)
        requested_url = str(incoming.get("url") or "").strip()
        if action_name in {"navigate", "goto"} and requested_url:
            action_args["url"] = requested_url
        url = str(incoming.get("url") or base_payload.get("url") or "").strip()
        screenshot = str(incoming.get("screenshot") or base_payload.get("screenshot") or "").strip()
        context = incoming.get("context")
        if context is None:
            context = base_payload.get("context")
        context_payload = _coerce_dict(context) if isinstance(context, dict) else {"value": context}

        if executor == "playwright":
            result = _execute_playwright(
                action_name=action_name,
                action_args=action_args,
                url=url,
            )
            status_value = result.get("status")
            if isinstance(status_value, str) and status_value.strip().lower() == "error":
                fallback = _execute_browser_stub(action_name, action_args)
                result = {
                    **fallback,
                    "fallback_from": "playwright",
                    "playwright_error": str(result.get("error") or ""),
                }
        elif executor == "browser_stub":
            result = _execute_browser_stub(action_name, action_args)
        else:
            result = _execute_noop(action_name, action_args)

        return {
            **result,
            "executor": executor,
            "target": {
                "url": url,
                "screenshot": screenshot,
                "context": context_payload,
            },
        }

    return _handler
