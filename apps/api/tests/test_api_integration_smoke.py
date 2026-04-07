from __future__ import annotations

import importlib
import os
import sys
import types
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

_INTEGRATION_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
)


@dataclass
class IntegrationHarness:
    client: TestClient
    session_factory: sessionmaker
    job_model: type
    video_model: type
    subscription_model: type
    temporal_client: object


def _purge_api_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "apps.api.app" or module_name.startswith("apps.api.app."):
            del sys.modules[module_name]


def _is_truthy_env(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_ci_environment() -> bool:
    return _is_truthy_env(os.getenv("CI")) or _is_truthy_env(os.getenv("GITHUB_ACTIONS"))


def _integration_smoke_strict_mode() -> bool:
    strict_override = os.getenv("API_INTEGRATION_SMOKE_STRICT")
    if strict_override is not None:
        return _is_truthy_env(strict_override)
    return _is_ci_environment()


def _fail_or_skip_for_env(requirement: str, detail: str) -> None:
    header = f"integration smoke requirement not met: {requirement}"
    guidance = "set API_INTEGRATION_SMOKE_STRICT=1 to enforce locally, or keep it unset/0 to allow local skip."
    message = f"{header}. {detail}. {guidance}"
    if _integration_smoke_strict_mode():
        pytest.fail(message, pytrace=False)
    pytest.xfail(message)


@pytest.fixture
def integration_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> Iterator[IntegrationHarness | None]:
    # Keep integration smoke deterministic even if other tests temporarily mutate DATABASE_URL.
    base_url = _INTEGRATION_DB_URL
    parsed_base = make_url(base_url)
    if parsed_base.drivername != "postgresql+psycopg":
        yield None
        return

    database_name = f"video_api_it_{uuid.uuid4().hex[:12]}"
    admin_database = parsed_base.database or "postgres"
    app_database_url = parsed_base.set(database=database_name).render_as_string(hide_password=False)
    admin_database_url = parsed_base.set(database=admin_database).render_as_string(
        hide_password=False
    )

    admin_engine = create_engine(admin_database_url, isolation_level="AUTOCOMMIT", future=True)
    state_db_path = str((tmp_path / "integration-state.db").resolve())

    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{database_name}"'))
    except Exception as exc:  # pragma: no cover
        admin_engine.dispose()
        _fail_or_skip_for_env(
            "ephemeral postgres database creation",
            f"unable to create integration database '{database_name}': {exc!r}",
        )

    try:
        monkeypatch.setenv("DATABASE_URL", app_database_url)
        monkeypatch.setenv("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
        monkeypatch.setenv("TEMPORAL_NAMESPACE", "default")
        monkeypatch.setenv("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
        monkeypatch.setenv("SQLITE_STATE_PATH", state_db_path)
        monkeypatch.setenv("UI_AUDIT_GEMINI_ENABLED", "false")
        monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "true")

        _purge_api_modules()

        notifications_stub = types.ModuleType("apps.api.app.routers.notifications")
        notifications_stub.router = APIRouter(prefix="/api/v1/notifications")
        notifications_stub.reports_router = APIRouter(prefix="/api/v1/reports")
        monkeypatch.setitem(sys.modules, "apps.api.app.routers.notifications", notifications_stub)

        models_module = importlib.import_module("apps.api.app.models")
        db_module = importlib.import_module("apps.api.app.db")
        main_module = importlib.import_module("apps.api.app.main")

        Base = models_module.Base
        Job = models_module.Job
        Video = models_module.Video
        Subscription = models_module.Subscription
        engine = db_module.engine
        SessionLocal = db_module.SessionLocal
        app = main_module.app

        Base.metadata.create_all(bind=engine)

        class _FakeTemporalClient:
            def __init__(self) -> None:
                self.started: list[dict[str, str]] = []

            async def start_workflow(
                self,
                workflow: str,
                job_id: str,
                *,
                id: str,
                task_queue: str,
                **kwargs,
            ) -> None:
                self.started.append(
                    {
                        "workflow": workflow,
                        "job_id": job_id,
                        "id": id,
                        "task_queue": task_queue,
                        "kwargs": kwargs,
                    }
                )

        fake_temporal_client = _FakeTemporalClient()

        async def _fake_connect(_target_host: str, *, namespace: str):
            assert namespace == "default"
            return fake_temporal_client

        temporal_client_module = importlib.import_module("temporalio.client")
        monkeypatch.setattr(temporal_client_module.Client, "connect", staticmethod(_fake_connect))

        with TestClient(app) as client:
            yield IntegrationHarness(
                client=client,
                session_factory=SessionLocal,
                job_model=Job,
                video_model=Video,
                subscription_model=Subscription,
                temporal_client=fake_temporal_client,
            )
    finally:
        _purge_api_modules()
        admin_engine.dispose()
        drop_engine = create_engine(admin_database_url, isolation_level="AUTOCOMMIT", future=True)
        with drop_engine.connect() as conn:
            conn.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"db_name": database_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        drop_engine.dispose()


def _count_rows(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_videos_process_reuses_existing_job_with_real_postgres(
    integration_api: IntegrationHarness | None,
) -> None:
    if integration_api is None:
        return

    payload = {
        "video": {
            "platform": "youtube",
            "url": "https://www.youtube.com/watch?v=abc123",
        },
        "mode": "refresh_comments",
        "overrides": {"lang": "zh-CN"},
    }

    first = integration_api.client.post("/api/v1/videos/process", json=payload)
    second = integration_api.client.post("/api/v1/videos/process", json=payload)

    assert first.status_code == 202
    assert second.status_code == 202

    first_json = first.json()
    second_json = second.json()

    assert first_json["video_uid"] == "abc123"
    assert first_json["mode"] == "refresh_comments"
    assert first_json["overrides"] == {"lang": "zh-CN"}
    assert first_json["reused"] is False
    assert isinstance(first_json["workflow_id"], str) and first_json["workflow_id"].startswith(
        "process-job-"
    )
    assert first_json["status"] == "queued"

    assert second_json["reused"] is True
    assert second_json["workflow_id"] is None
    assert second_json["job_id"] == first_json["job_id"]
    assert second_json["idempotency_key"] == first_json["idempotency_key"]

    videos_response = integration_api.client.get("/api/v1/videos?platform=youtube&limit=5")
    assert videos_response.status_code == 200
    videos_payload = videos_response.json()
    assert len(videos_payload) == 1
    assert videos_payload[0]["video_uid"] == "abc123"
    assert videos_payload[0]["status"] == "queued"
    assert videos_payload[0]["last_job_id"] == first_json["job_id"]

    job_response = integration_api.client.get(f"/api/v1/jobs/{first_json['job_id']}")
    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert job_payload["id"] == first_json["job_id"]
    assert job_payload["kind"] == "video_digest_v1"
    assert job_payload["status"] == "queued"
    assert job_payload["mode"] == "refresh_comments"

    with integration_api.session_factory() as session:
        assert _count_rows(session, integration_api.video_model) == 1
        assert _count_rows(session, integration_api.job_model) == 1


def test_videos_process_force_creates_new_job_with_same_video(
    integration_api: IntegrationHarness | None,
) -> None:
    if integration_api is None:
        return

    base_payload = {
        "video": {
            "platform": "youtube",
            "url": "https://www.youtube.com/watch?v=abc123",
        },
        "mode": "full",
        "overrides": {"tone": "concise"},
    }

    first = integration_api.client.post("/api/v1/videos/process", json=base_payload)
    forced = integration_api.client.post(
        "/api/v1/videos/process",
        json={
            **base_payload,
            "force": True,
        },
    )

    assert first.status_code == 202
    assert forced.status_code == 202

    first_json = first.json()
    forced_json = forced.json()
    assert first_json["reused"] is False
    assert forced_json["reused"] is False
    assert forced_json["force"] is True
    assert forced_json["job_id"] != first_json["job_id"]
    assert forced_json["video_db_id"] == first_json["video_db_id"]
    assert forced_json["idempotency_key"] != first_json["idempotency_key"]
    assert ":force:" in forced_json["idempotency_key"]
    assert forced_json["status"] == "queued"

    with integration_api.session_factory() as session:
        assert _count_rows(session, integration_api.video_model) == 1
        assert _count_rows(session, integration_api.job_model) == 2


def test_ingest_poll_starts_workflow_with_real_postgres_harness(
    integration_api: IntegrationHarness | None,
) -> None:
    if integration_api is None:
        return

    response = integration_api.client.post(
        "/api/v1/ingest/poll",
        json={"platform": "youtube", "max_new_videos": 5},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["run_id"]
    assert payload["status"] == "queued"
    assert payload["enqueued"] == 0
    assert payload["candidates"] == []

    started = integration_api.temporal_client.started
    assert len(started) == 1
    assert started[0]["workflow"] == "PollFeedsWorkflow"
    assert started[0]["job_id"]["subscription_id"] is None
    assert started[0]["job_id"]["platform"] == "youtube"
    assert started[0]["job_id"]["max_new_videos"] == 5
    assert started[0]["job_id"]["ingest_run_id"] == payload["run_id"]


def test_subscriptions_upsert_is_idempotent_with_real_postgres(
    integration_api: IntegrationHarness | None,
) -> None:
    if integration_api is None:
        return

    payload = {
        "platform": "youtube",
        "source_type": "url",
        "source_value": "https://example.com/feed.xml",
        "adapter_type": "rss_generic",
        "source_url": "https://example.com/feed.xml",
        "category": "tech",
        "tags": ["ai", "digest"],
        "priority": 80,
        "enabled": True,
    }

    first = integration_api.client.post("/api/v1/subscriptions", json=payload)
    second = integration_api.client.post("/api/v1/subscriptions", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200

    first_json = first.json()
    second_json = second.json()

    assert first_json["created"] is True
    assert second_json["created"] is False
    assert second_json["subscription"]["id"] == first_json["subscription"]["id"]
    assert second_json["subscription"]["adapter_type"] == "rss_generic"
    assert second_json["subscription"]["source_url"] == "https://example.com/feed.xml"
    assert second_json["subscription"]["priority"] == 80

    with integration_api.session_factory() as session:
        assert _count_rows(session, integration_api.subscription_model) == 1
