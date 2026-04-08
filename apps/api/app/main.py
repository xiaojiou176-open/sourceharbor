from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from apps.runtime_paths import get_runtime_cache_root, get_runtime_root

from .config import settings
from .routers import (
    artifacts,
    computer_use,
    feed,
    health,
    ingest,
    jobs,
    knowledge,
    notifications,
    ops,
    retrieval,
    subscriptions,
    ui_audit,
    videos,
    watchlists,
    workflows,
)

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_TRACEPARENT_PATTERN = re.compile(r"^[\da-f]{2}-([\da-f]{32})-[\da-f]{16}-[\da-f]{2}$")
_METRICS_LOCK = threading.Lock()
_PROCESS_STARTED_UNIX = time.time()
_REQUEST_COUNTER: dict[tuple[str, str, str], int] = defaultdict(int)
_REQUEST_DURATION: dict[tuple[str, str], dict[str, float]] = defaultdict(
    lambda: {"count": 0.0, "sum": 0.0}
)
_RUNTIME_ROOT = get_runtime_root()
_APP_LOG_PATH = get_runtime_cache_root() / "logs" / "app" / "api-http.jsonl"
_ENV_PROFILE = os.getenv("ENV_PROFILE", "unknown")


def _resolve_repo_commit() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=_RUNTIME_ROOT,
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
            or "unknown"
        )
    except OSError:
        return "unknown"


_REPO_COMMIT = _resolve_repo_commit()


def _escape_metric_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _request_route_label(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path.strip():
        return route_path.strip()
    path = request.url.path.strip()
    return path or "/"


def _resolve_trace_id(request: Request) -> str:
    trace_id = request.headers.get("x-trace-id", "").strip()
    if trace_id and _TRACE_ID_PATTERN.match(trace_id):
        return trace_id
    traceparent = request.headers.get("traceparent", "").strip().lower()
    if traceparent:
        matched = _TRACEPARENT_PATTERN.match(traceparent)
        if matched:
            return matched.group(1)
    return uuid.uuid4().hex


def _append_app_request_log(
    *,
    trace_id: str,
    route_label: str,
    method: str,
    status_code: int,
    elapsed_seconds: float,
) -> None:
    _APP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": trace_id,
        "trace_id": trace_id,
        "request_id": trace_id,
        "service": "api",
        "component": "http",
        "channel": "app",
        "event": "http_request",
        "severity": "info",
        "source_kind": "app",
        "repo_commit": _REPO_COMMIT,
        "entrypoint": "apps.api.app.main:request_observability_middleware",
        "env_profile": _ENV_PROFILE,
        "message": f"{method} {route_label} -> {status_code}",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": method,
        "route": route_label,
        "status_code": status_code,
        "duration_seconds": round(elapsed_seconds, 6),
    }
    with _APP_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    trace_id = _resolve_trace_id(request)
    request.state.trace_id = trace_id
    started = time.perf_counter()
    method = request.method.upper()
    route_label = _request_route_label(request)
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        elapsed = max(0.0, time.perf_counter() - started)
        with _METRICS_LOCK:
            _REQUEST_COUNTER[(method, route_label, str(status_code))] += 1
            duration = _REQUEST_DURATION[(method, route_label)]
            duration["count"] += 1.0
            duration["sum"] += elapsed
        _append_app_request_log(
            trace_id=trace_id,
            route_label=route_label,
            method=method,
            status_code=status_code,
            elapsed_seconds=elapsed,
        )
        raise

    elapsed = max(0.0, time.perf_counter() - started)
    with _METRICS_LOCK:
        _REQUEST_COUNTER[(method, route_label, str(status_code))] += 1
        duration = _REQUEST_DURATION[(method, route_label)]
        duration["count"] += 1.0
        duration["sum"] += elapsed
    _append_app_request_log(
        trace_id=trace_id,
        route_label=route_label,
        method=method,
        status_code=status_code,
        elapsed_seconds=elapsed,
    )
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.get("/healthz", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["system"])
def readiness_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> PlainTextResponse:
    lines = [
        "# HELP sourceharbor_process_start_time_seconds Unix time when the API process started.",
        "# TYPE sourceharbor_process_start_time_seconds gauge",
        f"sourceharbor_process_start_time_seconds {_PROCESS_STARTED_UNIX:.3f}",
        "# HELP sourceharbor_http_requests_total Total HTTP requests handled by method, route and status.",
        "# TYPE sourceharbor_http_requests_total counter",
    ]
    with _METRICS_LOCK:
        request_counter_items = sorted(_REQUEST_COUNTER.items())
        request_duration_items = sorted(_REQUEST_DURATION.items())

    for (method, route, status), total in request_counter_items:
        lines.append(
            "sourceharbor_http_requests_total{"
            f'method="{_escape_metric_label(method)}",'
            f'route="{_escape_metric_label(route)}",'
            f'status="{_escape_metric_label(status)}"'
            f"}} {total}"
        )

    lines.extend(
        [
            "# HELP sourceharbor_http_request_duration_seconds_sum Total request duration in seconds by method and route.",
            "# TYPE sourceharbor_http_request_duration_seconds_sum counter",
            "# HELP sourceharbor_http_request_duration_seconds_count Total sampled requests by method and route.",
            "# TYPE sourceharbor_http_request_duration_seconds_count counter",
        ]
    )
    for (method, route), duration in request_duration_items:
        lines.append(
            "sourceharbor_http_request_duration_seconds_sum{"
            f'method="{_escape_metric_label(method)}",'
            f'route="{_escape_metric_label(route)}"'
            f"}} {duration['sum']:.9f}"
        )
        lines.append(
            "sourceharbor_http_request_duration_seconds_count{"
            f'method="{_escape_metric_label(method)}",'
            f'route="{_escape_metric_label(route)}"'
            f"}} {int(duration['count'])}"
        )

    return PlainTextResponse(
        "\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


app.include_router(subscriptions.router)
app.include_router(feed.router)
app.include_router(ingest.router)
app.include_router(jobs.router)
app.include_router(knowledge.router)
app.include_router(videos.router)
app.include_router(notifications.router)
app.include_router(notifications.reports_router)
app.include_router(ops.router)
app.include_router(artifacts.router)
app.include_router(health.router)
app.include_router(workflows.router)
app.include_router(retrieval.router)
app.include_router(computer_use.router)
app.include_router(ui_audit.router)
app.include_router(watchlists.router)
