from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from apps.api.app.services import notifications


def _config_with_rules(category_rules: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        to_email="demo@example.com",
        daily_digest_enabled=True,
        daily_digest_hour_utc=9,
        failure_alert_enabled=True,
        category_rules=category_rules,
    )


def test_send_category_digest_respects_rule_cadence_and_dispatch_key(monkeypatch) -> None:
    config = _config_with_rules(
        {
            "default_rule": {"enabled": True, "cadence": "daily", "hour": 7},
            "category_rules": {"tech": {"enabled": True, "cadence": "instant", "min_priority": 50}},
        }
    )

    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)
    captured: dict[str, object] = {}

    def fake_dispatch_email(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(
            id="delivery-1",
            status="sent",
            provider_message_id="provider-1",
            error_message=None,
            recipient_email=kwargs["recipient_email"],
            subject=kwargs["subject"],
            sent_at=None,
            created_at=None,
        )

    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch_email)

    row = notifications.send_category_digest(
        None,  # type: ignore[arg-type]
        category="tech",
        digest_markdown="digest body",
        priority=60,
        dispatch_key="tech:2026-02-23",
    )

    assert row.status == "sent"
    assert captured["skip_reason"] is None
    assert captured["dispatch_key"] == "tech:2026-02-23"


def test_hourly_cadence_fires_at_matching_hour(monkeypatch) -> None:
    config = _config_with_rules(
        {"category_rules": {"tech": {"enabled": True, "cadence": "hourly", "interval_hours": 2}}}
    )
    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)
    captured: dict[str, object] = {}

    def fake_dispatch_email(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(
            id="delivery-h",
            status="sent",
            provider_message_id=None,
            error_message=None,
            recipient_email=kwargs["recipient_email"],
            subject=kwargs["subject"],
            sent_at=None,
            created_at=None,
        )

    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch_email)
    monkeypatch.setattr(
        notifications,
        "_utc_now",
        lambda: datetime(2026, 2, 23, 6, 30, tzinfo=UTC),
    )

    row = notifications.send_category_digest(
        None,  # type: ignore[arg-type]
        category="tech",
        digest_markdown="hourly digest",
        dispatch_key="tech:hourly:2026-02-23T06",
    )

    assert row.status == "sent"
    assert captured["skip_reason"] is None


def test_hourly_cadence_skips_at_non_matching_hour(monkeypatch) -> None:
    config = _config_with_rules(
        {"category_rules": {"tech": {"enabled": True, "cadence": "hourly", "interval_hours": 2}}}
    )
    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)
    captured: dict[str, object] = {}

    def fake_dispatch_email(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(status="skipped")

    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch_email)
    monkeypatch.setattr(
        notifications,
        "_utc_now",
        lambda: datetime(2026, 2, 23, 7, 0, tzinfo=UTC),
    )

    notifications.send_category_digest(
        None,  # type: ignore[arg-type]
        category="tech",
        digest_markdown="should skip",
        dispatch_key="tech:hourly:2026-02-23T07",
    )

    assert str(captured.get("skip_reason", "")).startswith("hourly cadence mismatch")


def test_send_category_digest_applies_min_priority_skip(monkeypatch) -> None:
    config = _config_with_rules(
        {
            "category_rules": {
                "ops": {"enabled": True, "cadence": "instant", "min_priority": 90},
            }
        }
    )
    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)
    captured: dict[str, object] = {}

    def fake_dispatch_email(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(status="skipped")

    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch_email)

    notifications.send_category_digest(
        None,  # type: ignore[arg-type]
        category="ops",
        digest_markdown="digest body",
        priority=20,
        dispatch_key="ops:2026-02-23",
    )

    assert str(captured["skip_reason"]).startswith("priority below threshold")


class _DispatchDB:
    def __init__(self, *, fail_first_commit: bool = False) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshes = 0
        self.fail_first_commit = fail_first_commit

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1
        if self.fail_first_commit and self.commits == 1:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, _obj: object) -> None:
        self.refreshes += 1


def test_send_test_email_requires_recipient(monkeypatch) -> None:
    config = _config_with_rules({})
    config.to_email = None
    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)

    with pytest.raises(ValueError, match="recipient email"):
        notifications.send_test_email(None)  # type: ignore[arg-type]


def test_send_failure_alert_sets_skip_reason_when_disabled(monkeypatch) -> None:
    config = _config_with_rules({})
    config.enabled = False
    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)

    captured: dict[str, object] = {}

    def fake_dispatch(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(status="skipped")

    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch)

    notifications.send_failure_alert(None, title="job failed", details="stack trace")  # type: ignore[arg-type]

    assert captured["skip_reason"] == "notification config is disabled"


