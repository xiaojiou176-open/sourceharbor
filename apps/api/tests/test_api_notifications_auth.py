from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette import status

from apps.api.app.db import get_db
from apps.api.app.routers import notifications as notifications_router
from apps.api.app.routers.notifications import reports_router, router


def _build_notifications_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.include_router(reports_router)

    def _fake_db():
        yield SimpleNamespace()

    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


def test_notifications_write_endpoints_require_write_access(monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    monkeypatch.setattr(
        notifications_router,
        "update_notification_config",
        lambda *args, **kwargs: SimpleNamespace(
            enabled=True,
            to_email="ops@example.com",
            daily_digest_enabled=True,
            daily_digest_hour_utc=9,
            failure_alert_enabled=True,
            category_rules={},
            created_at=now,
            updated_at=now,
        ),
    )
    monkeypatch.setattr(
        notifications_router,
        "send_daily_report_notification",
        lambda *args, **kwargs: SimpleNamespace(
            id="00000000-0000-4000-8000-000000000001",
            status="sent",
            payload_json={"digest_date": "2026-02-20"},
            recipient_email="ops@example.com",
            subject="Daily",
            error_message=None,
            sent_at=now,
            created_at=now,
        ),
    )

    with _build_notifications_client() as client:
        put_payload = {
            "enabled": True,
            "to_email": "ops@example.com",
            "daily_digest_enabled": True,
            "daily_digest_hour_utc": 9,
            "failure_alert_enabled": True,
        }
        unauth = client.put("/api/v1/notifications/config", json=put_payload)
        forbidden = client.put(
            "/api/v1/notifications/config",
            json=put_payload,
            headers={"Authorization": "Bearer wrong-token"},
        )
        authorized = client.put(
            "/api/v1/notifications/config",
            json=put_payload,
            headers={"X-API-Key": "unit-test-token"},
        )

        report_forbidden = client.post(
            "/api/v1/reports/daily/send",
            json={"date": date.today().isoformat()},
            headers={"X-API-Key": "wrong-token"},
        )
        report_authorized = client.post(
            "/api/v1/reports/daily/send",
            json={"date": date.today().isoformat()},
            headers={"Authorization": "Bearer unit-test-token"},
        )

    assert unauth.status_code == status.HTTP_401_UNAUTHORIZED
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert authorized.status_code == status.HTTP_200_OK
    assert report_forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert report_authorized.status_code == status.HTTP_200_OK


def test_notifications_route_contract_fields_are_owned_by_api(monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    captured: dict[str, object] = {}

    def _fake_update_notification_config(*_args, **kwargs):
        captured["config_kwargs"] = kwargs
        return SimpleNamespace(
            enabled=kwargs["enabled"],
            to_email=kwargs["to_email"],
            daily_digest_enabled=kwargs["daily_digest_enabled"],
            daily_digest_hour_utc=kwargs["daily_digest_hour_utc"],
            failure_alert_enabled=kwargs["failure_alert_enabled"],
            category_rules=kwargs["category_rules"] or {},
            created_at=now,
            updated_at=now,
        )

    def _fake_send_test_email(*_args, **kwargs):
        captured["test_kwargs"] = kwargs
        return SimpleNamespace(
            id="00000000-0000-4000-8000-000000000002",
            status="sent",
            provider_message_id="provider-1",
            error_message=None,
            recipient_email=kwargs["to_email"] or "ops@example.com",
            subject=kwargs["subject"] or "Test",
            sent_at=now,
            created_at=now,
        )

    monkeypatch.setattr(
        notifications_router,
        "update_notification_config",
        _fake_update_notification_config,
    )
    monkeypatch.setattr(
        notifications_router,
        "send_test_email",
        _fake_send_test_email,
    )

    with _build_notifications_client() as client:
        config_response = client.put(
            "/api/v1/notifications/config",
            json={
                "enabled": True,
                "to_email": "ops@example.com",
                "daily_digest_enabled": True,
                "daily_digest_hour_utc": 9,
                "failure_alert_enabled": True,
                "category_rules": {"ops": {"enabled": True}},
            },
            headers={"Authorization": "Bearer unit-test-token"},
        )
        test_send_response = client.post(
            "/api/v1/notifications/test",
            json={
                "to_email": "ops@example.com",
                "subject": "API contract test",
                "body": "route contract assertion",
            },
            headers={"X-API-Key": "unit-test-token"},
        )

    assert config_response.status_code == status.HTTP_200_OK
    assert config_response.json()["to_email"] == "ops@example.com"
    assert config_response.json()["daily_digest_enabled"] is True
    assert config_response.json()["daily_digest_hour_utc"] == 9
    assert config_response.json()["category_rules"] == {"ops": {"enabled": True}}
    assert captured["config_kwargs"] == {
        "enabled": True,
        "to_email": "ops@example.com",
        "daily_digest_enabled": True,
        "daily_digest_hour_utc": 9,
        "failure_alert_enabled": True,
        "category_rules": {"ops": {"enabled": True}},
    }

    assert test_send_response.status_code == status.HTTP_200_OK
    assert test_send_response.json()["status"] == "sent"
    assert test_send_response.json()["recipient_email"] == "ops@example.com"
    assert test_send_response.json()["subject"] == "API contract test"
    assert captured["test_kwargs"] == {
        "to_email": "ops@example.com",
        "subject": "API contract test",
        "body": "route contract assertion",
    }


def test_notifications_get_config_normalizes_non_dict_category_rules(monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(
        notifications_router,
        "get_notification_config",
        lambda *_args, **_kwargs: SimpleNamespace(
            enabled=True,
            to_email="ops@example.com",
            daily_digest_enabled=True,
            daily_digest_hour_utc=8,
            failure_alert_enabled=True,
            category_rules="not-a-dict",
            created_at=now,
            updated_at=now,
        ),
    )

    with _build_notifications_client() as client:
        response = client.get("/api/v1/notifications/config")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["category_rules"] == {}


def test_notifications_test_send_maps_value_and_runtime_errors(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")

    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("bad input")

    monkeypatch.setattr(notifications_router, "send_test_email", _raise_value_error)
    with _build_notifications_client() as client:
        bad_request = client.post(
            "/api/v1/notifications/test",
            json={"to_email": "ops@example.com"},
            headers={"X-API-Key": "unit-test-token"},
        )

    assert bad_request.status_code == status.HTTP_400_BAD_REQUEST

    def _raise_runtime_error(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(notifications_router, "send_test_email", _raise_runtime_error)
    with _build_notifications_client() as client:
        service_unavailable = client.post(
            "/api/v1/notifications/test",
            json={"to_email": "ops@example.com"},
            headers={"X-API-Key": "unit-test-token"},
        )

    assert service_unavailable.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_daily_report_send_uses_payload_digest_date_and_invalid_falls_back(monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    responses = [
        SimpleNamespace(
            id="00000000-0000-4000-8000-000000000011",
            status="sent",
            payload_json={"digest_date": "2026-02-20"},
            recipient_email="ops@example.com",
            subject="Daily",
            error_message=None,
            sent_at=now,
            created_at=now,
        ),
        SimpleNamespace(
            id="00000000-0000-4000-8000-000000000012",
            status="failed",
            payload_json={"digest_date": "invalid-date"},
            recipient_email="ops@example.com",
            subject="Daily",
            error_message="boom",
            sent_at=None,
            created_at=now,
        ),
    ]

    def _fake_send_daily(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(notifications_router, "send_daily_report_notification", _fake_send_daily)
    with _build_notifications_client() as client:
        from_payload = client.post(
            "/api/v1/reports/daily/send",
            json={},
            headers={"Authorization": "Bearer unit-test-token"},
        )
        fallback_today = client.post(
            "/api/v1/reports/daily/send",
            json={},
            headers={"Authorization": "Bearer unit-test-token"},
        )

    assert from_payload.status_code == status.HTTP_200_OK
    assert from_payload.json()["date"] == "2026-02-20"
    assert fallback_today.status_code == status.HTTP_200_OK
    assert fallback_today.json()["date"] == date.today().isoformat()
    assert fallback_today.json()["sent"] is False


def test_daily_report_and_category_send_map_value_and_runtime_errors(monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")

    def _daily_value_error(*_args, **_kwargs):
        raise ValueError("bad date")

    monkeypatch.setattr(notifications_router, "send_daily_report_notification", _daily_value_error)
    with _build_notifications_client() as client:
        daily_bad = client.post(
            "/api/v1/reports/daily/send",
            json={},
            headers={"X-API-Key": "unit-test-token"},
        )
    assert daily_bad.status_code == status.HTTP_400_BAD_REQUEST

    def _daily_runtime_error(*_args, **_kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        notifications_router, "send_daily_report_notification", _daily_runtime_error
    )
    with _build_notifications_client() as client:
        daily_unavailable = client.post(
            "/api/v1/reports/daily/send",
            json={},
            headers={"X-API-Key": "unit-test-token"},
        )
    assert daily_unavailable.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def _category_value_error(*_args, **_kwargs):
        raise ValueError("bad category")

    monkeypatch.setattr(notifications_router, "send_category_digest", _category_value_error)
    with _build_notifications_client() as client:
        category_bad = client.post(
            "/api/v1/notifications/category/send",
            json={"category": "ops", "body": "digest"},
            headers={"X-API-Key": "unit-test-token"},
        )
    assert category_bad.status_code == status.HTTP_400_BAD_REQUEST

    def _category_runtime_error(*_args, **_kwargs):
        raise RuntimeError("send failed")

    monkeypatch.setattr(notifications_router, "send_category_digest", _category_runtime_error)
    with _build_notifications_client() as client:
        category_unavailable = client.post(
            "/api/v1/notifications/category/send",
            json={"category": "ops", "body": "digest"},
            headers={"X-API-Key": "unit-test-token"},
        )
    assert category_unavailable.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_category_send_success_response_contract(monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    monkeypatch.setattr(
        notifications_router,
        "send_category_digest",
        lambda *_args, **_kwargs: SimpleNamespace(
            id="00000000-0000-4000-8000-000000000013",
            status="sent",
            provider_message_id="provider-13",
            error_message=None,
            recipient_email="ops@example.com",
            subject="Category digest",
            sent_at=now,
            created_at=now,
        ),
    )

    with _build_notifications_client() as client:
        response = client.post(
            "/api/v1/notifications/category/send",
            json={"category": "ops", "body": "digest"},
            headers={"Authorization": "Bearer unit-test-token"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "sent"
    assert response.json()["recipient_email"] == "ops@example.com"
