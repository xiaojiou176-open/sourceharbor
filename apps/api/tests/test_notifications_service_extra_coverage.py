from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from apps.api.app.services import notifications


class _ConfigSession:
    def __init__(self, *, fail_first_commit: bool = False) -> None:
        self.fail_first_commit = fail_first_commit
        self.scalar_values: list[object | None] = []
        self.scalar_calls = 0
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed: list[object] = []

    def scalar(self, _stmt: object) -> object | None:
        self.scalar_calls += 1
        if self.scalar_values:
            return self.scalar_values.pop(0)
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1
        if self.fail_first_commit and self.commits == 1:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, obj: object) -> None:
        self.refreshed.append(obj)


class _DispatchSession:
    def __init__(self, *, fail_first_commit: bool = False) -> None:
        self.fail_first_commit = fail_first_commit
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed: list[object] = []
        self.scalar_return: object | None = None
        self.scalar_calls = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1
        if self.fail_first_commit and self.commits == 1:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, obj: object) -> None:
        self.refreshed.append(obj)

    def scalar(self, _stmt: object) -> object | None:
        self.scalar_calls += 1
        return self.scalar_return


def test_get_notification_config_returns_existing_without_mutation() -> None:
    existing = SimpleNamespace(singleton_key=1)
    db = _ConfigSession()
    db.scalar_values = [existing]

    result = notifications.get_notification_config(db)  # type: ignore[arg-type]

    assert result is existing
    assert db.added == []
    assert db.commits == 0
    assert db.refreshed == []


def test_get_notification_config_creates_and_handles_integrity_race() -> None:
    db_created = _ConfigSession()
    db_created.scalar_values = [None]

    created = notifications.get_notification_config(db_created)  # type: ignore[arg-type]
    assert created.singleton_key == 1
    assert db_created.commits == 1
    assert len(db_created.added) == 1
    assert db_created.refreshed == [created]

    existing = SimpleNamespace(singleton_key=1, enabled=True)
    db_race = _ConfigSession(fail_first_commit=True)
    db_race.scalar_values = [None, existing]
    raced = notifications.get_notification_config(db_race)  # type: ignore[arg-type]
    assert raced is existing
    assert db_race.rollbacks == 1

    db_error = _ConfigSession(fail_first_commit=True)
    db_error.scalar_values = [None, None]
    with pytest.raises(IntegrityError):
        notifications.get_notification_config(db_error)  # type: ignore[arg-type]


def test_update_config_send_video_digest_and_send_failure_alert_disabled(monkeypatch) -> None:
    config = SimpleNamespace(
        enabled=True,
        to_email="  user@example.com ",
        daily_digest_enabled=True,
        daily_digest_hour_utc=8,
        failure_alert_enabled=True,
        category_rules={},
    )
    db = _ConfigSession()
    monkeypatch.setattr(notifications, "get_notification_config", lambda _db: config)

    updated = notifications.update_notification_config(
        db,  # type: ignore[arg-type]
        enabled=False,
        to_email="  ",
        daily_digest_enabled=False,
        daily_digest_hour_utc=6,
        failure_alert_enabled=False,
        category_rules=["invalid"],  # type: ignore[arg-type]
    )
    assert updated is config
    assert config.enabled is False
    assert config.to_email is None
    assert config.category_rules == {}
    assert db.commits == 1
    assert db.refreshed == [config]

    captured: dict[str, Any] = {}

    def _fake_dispatch(_db: object, **kwargs: Any) -> SimpleNamespace:
        captured.clear()
        captured.update(kwargs)
        return SimpleNamespace(status="queued")

    config.enabled = False
    config.to_email = "ops@example.com"
    config.failure_alert_enabled = False
    monkeypatch.setattr(notifications, "_dispatch_email", _fake_dispatch)

    job_id = uuid.uuid4()
    notifications.send_video_digest(
        None,  # type: ignore[arg-type]
        job_id=job_id,
        digest_markdown="digest",
    )
    assert captured["kind"] == "video_digest"
    assert captured["skip_reason"] == "notification config is disabled"
    assert captured["payload"] == {"job_id": str(job_id)}

    notifications.send_failure_alert(
        None,  # type: ignore[arg-type]
        title="job failed",
        details="traceback",
    )
    assert captured["kind"] == "failure_alert"
    assert captured["skip_reason"] == "notification config is disabled"