def test_send_daily_digest_with_explicit_date_and_disabled_flag(monkeypatch) -> None:
    config = _config_with_rules({})
    config.daily_digest_enabled = False
    monkeypatch.setattr(notifications, "get_notification_config", lambda db: config)

    captured: dict[str, object] = {}

    def fake_dispatch(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(status="skipped")

    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch)

    notifications.send_daily_digest(
        None,  # type: ignore[arg-type]
        digest_markdown="digest",
        digest_date=date(2026, 2, 23),
        subject="custom subject",
    )

    assert captured["subject"] == "custom subject"
    assert captured["payload"] == {"digest_date": "2026-02-23"}
    assert captured["skip_reason"] == "daily digest is disabled"


def test_send_daily_report_notification_uses_default_body(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_send_daily_digest(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(status="sent")

    monkeypatch.setattr(notifications, "send_daily_digest", fake_send_daily_digest)

    notifications.send_daily_report_notification(
        None,  # type: ignore[arg-type]
        report_date=date(2026, 2, 23),
        to_email="ops@example.com",
    )

    assert captured["digest_markdown"].endswith("2026-02-23")
    assert captured["digest_date"] == date(2026, 2, 23)
    assert captured["to_email"] == "ops@example.com"


def test_dispatch_email_returns_existing_by_dispatch_key(monkeypatch) -> None:
    existing = SimpleNamespace(id="existing")
    monkeypatch.setattr(
        notifications, "_get_delivery_by_dispatch_key", lambda db, kind, dispatch_key: existing
    )

    db = _DispatchDB()
    result = notifications._dispatch_email(
        db,
        kind="daily_digest",
        recipient_email="demo@example.com",
        subject="digest",
        text_body="hello",
        payload={"k": "v"},
        skip_reason=None,
        dispatch_key="k1",
    )

    assert result is existing
    assert not db.added


def test_dispatch_email_marks_skipped_when_env_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications,
        "settings",
        SimpleNamespace(
            notification_enabled=False,
            resend_api_key="key",
            resend_from_email="noreply@example.com",
        ),
    )

    db = _DispatchDB()
    result = notifications._dispatch_email(
        db,
        kind="daily_digest",
        recipient_email="demo@example.com",
        subject="digest",
        text_body="hello",
        payload={"k": "v"},
        skip_reason=None,
    )

    assert result.status == "skipped"
    assert result.error_message == "notification is disabled by environment"


def test_dispatch_email_runtime_error_marks_failed(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications,
        "settings",
        SimpleNamespace(
            notification_enabled=True,
            resend_api_key="key",
            resend_from_email="noreply@example.com",
        ),
    )
    monkeypatch.setattr(
        notifications,
        "_send_with_resend",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    db = _DispatchDB()
    with pytest.raises(RuntimeError, match="boom"):
        notifications._dispatch_email(
            db,
            kind="daily_digest",
            recipient_email="demo@example.com",
            subject="digest",
            text_body="hello",
            payload={"k": "v"},
            skip_reason=None,
        )

    delivery = db.added[0]
    assert delivery.status == "failed"
    assert delivery.error_message == "boom"


def test_dispatch_email_integrityerror_returns_existing_video_digest(monkeypatch) -> None:
    job_id = uuid.uuid4()
    existing = SimpleNamespace(id="existing-video")
    monkeypatch.setattr(notifications, "_get_video_digest_delivery", lambda db, job_id: existing)

    db = _DispatchDB(fail_first_commit=True)
    result = notifications._dispatch_email(
        db,
        kind="video_digest",
        recipient_email="demo@example.com",
        subject="digest",
        text_body="hello",
        payload={"job_id": str(job_id)},
        job_id=job_id,
        skip_reason=None,
    )

    assert result is existing
    assert db.rollbacks == 1


def test_send_with_resend_validates_required_config() -> None:
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        notifications._send_with_resend(
            to_email="a@example.com",
            subject="s",
            text_body="b",
            resend_api_key="  ",
            resend_from_email="noreply@example.com",
        )

    with pytest.raises(RuntimeError, match="RESEND_FROM_EMAIL"):
        notifications._send_with_resend(
            to_email="a@example.com",
            subject="s",
            text_body="b",
            resend_api_key="key",
            resend_from_email=" ",
        )


def test_send_with_resend_handles_request_and_response_errors(monkeypatch) -> None:
    def raise_request_error(*args, **kwargs):
        del args, kwargs
        request = httpx.Request("POST", notifications.RESEND_API_URL)
        raise httpx.RequestError("network down", request=request)

    monkeypatch.setattr(httpx, "post", raise_request_error)

    with pytest.raises(RuntimeError, match="Resend request failed"):
        notifications._send_with_resend(
            to_email="a@example.com",
            subject="s",
            text_body="b",
            resend_api_key="key",
            resend_from_email="noreply@example.com",
        )

    class _BadResponse:
        status_code = 500
        text = "error"

        def json(self):
            return {}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _BadResponse())

    with pytest.raises(RuntimeError, match="Resend API returned 500"):
        notifications._send_with_resend(
            to_email="a@example.com",
            subject="s",
            text_body="b",
            resend_api_key="key",
            resend_from_email="noreply@example.com",
        )


def test_send_with_resend_success_and_non_json(monkeypatch) -> None:
    class _JsonFailResponse:
        status_code = 200
        text = "ok"

        def json(self):
            raise ValueError("invalid json")

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _JsonFailResponse())
    assert (
        notifications._send_with_resend(
            to_email="a@example.com",
            subject="s",
            text_body="b",
            resend_api_key="key",
            resend_from_email="noreply@example.com",
        )
        is None
    )

    class _OkResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {"id": "msg-1"}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _OkResponse())
    assert (
        notifications._send_with_resend(
            to_email="a@example.com",
            subject="s",
            text_body="b",
            resend_api_key="key",
            resend_from_email="noreply@example.com",
        )
        == "msg-1"
    )


