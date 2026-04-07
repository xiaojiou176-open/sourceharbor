from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from sqlalchemy import text

from integrations.providers import gemini as gemini_provider
from integrations.providers import http_probe as http_probe_provider
from integrations.providers import resend as resend_provider
from integrations.providers import rsshub as rsshub_provider
from integrations.providers import youtube_data_api as youtube_provider
from worker.config import Settings
from worker.state.postgres_store import PostgresBusinessStore
from worker.temporal.activities_delivery import _classify_delivery_error
from worker.temporal.activities_email import (
    sanitize_text_preview as _sanitize_text_preview,
)
from worker.temporal.activities_email import (
    sanitize_url_for_payload as _sanitize_url_for_payload,
)
from worker.temporal.activities_timing import _coerce_int

try:
    from temporalio import activity
except ModuleNotFoundError:  # pragma: no cover

    class _ActivityFallback:
        @staticmethod
        def defn(name: str | None = None):
            def _decorator(func):
                return func

            return _decorator

    activity = _ActivityFallback()


HEALTH_CHECK_KINDS = ("rsshub", "youtube_data_api", "gemini", "resend")


def _classify_http_error_kind(*, status_code: int | None, error_message: str) -> str:
    if status_code in {401, 403}:
        return "auth"
    if status_code == 429:
        return "rate_limit"
    if status_code is not None and status_code >= 500:
        return "transient"
    return _classify_delivery_error(error_message)


def _http_probe(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 8,
) -> dict[str, Any]:
    return http_probe_provider.http_probe(
        url=url,
        method=method,
        headers=headers,
        timeout_seconds=timeout_seconds,
        request_cls=Request,
        urlopen_func=urlopen,
        sanitize_url=_sanitize_url_for_payload,
        sanitize_preview=_sanitize_text_preview,
        classify_error_kind=_classify_http_error_kind,
    )


def _record_provider_health_check(
    conn: Any,
    *,
    check_kind: str,
    status: str,
    error_kind: str | None,
    message: str,
    payload_json: dict[str, Any] | None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO provider_health_checks (
                check_kind,
                status,
                error_kind,
                message,
                payload_json,
                checked_at
            )
            VALUES (
                :check_kind,
                :status,
                :error_kind,
                :message,
                CAST(:payload_json AS JSONB),
                NOW()
            )
            """
        ),
        {
            "check_kind": check_kind,
            "status": status,
            "error_kind": error_kind,
            "message": message,
            "payload_json": (
                json.dumps(payload_json, ensure_ascii=False) if payload_json is not None else None
            ),
        },
    )


@activity.defn(name="provider_canary_activity")
async def provider_canary_activity(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    payload = payload or {}
    timeout_seconds = max(3, _coerce_int(payload.get("timeout_seconds"), fallback=8))

    checks: list[dict[str, Any]] = []

    rsshub_url = rsshub_provider.build_health_url(settings.rsshub_base_url)
    checks.append(
        {
            "check_kind": "rsshub",
            **_http_probe(url=rsshub_url, timeout_seconds=timeout_seconds),
        }
    )

    if settings.youtube_api_key:
        youtube_url = youtube_provider.build_video_probe_url(settings.youtube_api_key)
        checks.append(
            {
                "check_kind": "youtube_data_api",
                **_http_probe(url=youtube_url, timeout_seconds=timeout_seconds),
            }
        )
    else:
        checks.append(
            {
                "check_kind": "youtube_data_api",
                "status": "warn",
                "error_kind": "config_error",
                "message": "YOUTUBE_API_KEY is not configured",
                "payload_json": {},
            }
        )

    if settings.gemini_api_key:
        gemini_url = gemini_provider.build_models_probe_url(settings.gemini_api_key)
        checks.append(
            {
                "check_kind": "gemini",
                **_http_probe(url=gemini_url, timeout_seconds=timeout_seconds),
            }
        )
    else:
        checks.append(
            {
                "check_kind": "gemini",
                "status": "warn",
                "error_kind": "config_error",
                "message": "GEMINI_API_KEY is not configured",
                "payload_json": {},
            }
        )

    if settings.resend_api_key and settings.resend_from_email:
        resend_url, resend_headers = resend_provider.build_domains_probe_request(
            settings.resend_api_key
        )
        checks.append(
            {
                "check_kind": "resend",
                **_http_probe(
                    url=resend_url,
                    headers=resend_headers,
                    timeout_seconds=timeout_seconds,
                ),
            }
        )
    else:
        checks.append(
            {
                "check_kind": "resend",
                "status": "warn",
                "error_kind": "config_error",
                "message": "RESEND_API_KEY or RESEND_FROM_EMAIL is not configured",
                "payload_json": {},
            }
        )

    with pg_store._engine.begin() as conn:  # type: ignore[attr-defined]
        for check in checks:
            kind = str(check.get("check_kind") or "")
            if kind not in HEALTH_CHECK_KINDS:
                continue
            _record_provider_health_check(
                conn,
                check_kind=kind,
                status=str(check.get("status") or "fail"),
                error_kind=(
                    str(check.get("error_kind"))
                    if isinstance(check.get("error_kind"), str)
                    else None
                ),
                message=str(check.get("message") or ""),
                payload_json=(
                    check.get("payload_json") if isinstance(check.get("payload_json"), dict) else {}
                ),
            )

    summary = {"ok": 0, "warn": 0, "fail": 0}
    for check in checks:
        status = str(check.get("status") or "fail")
        if status not in summary:
            status = "fail"
        summary[status] += 1

    return {
        "ok": True,
        "checks": checks,
        "summary": summary,
    }
