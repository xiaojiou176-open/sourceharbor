from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/sourceharbor-ops-route.db")
os.environ.setdefault("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
os.environ.setdefault("TEMPORAL_TASK_QUEUE", "sourceharbor-worker")
os.environ.setdefault("SQLITE_STATE_PATH", "/tmp/sourceharbor-ops-route-state.db")


def _make_ops_client(monkeypatch, replacement) -> TestClient:  # noqa: ANN001
    from apps.api.app.routers import ops as ops_router

    app = FastAPI()
    app.include_router(ops_router.router)

    def override():  # noqa: ANN202
        return replacement(None)

    monkeypatch.setitem(app.dependency_overrides, ops_router.get_ops_service, override)
    return TestClient(app)


def test_ops_inbox_route_returns_payload(monkeypatch) -> None:
    class StubOpsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def get_inbox(self, *, limit=5, window_hours=24):  # noqa: ANN001
            return {
                "generated_at": "2026-03-31T10:00:00Z",
                "overview": {
                    "attention_items": 1,
                    "failed_jobs": 1,
                    "failed_ingest_runs": 0,
                    "notification_or_gate_issues": 1,
                },
                "failed_jobs": {"status": "ok", "total": 1, "error": None, "items": []},
                "failed_ingest_runs": {"status": "ok", "total": 0, "error": None, "items": []},
                "notification_deliveries": {"status": "ok", "total": 0, "error": None, "items": []},
                "provider_health": {"window_hours": window_hours, "providers": []},
                "gates": {
                    "retrieval": {
                        "status": "blocked",
                        "summary": "x",
                        "next_step": "x",
                        "details": {},
                    },
                    "notifications": {
                        "status": "warn",
                        "summary": "x",
                        "next_step": "x",
                        "details": {},
                    },
                    "ui_audit": {
                        "status": "ready",
                        "summary": "x",
                        "next_step": "x",
                        "details": {},
                    },
                    "computer_use": {
                        "status": "blocked",
                        "summary": "x",
                        "next_step": "x",
                        "details": {},
                    },
                },
                "inbox_items": [],
            }

    client = _make_ops_client(monkeypatch, StubOpsService)
    response = client.get("/api/v1/ops/inbox?limit=4&window_hours=12")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["failed_jobs"] == 1
    assert payload["gates"]["retrieval"]["status"] == "blocked"


def test_ops_inbox_route_sanitizes_internal_errors(monkeypatch) -> None:
    class ExplodingOpsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def get_inbox(self, *, limit=5, window_hours=24):  # noqa: ANN001
            del limit, window_hours
            raise RuntimeError(
                "db password=postgresql://ops:super-secret@127.0.0.1:5432/sourceharbor"
            )

    client = _make_ops_client(monkeypatch, ExplodingOpsService)
    response = client.get("/api/v1/ops/inbox")

    assert response.status_code == 503
    assert response.json()["detail"] == "ops inbox unavailable"
    assert "***REDACTED***" not in response.json()["detail"]
    assert "super-secret" not in response.json()["detail"]


def test_ops_inbox_route_uses_generic_bad_request_detail(monkeypatch) -> None:
    class InvalidOpsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def get_inbox(self, *, limit=5, window_hours=24):  # noqa: ANN001
            del limit, window_hours
            raise ValueError("window_hours invalid for ops@example.com?token=secret-value")

    client = _make_ops_client(monkeypatch, InvalidOpsService)
    response = client.get("/api/v1/ops/inbox")

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid ops inbox request"