def test_evaluate_category_rule_weekly_and_unsupported() -> None:
    config = _config_with_rules(
        {"category_rules": {"ops": {"cadence": "weekly", "weekday": 1, "hour": 8}}}
    )
    now = datetime(2026, 2, 24, 8, 0, tzinfo=UTC)
    assert (
        notifications._evaluate_category_rule(
            config=config, category="ops", now_utc=now, priority=None
        )
        is None
    )

    mismatch = datetime(2026, 2, 25, 8, 0, tzinfo=UTC)
    assert "weekly cadence mismatch weekday" in str(
        notifications._evaluate_category_rule(
            config=config, category="ops", now_utc=mismatch, priority=None
        )
    )

    config_unknown = _config_with_rules({"category_rules": {"ops": {"cadence": "monthly"}}})
    assert notifications._evaluate_category_rule(
        config=config_unknown, category="ops", now_utc=now, priority=None
    ) == ("unsupported cadence: monthly")


def test_get_and_update_notification_config_cover_default_and_update_paths() -> None:
    class _FakeDB:
        def __init__(self) -> None:
            self.scalar_value = None
            self.added: list[object] = []
            self.commits = 0
            self.refreshed: list[object] = []

        def scalar(self, _stmt):
            return self.scalar_value

        def add(self, item):
            self.added.append(item)
            self.scalar_value = item

        def commit(self):
            self.commits += 1

        def rollback(self):
            return None

        def refresh(self, item):
            self.refreshed.append(item)

    db = _FakeDB()
    config = notifications.get_notification_config(db)  # type: ignore[arg-type]
    assert config.singleton_key == 1
    assert db.added[-1] is config

    updated = notifications.update_notification_config(  # type: ignore[arg-type]
        db,
        enabled=False,
        to_email="  ops@example.com  ",
        daily_digest_enabled=True,
        daily_digest_hour_utc=6,
        failure_alert_enabled=False,
        category_rules={"tech": {"enabled": True}},
    )
    assert updated.enabled is False
    assert updated.to_email == "ops@example.com"
    assert updated.daily_digest_hour_utc == 6
    assert updated.category_rules == {"tech": {"enabled": True}}


def test_notification_helpers_cover_normalization_and_skip_reasons(monkeypatch) -> None:
    config = _config_with_rules(
        {
            "category_rules": {"tech": {"enabled": False}},
            "default_rule": {"cadence": "hourly", "interval_hours": "3"},
        }
    )
    assert notifications._normalize_email("  a@example.com ") == "a@example.com"
    assert notifications._normalize_email(" ") is None
    assert notifications._normalize_dispatch_key(" key ") == "key"
    assert notifications._normalize_dispatch_key("") is None
    assert notifications._coerce_int("4") == 4
    assert notifications._coerce_int(3.5) == 3
    assert notifications._coerce_int("bad", default=9) == 9
    assert (
        notifications._resolve_recipient_email(config, " override@example.com ")
        == "override@example.com"
    )
    assert notifications._resolve_recipient_email(config, None) == "demo@example.com"
    assert notifications._extract_notification_rules(config, "other") == {
        "cadence": "hourly",
        "interval_hours": "3",
    }
    assert (
        notifications._evaluate_category_rule(
            config=config,
            category="tech",
            now_utc=datetime(2026, 3, 8, 9, tzinfo=UTC),
            priority=5,
        )
        == "category rule disabled: tech"
    )

    captured: dict[str, object] = {}

    def fake_dispatch(db, **kwargs):
        del db
        captured.update(kwargs)
        return SimpleNamespace(status="skipped", recipient_email=kwargs["recipient_email"])

    disabled_config = SimpleNamespace(
        enabled=False,
        to_email="ops@example.com",
        daily_digest_enabled=False,
        failure_alert_enabled=False,
        category_rules={},
    )
    monkeypatch.setattr(notifications, "get_notification_config", lambda _db: disabled_config)
    monkeypatch.setattr(notifications, "_dispatch_email", fake_dispatch)

    notifications.send_failure_alert(None, title="Job failed", details="boom")  # type: ignore[arg-type]
    assert captured["skip_reason"] == "notification config is disabled"

    notifications.send_video_digest(None, job_id=uuid.uuid4(), digest_markdown="# hi")  # type: ignore[arg-type]
    assert captured["kind"] == "video_digest"
    assert captured["skip_reason"] == "notification config is disabled"
