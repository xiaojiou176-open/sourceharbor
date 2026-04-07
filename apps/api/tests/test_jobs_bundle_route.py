from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_job_bundle_route_returns_bundle(monkeypatch) -> None:
    from apps.api.app.db import get_db
    from apps.api.app.routers import jobs as jobs_router
    from apps.api.app.services.jobs import JobsService

    class StubJobsService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        def build_evidence_bundle(self, *, job_id):  # noqa: ANN001
            return {
                "bundle_kind": "sourceharbor_job_evidence_bundle_v1",
                "sharing_scope": "internal",
                "sample": False,
                "generated_at": "2026-03-31T10:00:00Z",
                "proof_boundary": "Internal only.",
                "job": {"id": "job-1"},
                "trace_summary": {"step_count": 3},
                "digest": "# Sample",
                "digest_meta": None,
                "comparison": None,
                "knowledge_cards": [],
                "artifact_manifest": {},
                "step_summary": [],
            }

    monkeypatch.setattr(
        JobsService,
        "build_evidence_bundle",
        lambda self, job_id: {  # noqa: ARG005
            "bundle_kind": "sourceharbor_job_evidence_bundle_v1",
            "sharing_scope": "internal",
            "sample": False,
            "generated_at": "2026-03-31T10:00:00Z",
            "proof_boundary": "Internal only.",
            "job": {"id": "job-1"},
            "trace_summary": {"step_count": 3},
            "digest": "# Sample",
            "digest_meta": None,
            "comparison": None,
            "knowledge_cards": [],
            "artifact_manifest": {},
            "step_summary": [],
        },
    )
    monkeypatch.setattr(jobs_router, "JobsService", StubJobsService)

    def _fake_db():
        return object()

    app = FastAPI()
    app.include_router(jobs_router.router)
    app.dependency_overrides[get_db] = _fake_db

    client = TestClient(app)
    response = client.get("/api/v1/jobs/11111111-1111-1111-1111-111111111111/bundle")

    assert response.status_code == 200
    assert response.json()["bundle_kind"] == "sourceharbor_job_evidence_bundle_v1"


def test_job_bundle_route_returns_404_when_bundle_is_missing(monkeypatch) -> None:
    from apps.api.app.db import get_db
    from apps.api.app.routers import jobs as jobs_router
    from apps.api.app.services.jobs import JobsService

    def _missing_bundle(self, job_id):  # noqa: ANN001, ARG001
        return None

    monkeypatch.setattr(JobsService, "build_evidence_bundle", _missing_bundle)

    def _fake_db():
        return object()

    app = FastAPI()
    app.include_router(jobs_router.router)
    app.dependency_overrides[get_db] = _fake_db

    client = TestClient(app)
    response = client.get("/api/v1/jobs/11111111-1111-1111-1111-111111111111/bundle")

    assert response.status_code == 404