def test_dispatch_email_integrityerror_with_dispatch_key_returns_existing(monkeypatch) -> None:
    db = _DispatchSession(fail_first_commit=True)
    existing = SimpleNamespace(id="delivery-existing")
    calls = {"count": 0}

    def _fake_get_by_key(_db: object, *, kind: str, dispatch_key: str) -> object | None:
        del _db, kind, dispatch_key
        calls["count"] += 1
        return existing if calls["count"] >= 2 else None

    monkeypatch.setattr(notifications, "_get_delivery_by_dispatch_key", _fake_get_by_key)
    monkeypatch.setattr(notifications, "_send_with_resend", lambda **_: "msg-1")

    result = notifications._dispatch_email(
        db,  # type: ignore[arg-type]
        kind="daily_digest",
        recipient_email="user@example.com",
        subject="subject",
        text_body="body",
        payload={"k": "v"},
        skip_reason=None,
        dispatch_key="digest:2026-03-08",
    )

    assert result is existing
    assert db.rollbacks == 1
    assert calls["count"] == 2


def test_send_with_resend_non_string_id_and_helper_functions(monkeypatch) -> None:
    class _Response:
        status_code = 200
        text = "ok"

        def json(self) -> dict[str, object]:
            return {"id": 123}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _Response())
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

    config = SimpleNamespace(to_email="fallback@example.com")
    assert (
        notifications._resolve_recipient_email(config, "  override@example.com ")
        == "override@example.com"
    )
    assert notifications._resolve_recipient_email(config, "   ") == "fallback@example.com"
    assert notifications._normalize_email("  ") is None
    assert notifications._normalize_dispatch_key("  k-1  ") == "k-1"
    assert notifications._coerce_int(4.8) == 4
    assert notifications._coerce_int("bad", default=9) == 9


def test_rule_extraction_evaluation_rendering_and_query_helpers(monkeypatch) -> None:
    cfg_with_default = SimpleNamespace(
        enabled=True,
        daily_digest_hour_utc=9,
        category_rules={
            "tech": {"cadence": "daily", "hour": 10},
        },
    )
    assert notifications._extract_notification_rules(cfg_with_default, "tech") == {
        "cadence": "daily",
        "hour": 10,
    }

    cfg_flat = SimpleNamespace(
        enabled=True,
        daily_digest_hour_utc=8,
        category_rules={"ops": {"enabled": False}},
    )
    assert notifications._extract_notification_rules(cfg_flat, "ops") == {"enabled": False}
    assert (
        notifications._extract_notification_rules(SimpleNamespace(category_rules=None), "ops") == {}
    )

    now = datetime(2026, 3, 8, 6, 0, tzinfo=UTC)
    assert (
        notifications._evaluate_category_rule(
            config=SimpleNamespace(enabled=False, daily_digest_hour_utc=9, category_rules={}),
            category="tech",
            now_utc=now,
            priority=50,
        )
        == "notification config is disabled"
    )
    assert (
        notifications._evaluate_category_rule(
            config=cfg_flat,
            category="ops",
            now_utc=now,
            priority=50,
        )
        == "category rule disabled: ops"
    )

    daily_cfg = SimpleNamespace(
        enabled=True,
        daily_digest_hour_utc=8,
        category_rules={
            "default_rule": {"cadence": "daily", "hour": 7},
            "category_rules": {},
        },
    )
    assert "daily cadence mismatch" in str(
        notifications._evaluate_category_rule(
            config=daily_cfg,
            category="misc",
            now_utc=now,
            priority=None,
        )
    )

    weekly_cfg = SimpleNamespace(
        enabled=True,
        daily_digest_hour_utc=9,
        category_rules={
            "category_rules": {"ops": {"cadence": "weekly", "weekday": None, "hour": 5}}
        },
    )
    weekly_now = datetime(2026, 3, 9, 6, 0, tzinfo=UTC)
    assert "weekly cadence mismatch hour" in str(
        notifications._evaluate_category_rule(
            config=weekly_cfg,
            category="ops",
            now_utc=weekly_now,
            priority=None,
        )
    )

    # Force markdown fallback branch.
    fake_markdown = SimpleNamespace(
        markdown=lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError)
    )
    monkeypatch.setitem(sys.modules, "markdown", fake_markdown)
    html = notifications._render_markdown_html("line <x>\nline 2")
    assert html.startswith("<div>")
    assert "&lt;x&gt;" in html

    marker = object()
    db = _DispatchSession()
    db.scalar_return = marker
    assert notifications._get_video_digest_delivery(db, job_id=uuid.uuid4()) is marker  # type: ignore[arg-type]
    assert (
        notifications._get_delivery_by_dispatch_key(  # type: ignore[arg-type]
            db,
            kind="daily_digest",
            dispatch_key="k1",
        )
        is marker
    )
    assert db.scalar_calls == 2
