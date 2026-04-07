from __future__ import annotations

import asyncio
import io
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any, Self
from urllib.error import HTTPError, URLError

import httpx
from worker.temporal import (
    activities_delivery_payload,
    activities_delivery_policy,
    activities_email,
    activities_health,
    activities_timing,
)


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", payload: Any = None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeHTTPReadResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self, _size: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _DummyConn:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute(self, statement: Any, params: dict[str, Any]) -> None:
        self.calls.append({"statement": str(statement), "params": params})


class _DummyBegin:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def __enter__(self) -> Any:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _DummyEngine:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def begin(self) -> _DummyBegin:
        return _DummyBegin(self._conn)


class _DummyPGStore:
    def __init__(self, _database_url: str) -> None:
        self.conn = _DummyConn()
        self._engine = _DummyEngine(self.conn)


def test_delivery_payload_extractors_and_retry_payload() -> None:
    assert activities_delivery_payload.extract_daily_digest_date(None) is None
    assert activities_delivery_payload.extract_daily_digest_date({"digest_date": ""}) is None
    assert (
        activities_delivery_payload.extract_daily_digest_date({"digest_date": "not-a-date"}) is None
    )
    assert activities_delivery_payload.extract_daily_digest_date(
        {"digest_date": "2026-03-01"}
    ) == date(2026, 3, 1)

    assert activities_delivery_payload.extract_timezone_name(None) is None
    assert activities_delivery_payload.extract_timezone_name(
        {"timezone_name": "  Asia/Shanghai "}
    ) == ("Asia/Shanghai")
    assert activities_delivery_payload.extract_timezone_name({"timezone_name": ""}) is None

    assert (
        activities_delivery_payload.extract_timezone_offset_minutes(
            {"timezone_offset_minutes": "480"}, coerce_int=lambda v, d: int(v)
        )
        == 480
    )
    assert (
        activities_delivery_payload.extract_timezone_offset_minutes(
            None, coerce_int=lambda _v, d: d
        )
        == 0
    )

    error_kind, next_retry = activities_delivery_payload.build_retry_failure_payload(
        error_message="timeout",
        attempt_count=2,
        classify_delivery_error=lambda msg: f"kind:{msg}",
        resolve_next_retry_at=lambda **_: datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
    )
    assert error_kind == "kind:timeout"
    assert next_retry == datetime(2026, 3, 1, 8, 0, tzinfo=UTC)


def test_delivery_policy_helpers() -> None:
    assert (
        activities_delivery_policy.prepare_delivery_skip_reason(
            config={"enabled": True, "daily_digest_enabled": True},
            recipient_email=None,
            notification_enabled=True,
        )
        == "notification recipient email is not configured"
    )
    assert activities_delivery_policy.classify_delivery_error("401 unauthorized") == "auth"
    assert activities_delivery_policy.classify_delivery_error("network timeout") == "transient"
    assert activities_delivery_policy.resolve_retry_backoff_minutes(attempt_count=3) == 15
    assert (
        activities_delivery_policy.resolve_next_retry_at(
            attempt_count=5,
            error_kind="transient",
            now_utc=datetime(2026, 3, 1, 8, 0, tzinfo=UTC),
        )
        is None
    )


def test_email_sanitizers_and_html_rendering() -> None:
    secret_like_token = "provider-token-for-redaction"
    assert activities_email.normalize_email("  a@example.com ") == "a@example.com"
    assert activities_email.normalize_email("   ") is None
    assert activities_email.normalize_email(123) is None

    assert activities_email.is_sensitive_query_key("api_key") is True
    assert activities_email.is_sensitive_query_key("page") is False

    query_parts = ("a=1", "api_key=SECRET", "token=abc")
    sanitized_query = f"{query_parts[0]}&{query_parts[1]}&{query_parts[2]}"
    sanitized_url = activities_email.sanitize_url_for_payload(
        f"https://example.com/path?{sanitized_query}"
    )
    assert "api_key=%2A%2A%2AREDACTED%2A%2A%2A" in sanitized_url
    assert "token=%2A%2A%2AREDACTED%2A%2A%2A" in sanitized_url

    preview = activities_email.sanitize_text_preview(
        "Bearer "
        + secret_like_token
        + " "
        + "ghp_"
        + "12345678901234567890"
        + " "
        + "AKIA"
        + "IOSFODNN7EXAMPLE",
        max_chars=120,
    )
    assert "***REDACTED***" in preview
    assert secret_like_token not in preview

    html = activities_email.to_html("# Title\n\nBody")
    assert "<!doctype html>" in html
    assert "<article" in html


