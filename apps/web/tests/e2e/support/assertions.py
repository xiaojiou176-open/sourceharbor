from __future__ import annotations

from collections.abc import Callable
from typing import Any

from support.mock_api import MockApiState


def _wait_for_state(
    state: MockApiState,
    predicate: Callable[[], bool],
    timeout_sec: float,
    error_message: str,
) -> None:
    with state.condition:
        if state.condition.wait_for(predicate, timeout=timeout_sec):
            return
    raise AssertionError(error_message)


def wait_for_call_count(
    state: MockApiState,
    key: str,
    expected: int,
    timeout_sec: float = 5.0,
    *,
    exact: bool = True,
) -> None:
    qualifier = "==" if exact else ">="
    _wait_for_state(
        state,
        lambda: (
            (len(state.calls[key]) == expected) if exact else (len(state.calls[key]) >= expected)
        ),
        timeout_sec,
        f"Timed out waiting for `{key}` calls: expected {qualifier} {expected}, actual={state.call_count(key)}",
    )


def wait_for_http_path(state: MockApiState, path: str, timeout_sec: float = 5.0) -> None:
    _wait_for_state(
        state,
        lambda: any(item.get("path") == path for item in state.calls["http"]),
        timeout_sec,
        f"Timed out waiting for HTTP path call: {path}",
    )


def wait_for_http_query_fragment(
    state: MockApiState,
    path: str,
    query_fragment: str,
    timeout_sec: float = 5.0,
) -> None:
    _wait_for_state(
        state,
        lambda: any(
            item.get("path") == path and query_fragment in item.get("query", "")
            for item in state.calls["http"]
        ),
        timeout_sec,
        f"Timed out waiting for HTTP query fragment: {path}?...{query_fragment}",
    )


def _find_http_call(
    calls: list[dict[str, Any]],
    *,
    method_upper: str | None,
    path: str | None,
    status: int | None,
    query_fragment: str | None,
    payload_contains: dict[str, Any] | None,
    payload_check: Callable[[dict[str, Any] | None], bool] | None,
) -> dict[str, Any] | None:
    for call in calls:
        if method_upper and call.get("method") != method_upper:
            continue
        if path and call.get("path") != path:
            continue
        if status is not None and call.get("status") != status:
            continue
        if query_fragment and query_fragment not in call.get("query", ""):
            continue
        payload = call.get("payload")
        if payload_contains:
            if not isinstance(payload, dict):
                continue
            if not all(payload.get(k) == v for k, v in payload_contains.items()):
                continue
        if payload_check and not payload_check(payload if isinstance(payload, dict) else None):
            continue
        return dict(call)
    return None


def wait_for_http_call(
    state: MockApiState,
    *,
    method: str | None = None,
    path: str | None = None,
    status: int | None = None,
    query_fragment: str | None = None,
    payload_contains: dict[str, Any] | None = None,
    payload_check: Callable[[dict[str, Any] | None], bool] | None = None,
    timeout_sec: float = 5.0,
) -> dict[str, Any]:
    method_upper = method.upper() if method else None

    with state.condition:
        matched = state.condition.wait_for(
            lambda: (
                _find_http_call(
                    state.calls["http"],
                    method_upper=method_upper,
                    path=path,
                    status=status,
                    query_fragment=query_fragment,
                    payload_contains=payload_contains,
                    payload_check=payload_check,
                )
                is not None
            ),
            timeout=timeout_sec,
        )
        if matched:
            result = _find_http_call(
                state.calls["http"],
                method_upper=method_upper,
                path=path,
                status=status,
                query_fragment=query_fragment,
                payload_contains=payload_contains,
                payload_check=payload_check,
            )
            if result is not None:
                return result

    raise AssertionError(
        "Timed out waiting for HTTP call "
        f"(method={method!r}, path={path!r}, status={status!r}, query_fragment={query_fragment!r})"
    )
