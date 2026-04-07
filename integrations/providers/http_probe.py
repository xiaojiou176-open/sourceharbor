from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError


def http_probe(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 8,
    request_cls: Callable[..., Any],
    urlopen_func: Callable[..., Any],
    sanitize_url: Callable[[str], str],
    sanitize_preview: Callable[[str], str],
    classify_error_kind: Callable[..., str],
) -> dict[str, Any]:
    sanitized_url = sanitize_url(url)
    request = request_cls(url, headers=headers or {}, method=method)
    try:
        with urlopen_func(request, timeout=timeout_seconds) as response:
            status_code = int(response.status)
            body_preview = sanitize_preview(response.read(512).decode("utf-8", errors="replace"))
    except HTTPError as exc:
        error_body = sanitize_preview(exc.read().decode("utf-8", errors="replace"))
        error_kind = classify_error_kind(status_code=exc.code, error_message=error_body)
        status = "warn" if error_kind == "rate_limit" else "fail"
        return {
            "status": status,
            "error_kind": error_kind,
            "message": f"http_error:{exc.code}",
            "payload_json": {
                "url": sanitized_url,
                "status_code": exc.code,
                "body": error_body,
            },
        }
    except URLError as exc:
        reason = sanitize_preview(str(exc.reason))
        return {
            "status": "fail",
            "error_kind": "transient",
            "message": f"network_error:{reason}",
            "payload_json": {"url": sanitized_url},
        }

    if 200 <= status_code < 300:
        return {
            "status": "ok",
            "error_kind": None,
            "message": "ok",
            "payload_json": {"url": sanitized_url, "status_code": status_code},
        }

    error_kind = classify_error_kind(status_code=status_code, error_message=body_preview)
    return {
        "status": "warn" if error_kind == "rate_limit" else "fail",
        "error_kind": error_kind,
        "message": f"http_status:{status_code}",
        "payload_json": {
            "url": sanitized_url,
            "status_code": status_code,
            "body": body_preview,
        },
    }