def test_send_with_resend_branches(monkeypatch: Any) -> None:
    try:
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key=None,
            resend_from_email="from@example.com",
        )
        raise AssertionError("expected missing api key to raise")
    except RuntimeError as exc:
        assert "RESEND_API_KEY" in str(exc)

    try:
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key="rk_test",
            resend_from_email=None,
        )
        raise AssertionError("expected missing from email to raise")
    except RuntimeError as exc:
        assert "RESEND_FROM_EMAIL" in str(exc)

    def _raise_request_error(*_: Any, **__: Any) -> Any:
        request = httpx.Request("POST", "https://api.resend.com/emails")
        raise httpx.RequestError("network down", request=request)

    monkeypatch.setattr(activities_email.httpx, "post", _raise_request_error)
    try:
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key="rk_test",
            resend_from_email="from@example.com",
        )
        raise AssertionError("expected request error")
    except RuntimeError as exc:
        assert "Resend request failed" in str(exc)

    monkeypatch.setattr(
        activities_email.httpx,
        "post",
        lambda *_, **__: _FakeResponse(500, text="boom"),
    )
    try:
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key="rk_test",
            resend_from_email="from@example.com",
        )
        raise AssertionError("expected API status error")
    except RuntimeError as exc:
        assert "Resend API returned 500" in str(exc)

    monkeypatch.setattr(
        activities_email.httpx,
        "post",
        lambda *_, **__: _FakeResponse(200, payload=ValueError("bad json")),
    )
    assert (
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key="rk_test",
            resend_from_email="from@example.com",
        )
        is None
    )

    monkeypatch.setattr(
        activities_email.httpx,
        "post",
        lambda *_, **__: _FakeResponse(200, payload={"id": "msg_1"}),
    )
    assert (
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key="rk_test",
            resend_from_email="from@example.com",
        )
        == "msg_1"
    )

    captured_headers: dict[str, str] = {}

    def _capture_post(*_: Any, **kwargs: Any) -> _FakeResponse:
        captured_headers.update(kwargs.get("headers") or {})
        return _FakeResponse(200, payload={"id": "msg_2"})

    monkeypatch.setattr(activities_email.httpx, "post", _capture_post)
    assert (
        activities_email.send_with_resend(
            to_email="to@example.com",
            subject="S",
            text_body="B",
            resend_api_key="rk_test",
            resend_from_email="from@example.com",
            idempotency_key="delivery-retry:delivery-1:attempt-1",
        )
        == "msg_2"
    )
    assert captured_headers["Idempotency-Key"] == "delivery-retry:delivery-1:attempt-1"


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ANN001
        base = cls(2026, 3, 1, 1, 30, tzinfo=UTC)
        if tz is None:
            return base.replace(tzinfo=None)
        return base.astimezone(tz)


