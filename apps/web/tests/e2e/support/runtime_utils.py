from __future__ import annotations

import errno
import os
import re
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from threading import Event
from typing import TypeVar
from urllib.parse import urlparse
from urllib.request import urlopen

T = TypeVar("T")
_PAUSE_EVENT = Event()


def slugify_nodeid(nodeid: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", nodeid).strip("-")
    return value or "unknown-test"


def sanitize_worker_id(raw: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-")
    return value or "gw0"


def resolve_worker_id(
    cli_worker_id: str | None,
    *,
    xdist_worker_id: str | None = None,
    browser_name: str | None = None,
    process_id: int | None = None,
) -> str:
    """Return a stable worker id, unique by process when xdist/cli ids are missing."""
    if xdist_worker_id is not None and xdist_worker_id.strip():
        return sanitize_worker_id(xdist_worker_id)
    if cli_worker_id is not None and cli_worker_id.strip():
        return sanitize_worker_id(cli_worker_id)

    browser = sanitize_worker_id(browser_name or "browser")
    pid = int(process_id) if process_id is not None else os.getpid()
    return sanitize_worker_id(f"{browser}-p{pid}")


def worker_dist_dir(worker_id: str) -> str:
    return f".next-e2e-{sanitize_worker_id(worker_id)}"


def free_port() -> int:
    # Chromium in this environment occasionally reports ERR_ADDRESS_INVALID for
    # some very high ephemeral ports. Keep web-e2e ports in a safer range.
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
            if port < 60_000:
                return port
    return port


def is_port_in_use_error(exc: BaseException) -> bool:
    return isinstance(exc, OSError) and exc.errno == errno.EADDRINUSE


def with_free_port_retry(
    start: Callable[[int], T],
    *,
    attempts: int = 3,
    port_supplier: Callable[[], int] | None = None,
    retry_if: Callable[[Exception], bool] | None = None,
) -> tuple[T, int]:
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    provide_port = port_supplier or free_port
    should_retry = retry_if or is_port_in_use_error
    last_error: Exception | None = None

    for attempt in range(attempts):
        port = provide_port()
        try:
            return start(port), port
        except Exception as exc:
            if should_retry(exc) and attempt < attempts - 1:
                last_error = exc
                continue
            raise

    raise RuntimeError(f"Unable to start service after {attempts} attempts") from last_error


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def wait_http_ok(url: str, timeout_sec: float = 150.0) -> None:
    deadline = time.monotonic() + timeout_sec
    last_error: Exception | None = None
    backoff_sec = 0.05
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                if response.status < HTTPStatus.INTERNAL_SERVER_ERROR:
                    return
        except Exception as exc:  # pragma: no cover - only for startup retries
            last_error = exc
        remaining = deadline - time.monotonic()
        if remaining > 0:
            _PAUSE_EVENT.wait(min(backoff_sec, remaining))
            backoff_sec = min(backoff_sec * 2, 0.5)
    raise RuntimeError(f"Timeout waiting for server readiness: {url}. Last error: {last_error}")


def parse_external_web_base_url(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    candidate = raw_value.strip().rstrip("/")
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(
            f"--web-e2e-base-url must be an absolute http(s) URL, got: {raw_value!r}"
        )
    return candidate
