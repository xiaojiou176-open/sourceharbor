from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import DBAPIError

from apps.api.app.services.health import HealthService


class _RowsResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _RowsResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeDB:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _statement: Any, _params: dict[str, Any] | None = None) -> _RowsResult:
        self.calls += 1
        if self.calls == 1:
            return _RowsResult(
                [
                    {"check_kind": "rsshub", "status": "ok", "count": 3},
                    {"check_kind": "rsshub", "status": "warn", "count": 1},
                    {"check_kind": "gemini", "status": "fail", "count": 2},
                ]
            )
        return _RowsResult(
            [
                {
                    "check_kind": "rsshub",
                    "status": "ok",
                    "checked_at": datetime(2026, 2, 22, 10, 0, tzinfo=UTC),
                    "error_kind": None,
                    "message": "ok",
                },
                {
                    "check_kind": "gemini",
                    "status": "fail",
                    "checked_at": datetime(2026, 2, 22, 10, 5, tzinfo=UTC),
                    "error_kind": "transient",
                    "message": "timeout",
                },
            ]
        )

    def rollback(self) -> None:
        return None


class _FirstQueryFailsDB:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def execute(self, _statement: Any, _params: dict[str, Any] | None = None) -> _RowsResult:
        raise DBAPIError.instance("SELECT", {}, Exception("boom"), Exception)

    def rollback(self) -> None:
        self.rollback_calls += 1


class _LatestQueryFailsDB:
    def __init__(self) -> None:
        self.calls = 0
        self.rollback_calls = 0

    def execute(self, _statement: Any, _params: dict[str, Any] | None = None) -> _RowsResult:
        self.calls += 1
        if self.calls == 1:
            return _RowsResult(
                [
                    {"check_kind": "rsshub", "status": "ok", "count": 2},
                    {"check_kind": "unknown", "status": "ok", "count": 7},
                    {"check_kind": "gemini", "status": "unexpected", "count": 9},
                ]
            )
        raise DBAPIError.instance("SELECT", {}, Exception("late boom"), Exception)

    def rollback(self) -> None:
        self.rollback_calls += 1


def test_get_provider_health_aggregates_rows() -> None:
    service = HealthService(_FakeDB())  # type: ignore[arg-type]

    payload = service.get_provider_health(window_hours=24)

    assert payload["window_hours"] == 24
    providers = {item["provider"]: item for item in payload["providers"]}
    assert providers["rsshub"]["ok"] == 3
    assert providers["rsshub"]["warn"] == 1
    assert providers["rsshub"]["fail"] == 0
    assert providers["rsshub"]["last_status"] == "ok"
    assert providers["gemini"]["fail"] == 2
    assert providers["gemini"]["last_error_kind"] == "transient"
    assert providers["youtube_data_api"]["ok"] == 0


def test_get_provider_health_rolls_back_and_returns_defaults_when_aggregate_query_fails() -> None:
    db = _FirstQueryFailsDB()
    service = HealthService(db)  # type: ignore[arg-type]

    payload = service.get_provider_health(window_hours=0)

    assert db.rollback_calls == 1
    assert payload["window_hours"] == 1
    providers = {item["provider"]: item for item in payload["providers"]}
    assert providers["rsshub"]["ok"] == 0
    assert providers["gemini"]["fail"] == 0
    assert providers["resend"]["last_status"] is None


def test_get_provider_health_keeps_aggregate_counts_when_latest_query_fails() -> None:
    db = _LatestQueryFailsDB()
    service = HealthService(db)  # type: ignore[arg-type]

    payload = service.get_provider_health(window_hours=2)

    assert db.rollback_calls == 1
    providers = {item["provider"]: item for item in payload["providers"]}
    assert providers["rsshub"]["ok"] == 2
    assert providers["rsshub"]["last_status"] is None
    assert providers["gemini"]["fail"] == 0