def test_timing_helpers_and_activity(monkeypatch: Any) -> None:
    assert activities_timing._coerce_int(True, fallback=9) == 9
    assert activities_timing._coerce_int(" +42 ", fallback=0) == 42
    assert activities_timing._coerce_int("-7", fallback=0) == -7
    assert activities_timing._coerce_int("x", fallback=3) == 3

    local_tz, label = activities_timing._resolve_local_timezone(
        timezone_name="Invalid/Zone",
        offset_minutes=480,
    )
    assert label == "offset:480"
    assert activities_timing._resolve_local_digest_date(
        digest_date="2026-03-05",
        timezone_name="UTC",
        offset_minutes=0,
    ) == date(2026, 3, 5)

    start_utc, end_utc = activities_timing._build_local_day_window_utc(
        local_day=date(2026, 3, 5),
        timezone_name=None,
        offset_minutes=480,
    )
    assert start_utc.tzinfo == UTC
    assert end_utc.tzinfo == UTC
    assert end_utc > start_utc

    monkeypatch.setattr(activities_timing, "datetime", _FixedDatetime)

    payload_wait = asyncio.run(
        activities_timing.resolve_daily_digest_timing_activity(
            {
                "run_once": False,
                "timezone_name": "UTC",
                "timezone_offset_minutes": 0,
                "local_hour": 9,
            }
        )
    )
    assert payload_wait["ok"] is True
    assert payload_wait["wait_before_run_seconds"] > 0
    assert payload_wait["wait_after_run_seconds"] >= 60

    payload_no_wait = asyncio.run(
        activities_timing.resolve_daily_digest_timing_activity(
            {
                "run_once": True,
                "timezone_name": "UTC",
                "timezone_offset_minutes": 0,
                "local_hour": 9,
            }
        )
    )
    assert payload_no_wait["wait_before_run_seconds"] == 0
    assert payload_no_wait["timezone_name"] == "UTC"
    assert local_tz.utcoffset(datetime.now(UTC)) is not None


def test_health_http_probe_and_provider_activity(monkeypatch: Any) -> None:
    assert activities_health._classify_http_error_kind(status_code=401, error_message="x") == "auth"
    assert (
        activities_health._classify_http_error_kind(status_code=429, error_message="x")
        == "rate_limit"
    )
    assert (
        activities_health._classify_http_error_kind(status_code=500, error_message="x")
        == "transient"
    )

    monkeypatch.setattr(
        activities_health,
        "urlopen",
        lambda request, timeout=8: _FakeHTTPReadResponse(200, b"ok"),
    )
    ok_payload = activities_health._http_probe(url="https://example.com?q=1")
    assert ok_payload["status"] == "ok"

    def _raise_http_error(request: Any, timeout: int = 8) -> Any:
        fp = io.BytesIO(b"too many requests")
        raise HTTPError(request.full_url, 429, "rate limit", {}, fp)

    monkeypatch.setattr(activities_health, "urlopen", _raise_http_error)
    warn_payload = activities_health._http_probe(url="https://example.com?token=secret")
    assert warn_payload["status"] == "warn"
    assert warn_payload["error_kind"] == "rate_limit"
    assert "%2A%2A%2AREDACTED%2A%2A%2A" in warn_payload["payload_json"]["url"]

    monkeypatch.setattr(
        activities_health,
        "urlopen",
        lambda request, timeout=8: (_ for _ in ()).throw(URLError("dns failed")),
    )
    fail_payload = activities_health._http_probe(url="https://example.com")
    assert fail_payload["status"] == "fail"
    assert fail_payload["error_kind"] == "transient"

    conn = _DummyConn()
    activities_health._record_provider_health_check(
        conn,
        check_kind="rsshub",
        status="ok",
        error_kind=None,
        message="ok",
        payload_json={"k": "v"},
    )
    assert conn.calls
    assert conn.calls[0]["params"]["check_kind"] == "rsshub"

    recorded: list[dict[str, Any]] = []

    def _record_stub(_conn: Any, **kwargs: Any) -> None:
        recorded.append(kwargs)

    monkeypatch.setattr(activities_health, "_record_provider_health_check", _record_stub)
    monkeypatch.setattr(activities_health, "PostgresBusinessStore", _DummyPGStore)
    monkeypatch.setattr(
        activities_health.Settings,
        "from_env",
        staticmethod(
            lambda: SimpleNamespace(
                database_url="postgresql://example.invalid/db",
                rsshub_base_url="https://rsshub.example.com",
                youtube_api_key="yt_key",
                gemini_api_key="gm_key",
                resend_api_key="rs_key",
                resend_from_email="digest@example.com",
            )
        ),
    )
    monkeypatch.setattr(
        activities_health,
        "_http_probe",
        lambda **_: {"status": "ok", "error_kind": None, "message": "ok", "payload_json": {}},
    )

    result = asyncio.run(activities_health.provider_canary_activity({"timeout_seconds": "5"}))
    assert result["ok"] is True
    assert result["summary"]["ok"] == 4
    assert len(recorded) == 4
