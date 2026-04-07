from __future__ import annotations

import importlib
import os
import sys
import tempfile
import types
import uuid

import pytest
from fastapi.testclient import TestClient

_BOOTSTRAP_TAG = f"{os.getpid()}-{uuid.uuid4().hex}"
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
os.environ.setdefault("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
os.environ.setdefault(
    "SQLITE_STATE_PATH",
    os.path.join(tempfile.gettempdir(), f"sourceharbor-api-tests-{_BOOTSTRAP_TAG}.db"),
)


@pytest.fixture(autouse=True)
def _isolated_api_test_env(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    env_root = tmp_path_factory.mktemp("api-tests-env")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
    monkeypatch.setenv("TEMPORAL_NAMESPACE", "default")
    monkeypatch.setenv("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
    monkeypatch.setenv("SQLITE_STATE_PATH", str((env_root / "state.db").resolve()))
    monkeypatch.setenv("UI_AUDIT_GEMINI_ENABLED", "false")
    if request.node.get_closest_marker("allow_unauth_write") is not None:
        monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "true")
        monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
        monkeypatch.delenv("WEB_ACTION_SESSION_TOKEN", raising=False)
    else:
        monkeypatch.delenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", raising=False)


@pytest.fixture
def allow_unauth_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", "true")


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # notifications router currently has a type-annotation issue during module import.
    # Stub it here to keep API route tests focused on health/ingest/videos behavior.
    from fastapi import APIRouter

    notifications_stub = types.ModuleType("apps.api.app.routers.notifications")
    notifications_stub.router = APIRouter(prefix="/api/v1/notifications")
    notifications_stub.reports_router = APIRouter(prefix="/api/v1/reports")
    monkeypatch.setitem(sys.modules, "apps.api.app.routers.notifications", notifications_stub)

    module = importlib.import_module("apps.api.app.main")
    app = module.app
    with TestClient(app) as client:
        yield client
