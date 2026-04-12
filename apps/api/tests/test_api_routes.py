from __future__ import annotations

import base64
import json
import sys
import tempfile
import types
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette import status

from apps.api.app import main as api_main
from apps.api.app.security import sanitize_exception_detail

pytestmark = pytest.mark.allow_unauth_write


def test_healthz_returns_ok_status(api_client: TestClient) -> None:
    response = api_client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_endpoint_exposes_prometheus_text(api_client: TestClient) -> None:
    api_client.get("/healthz")
    response = api_client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    body = response.text
    assert "sourceharbor_http_requests_total" in body
    assert 'route="/healthz"' in body


def test_trace_id_is_echoed_back_in_response_header(api_client: TestClient) -> None:
    trace_id = "trace-audit-0001"
    app_log_path = api_main._APP_LOG_PATH
    existing_lines = []
    if app_log_path.exists():
        existing_lines = [
            line for line in app_log_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]

    response = api_client.get("/healthz", headers={"x-trace-id": trace_id})

    assert response.status_code == 200
    assert response.headers.get("x-trace-id") == trace_id
    assert app_log_path.is_file()
    lines = [line for line in app_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= len(existing_lines) + 1
    new_payloads = [json.loads(line) for line in lines[len(existing_lines) :]]
    payload = next(
        (
            candidate
            for candidate in reversed(new_payloads)
            if candidate.get("event") == "http_request" and candidate.get("trace_id") == trace_id
        ),
        None,
    )
    assert payload is not None
    assert payload["channel"] == "app"
    assert payload["event"] == "http_request"
    assert payload["trace_id"] == trace_id
    assert payload["run_id"] == trace_id
    assert payload["service"] == "api"
    assert payload["source_kind"] == "app"


def test_ingest_poll_returns_candidates(
    api_client: TestClient,
    monkeypatch,
) -> None:
    run_id = uuid.uuid4()
    video_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async def fake_poll(self, *, subscription_id, platform, max_new_videos):
        assert max_new_videos == 10
        return {
            "run_id": run_id,
            "workflow_id": "wf-1",
            "status": "queued",
            "enqueued": 1,
            "candidates": [
                {
                    "video_id": video_id,
                    "platform": "youtube",
                    "video_uid": "abc123",
                    "source_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Demo",
                    "published_at": datetime.now(UTC),
                    "job_id": job_id,
                }
            ],
        }

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.poll", fake_poll)

    response = api_client.post(
        "/api/v1/ingest/poll",
        json={"platform": "youtube", "max_new_videos": 10},
    )

    payload = response.json()
    assert response.status_code == 202
    assert payload["run_id"] == str(run_id)
    assert payload["workflow_id"] == "wf-1"
    assert payload["status"] == "queued"
    assert payload["enqueued"] == 1
    assert payload["candidates"][0]["video_uid"] == "abc123"
    assert payload["candidates"][0]["job_id"] == str(job_id)


def test_ingest_poll_maps_runtime_error_to_503(api_client: TestClient, monkeypatch) -> None:
    async def fake_poll(self, *, subscription_id, platform, max_new_videos):
        del self, subscription_id, platform, max_new_videos
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.poll", fake_poll)

    response = api_client.post(
        "/api/v1/ingest/poll",
        json={"platform": "youtube", "max_new_videos": 10},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "upstream timeout"


def test_ingest_poll_maps_value_error_to_404(api_client: TestClient, monkeypatch) -> None:
    async def fake_poll(self, *, subscription_id, platform, max_new_videos):
        del self, subscription_id, platform, max_new_videos
        raise ValueError("subscription not found")

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.poll", fake_poll)

    response = api_client.post(
        "/api/v1/ingest/poll",
        json={"platform": "youtube", "max_new_videos": 10},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "subscription not found"


def test_ingest_consume_returns_batch_summary(api_client: TestClient, monkeypatch) -> None:
    batch_id = uuid.uuid4()
    cutoff_at = datetime.now(UTC)

    async def fake_consume(
        self,
        *,
        trigger_mode,
        subscription_id,
        platform,
        timezone_name,
        window_id,
        cooldown_minutes,
    ):
        del self, subscription_id, platform, timezone_name, window_id, cooldown_minutes
        assert trigger_mode == "manual"
        return {
            "consumption_batch_id": batch_id,
            "workflow_id": f"consume-batch-{batch_id}",
            "status": "frozen",
            "trigger_mode": "manual",
            "window_id": "2026-04-09@America/Los_Angeles",
            "cutoff_at": cutoff_at,
            "source_item_count": 2,
            "pending_window_ids": ["2026-04-09@America/Los_Angeles"],
            "track_interval_minutes": 15,
            "auto_cooldown_minutes": 60,
            "cooldown_remaining_seconds": 0,
        }

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.consume", fake_consume)

    response = api_client.post(
        "/api/v1/ingest/consume",
        json={"trigger_mode": "manual", "timezone_name": "America/Los_Angeles"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["consumption_batch_id"] == str(batch_id)
    assert payload["workflow_id"] == f"consume-batch-{batch_id}"
    assert payload["status"] == "frozen"
    assert payload["source_item_count"] == 2
    assert payload["track_interval_minutes"] == 15
    assert payload["auto_cooldown_minutes"] == 60


def test_ingest_runs_list_returns_summaries(api_client: TestClient, monkeypatch) -> None:
    run_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.ingest.IngestService.list_runs",
        lambda self, *, limit, status, platform: [
            SimpleNamespace(
                id=run_id,
                subscription_id=None,
                workflow_id="wf-ingest-1",
                platform=platform,
                max_new_videos=limit,
                status=status or "queued",
                jobs_created=2,
                candidates_count=2,
                feeds_polled=1,
                entries_fetched=3,
                entries_normalized=3,
                ingest_events_created=2,
                ingest_event_duplicates=1,
                job_duplicates=0,
                error_message=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
        ],
    )

    response = api_client.get("/api/v1/ingest/runs?platform=youtube&status=queued&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == str(run_id)
    assert payload[0]["workflow_id"] == "wf-ingest-1"
    assert payload[0]["platform"] == "youtube"
    assert payload[0]["status"] == "queued"
    assert payload[0]["jobs_created"] == 2


def test_ingest_runs_get_returns_items(api_client: TestClient, monkeypatch) -> None:
    run_id = uuid.uuid4()
    item_id = uuid.uuid4()
    job_id = uuid.uuid4()
    video_id = uuid.uuid4()
    event_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.ingest.IngestService.get_run",
        lambda self, *, run_id: SimpleNamespace(
            id=run_id,
            subscription_id=None,
            workflow_id="wf-ingest-2",
            platform="youtube",
            max_new_videos=10,
            status="succeeded",
            jobs_created=1,
            candidates_count=1,
            feeds_polled=1,
            entries_fetched=1,
            entries_normalized=1,
            ingest_events_created=1,
            ingest_event_duplicates=0,
            job_duplicates=0,
            error_message=None,
            requested_by="tester",
            requested_trace_id="trace-ingest",
            filters_json={"platform": "youtube"},
            created_at=now,
            updated_at=now,
            completed_at=now,
            items=[
                SimpleNamespace(
                    id=item_id,
                    subscription_id=None,
                    video_id=video_id,
                    job_id=job_id,
                    ingest_event_id=event_id,
                    platform="youtube",
                    video_uid="abc123",
                    source_url="https://www.youtube.com/watch?v=abc123",
                    title="Demo",
                    published_at=now,
                    entry_hash="entry-1",
                    pipeline_mode="full",
                    content_type="video",
                    item_status="queued",
                    created_at=now,
                    updated_at=now,
                )
            ],
        ),
    )

    response = api_client.get(f"/api/v1/ingest/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(run_id)
    assert payload["workflow_id"] == "wf-ingest-2"
    assert payload["requested_by"] == "tester"
    assert payload["filters_json"] == {"platform": "youtube"}
    assert payload["items"][0]["id"] == str(item_id)
    assert payload["items"][0]["job_id"] == str(job_id)
    assert payload["items"][0]["video_uid"] == "abc123"


def test_consumption_batches_list_and_get_return_payloads(
    api_client: TestClient, monkeypatch
) -> None:
    batch_id = uuid.uuid4()
    item_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.ingest.IngestService.list_batches",
        lambda self, *, limit, status: [
            SimpleNamespace(
                id=batch_id,
                workflow_id="consume-batch-1",
                status=status or "closed",
                trigger_mode="manual",
                window_id="2026-04-09@America/Los_Angeles",
                timezone_name="America/Los_Angeles",
                cutoff_at=now,
                requested_by="tester",
                requested_trace_id="trace-batch",
                source_item_count=1,
                processed_job_count=1,
                succeeded_job_count=1,
                failed_job_count=0,
                error_message=None,
                judged_at=now,
                materialized_at=now,
                closed_at=now,
                created_at=now,
                updated_at=now,
                items=[],
            )
        ],
    )
    monkeypatch.setattr(
        "apps.api.app.services.ingest.IngestService.get_batch",
        lambda self, *, batch_id: SimpleNamespace(
            id=batch_id,
            workflow_id="consume-batch-1",
            status="closed",
            trigger_mode="manual",
            window_id="2026-04-09@America/Los_Angeles",
            timezone_name="America/Los_Angeles",
            cutoff_at=now,
            requested_by="tester",
            requested_trace_id="trace-batch",
            source_item_count=1,
            processed_job_count=1,
            succeeded_job_count=1,
            failed_job_count=0,
            error_message=None,
            judged_at=now,
            materialized_at=now,
            closed_at=now,
            created_at=now,
            updated_at=now,
            filters_json={"platform": "youtube"},
            base_published_doc_versions=[],
            process_summary_json={"downstream_status": "cluster_judge_pending_w3"},
            items=[
                SimpleNamespace(
                    id=item_id,
                    ingest_run_item_id=None,
                    subscription_id=None,
                    video_id=None,
                    job_id=None,
                    ingest_event_id=None,
                    platform="youtube",
                    video_uid="abc123",
                    source_url="https://www.youtube.com/watch?v=abc123",
                    title="Demo",
                    published_at=now,
                    source_effective_at=now,
                    discovered_at=now,
                    entry_hash="entry-1",
                    pipeline_mode="full",
                    content_type="video",
                    source_origin="subscription_tracked",
                    created_at=now,
                    updated_at=now,
                )
            ],
        ),
    )

    list_response = api_client.get("/api/v1/ingest/batches?status=closed&limit=5")
    get_response = api_client.get(f"/api/v1/ingest/batches/{batch_id}")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == str(batch_id)
    assert get_response.status_code == 200
    assert get_response.json()["items"][0]["id"] == str(item_id)


def test_get_ingest_run_returns_not_found(api_client: TestClient, monkeypatch) -> None:
    def fake_get_run(self, *, run_id):
        del self, run_id
        return

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.get_run", fake_get_run)

    response = api_client.get(f"/api/v1/ingest/runs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "ingest run not found"


def test_list_ingest_runs_returns_summary_rows(api_client: TestClient, monkeypatch) -> None:
    run_id = uuid.uuid4()
    row = SimpleNamespace(
        id=run_id,
        subscription_id=None,
        workflow_id="wf-1",
        platform="youtube",
        max_new_videos=5,
        status="running",
        jobs_created=1,
        candidates_count=1,
        feeds_polled=1,
        entries_fetched=2,
        entries_normalized=2,
        ingest_events_created=1,
        ingest_event_duplicates=0,
        job_duplicates=1,
        error_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        completed_at=None,
    )

    def fake_list_runs(self, *, limit, status, platform):
        assert limit == 10
        assert status == "running"
        assert platform == "youtube"
        return [row]

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.list_runs", fake_list_runs)

    response = api_client.get("/api/v1/ingest/runs?limit=10&status=running&platform=youtube")

    payload = response.json()
    assert response.status_code == 200
    assert payload[0]["id"] == str(run_id)
    assert payload[0]["workflow_id"] == "wf-1"
    assert payload[0]["status"] == "running"


def test_get_ingest_run_returns_items(api_client: TestClient, monkeypatch) -> None:
    run_id = uuid.uuid4()
    item_id = uuid.uuid4()
    row = SimpleNamespace(
        id=run_id,
        subscription_id=None,
        workflow_id="wf-2",
        platform="youtube",
        max_new_videos=8,
        status="succeeded",
        jobs_created=1,
        candidates_count=1,
        feeds_polled=1,
        entries_fetched=1,
        entries_normalized=1,
        ingest_events_created=1,
        ingest_event_duplicates=0,
        job_duplicates=0,
        error_message=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        requested_by="tester",
        requested_trace_id="trace-1",
        filters_json={"platform": "youtube", "max_new_videos": 8},
        items=[
            SimpleNamespace(
                id=item_id,
                subscription_id=None,
                video_id=None,
                job_id=None,
                ingest_event_id=None,
                platform="youtube",
                video_uid="abc123",
                source_url="https://www.youtube.com/watch?v=abc123",
                title="Demo",
                published_at=datetime.now(UTC),
                entry_hash="entry-1",
                pipeline_mode="full",
                content_type="video",
                item_status="queued",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    def fake_get_run(self, *, run_id):
        assert str(run_id) == str(row.id)
        return row

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.get_run", fake_get_run)

    response = api_client.get(f"/api/v1/ingest/runs/{run_id}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["id"] == str(run_id)
    assert payload["workflow_id"] == "wf-2"
    assert payload["requested_by"] == "tester"
    assert payload["filters_json"] == {"platform": "youtube", "max_new_videos": 8}
    assert payload["items"][0]["id"] == str(item_id)
    assert payload["items"][0]["video_uid"] == "abc123"


def test_video_process_maps_value_error_to_400(
    api_client: TestClient,
    monkeypatch,
) -> None:
    async def fake_process_video(self, **kwargs):
        raise ValueError("invalid_url")

    monkeypatch.setattr(
        "apps.api.app.services.videos.VideosService.process_video",
        fake_process_video,
    )

    response = api_client.post(
        "/api/v1/videos/process",
        json={
            "video": {
                "platform": "youtube",
                "url": "invalid-url",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_url"


def test_video_process_rejects_non_whitelisted_video_url(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/videos/process",
        json={
            "video": {
                "platform": "youtube",
                "url": "https://example.com/watch?v=abc123",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "video_url_domain_not_allowed"


def test_video_process_returns_mode_field(
    api_client: TestClient,
    monkeypatch,
) -> None:
    job_id = uuid.uuid4()
    video_db_id = uuid.uuid4()

    async def fake_process_video(self, **kwargs):
        assert kwargs["mode"] == "refresh_comments"
        return {
            "job_id": job_id,
            "video_db_id": video_db_id,
            "video_uid": "abc123",
            "status": "queued",
            "idempotency_key": "idem-key",
            "mode": "refresh_comments",
            "overrides": {"lang": "zh-CN"},
            "force": False,
            "reused": False,
            "workflow_id": "wf-1",
        }

    monkeypatch.setattr(
        "apps.api.app.services.videos.VideosService.process_video",
        fake_process_video,
    )

    response = api_client.post(
        "/api/v1/videos/process",
        json={
            "video": {
                "platform": "youtube",
                "url": "https://www.youtube.com/watch?v=abc123",
            },
            "mode": "refresh_comments",
            "overrides": {"lang": "zh-CN"},
        },
    )

    payload = response.json()
    assert response.status_code == 202
    assert payload["mode"] == "refresh_comments"
    assert payload["job_id"] == str(job_id)
    assert payload["overrides"] == {"lang": "zh-CN"}


def test_video_process_redacts_sensitive_error_detail(
    api_client: TestClient,
    monkeypatch,
) -> None:
    async def fake_process_video(self, **kwargs):
        bearer_parts = ("sk", "live", "12345678901234567890")
        api_key_parts = ("abc", "123", "xyz")
        bearer_value = f"{bearer_parts[0]}-{bearer_parts[1]}-{bearer_parts[2]}"
        api_key_value = f"{api_key_parts[0]}{api_key_parts[1]}{api_key_parts[2]}"
        raise RuntimeError(
            "provider_failed Authorization: Bearer "
            f"{bearer_value} "
            "https://api.example.com/send?api_key="
            f"{api_key_value}"
        )

    monkeypatch.setattr(
        "apps.api.app.services.videos.VideosService.process_video",
        fake_process_video,
    )

    response = api_client.post(
        "/api/v1/videos/process",
        json={
            "video": {
                "platform": "youtube",
                "url": "https://www.youtube.com/watch?v=abc123",
            }
        },
    )
    detail = response.json()["detail"]

    assert response.status_code == 503
    assert "Bearer ***REDACTED***" in detail
    assert "api_key=***REDACTED***" in detail
    assert "abc123xyz" not in detail
    assert "sk-live-12345678901234567890" not in detail


def test_job_get_returns_mode_and_pipeline_fields(
    api_client: TestClient,
    monkeypatch,
) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    def fake_get_job(self, query_job_id):
        assert query_job_id == job_id
        return SimpleNamespace(
            id=job_id,
            video_id=uuid.uuid4(),
            kind="video_digest_v1",
            status="succeeded",
            mode="refresh_llm",
            idempotency_key="idem-1",
            error_message=None,
            artifact_digest_md=None,
            artifact_root=None,
            llm_required=True,
            llm_gate_passed=False,
            hard_fail_reason="llm_provider_unavailable",
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr("apps.api.app.services.jobs.JobsService.get_job", fake_get_job)
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_steps",
        lambda self, _job_id: [
            {
                "name": "write_artifacts",
                "status": "failed",
                "attempt": 1,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "error": {"reason": "llm_provider_unavailable"},
                "error_kind": None,
                "retry_meta": None,
                "result": None,
                "thought_metadata": {"provider": "gemini", "thought_tokens": 42},
                "cache_key": None,
            }
        ],
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_degradations",
        lambda self, **kwargs: [{"step": "write_artifacts", "status": "failed"}],
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_artifacts_index",
        lambda self, **kwargs: {"digest": "/tmp/digest.md"},
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_pipeline_final_status",
        lambda self, _job_id, fallback_status: "degraded",
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_notification_retry",
        lambda self, _job_id: {
            "delivery_id": str(uuid.uuid4()),
            "status": "failed",
            "attempt_count": 2,
            "next_retry_at": now,
            "last_error_kind": "transient",
        },
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["kind"] == "video_digest_v1"
    assert payload["mode"] == "refresh_llm"
    assert payload["llm_required"] is True
    assert payload["llm_gate_passed"] is False
    assert payload["hard_fail_reason"] == "llm_provider_unavailable"
    assert payload["steps"][0]["name"] == "write_artifacts"
    assert payload["steps"][0]["thought_metadata"] == {"provider": "gemini", "thought_tokens": 42}
    assert payload["degradations"][0]["step"] == "write_artifacts"
    assert payload["pipeline_final_status"] == "degraded"
    assert payload["notification_retry"]["status"] == "failed"
    assert payload["notification_retry"]["attempt_count"] == 2


def test_job_get_accepts_legacy_phase2_kind(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    def fake_get_job(self, query_job_id):
        assert query_job_id == job_id
        return SimpleNamespace(
            id=job_id,
            video_id=uuid.uuid4(),
            kind="phase2_ingest_stub",
            status="succeeded",
            mode="full",
            idempotency_key="idem-phase2",
            error_message=None,
            artifact_digest_md=None,
            artifact_root=None,
            llm_required=None,
            llm_gate_passed=None,
            hard_fail_reason=None,
            created_at=now,
            updated_at=now,
        )

    monkeypatch.setattr("apps.api.app.services.jobs.JobsService.get_job", fake_get_job)
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_steps", lambda self, _job_id: []
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_degradations", lambda self, **kwargs: []
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_artifacts_index", lambda self, **kwargs: {}
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_pipeline_final_status",
        lambda self, _job_id, fallback_status: None,
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_notification_retry",
        lambda self, _job_id: None,
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["kind"] == "phase2_ingest_stub"


def test_job_compare_returns_diff_payload(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    previous_job_id = uuid.uuid4()

    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.compare_with_previous",
        lambda self, *, job_id: {
            "job_id": str(job_id),
            "previous_job_id": str(previous_job_id),
            "has_previous": True,
            "current_digest": "# Current\n\n- one",
            "previous_digest": "# Previous\n\n- zero",
            "diff_markdown": "--- old\n+++ new\n@@\n-- zero\n+- one",
            "stats": {"added_lines": 1, "removed_lines": 1, "changed": True},
        },
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}/compare")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == str(job_id)
    assert payload["previous_job_id"] == str(previous_job_id)
    assert payload["has_previous"] is True
    assert payload["stats"]["changed"] is True
    assert payload["stats"]["added_lines"] == 1


def test_job_compare_returns_404_for_missing_job(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.compare_with_previous",
        lambda self, *, job_id: None,
    )

    response = api_client.get(f"/api/v1/jobs/{uuid.uuid4()}/compare")

    assert response.status_code == 404


def test_job_knowledge_cards_returns_payload(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_knowledge_cards",
        lambda self, *, job_id: [
            {
                "card_type": "takeaway",
                "title": "Key takeaway",
                "body": "This job added a durable takeaway.",
                "source_section": "highlights",
                "order_index": 1,
            }
        ],
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}/knowledge-cards")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["card_type"] == "takeaway"
    assert payload[0]["title"] == "Key takeaway"


def test_job_knowledge_cards_returns_404_for_missing_job(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_knowledge_cards",
        lambda self, *, job_id: None,
    )

    response = api_client.get(f"/api/v1/jobs/{uuid.uuid4()}/knowledge-cards")

    assert response.status_code == 404


def test_knowledge_cards_list_returns_rows(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    video_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.knowledge.KnowledgeService.list_cards",
        lambda self, *, job_id, video_id, card_type, topic_key, claim_kind, limit: [
            SimpleNamespace(
                id=uuid.uuid4(),
                job_id=job_id,
                video_id=video_id or uuid.uuid4(),
                card_type=card_type or "takeaway",
                source_section="highlights",
                title="Key takeaway",
                body="Durable note",
                ordinal=0,
                metadata_json={
                    "kind": "highlight",
                    "topic_key": topic_key or "agent-workflows",
                    "claim_kind": claim_kind or "takeaway",
                },
                created_at=now,
                updated_at=now,
            )
        ],
    )

    response = api_client.get(
        f"/api/v1/knowledge/cards?job_id={job_id}&video_id={video_id}&card_type=takeaway&topic_key=agent-workflows&claim_kind=takeaway&limit=5"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["job_id"] == str(job_id)
    assert payload[0]["video_id"] == str(video_id)
    assert payload[0]["card_type"] == "takeaway"
    assert payload[0]["metadata_json"]["topic_key"] == "agent-workflows"
    assert payload[0]["metadata_json"]["claim_kind"] == "takeaway"
    assert payload[0]["order_index"] == 0
    assert payload[0]["metadata_json"]["kind"] == "highlight"


def test_feed_feedback_get_returns_default_state(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    monkeypatch.setattr(
        "apps.api.app.services.feed.FeedService.get_feedback",
        lambda self, *, job_id: {
            "job_id": job_id,
            "saved": False,
            "feedback_label": None,
            "exists": False,
            "created_at": None,
            "updated_at": None,
        },
    )

    response = api_client.get(f"/api/v1/feed/feedback?job_id={job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == str(job_id)
    assert payload["exists"] is False
    assert payload["saved"] is False


def test_feed_feedback_put_updates_state(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "apps.api.app.services.feed.FeedService.set_feedback",
        lambda self, *, job_id, saved, feedback_label: {
            "job_id": job_id,
            "saved": saved,
            "feedback_label": feedback_label,
            "exists": True,
            "created_at": now,
            "updated_at": now,
        },
    )

    response = api_client.put(
        "/api/v1/feed/feedback",
        json={"job_id": str(job_id), "saved": True, "feedback_label": "useful"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == str(job_id)
    assert payload["saved"] is True
    assert payload["feedback_label"] == "useful"


def test_feed_feedback_put_maps_missing_job_to_404(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.feed.FeedService.set_feedback",
        lambda self, **kwargs: (_ for _ in ()).throw(ValueError("job not found")),
    )

    response = api_client.put(
        "/api/v1/feed/feedback",
        json={"job_id": str(uuid.uuid4()), "saved": False, "feedback_label": None},
    )

    assert response.status_code == 404


def test_job_get_preserves_explicit_llm_required_false(api_client: TestClient, monkeypatch) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_job",
        lambda self, query_job_id: SimpleNamespace(
            id=query_job_id,
            video_id=uuid.uuid4(),
            kind="video_digest_v1",
            status="queued",
            mode="text_only",
            idempotency_key="idem-llm-false",
            error_message=None,
            artifact_digest_md=None,
            artifact_root=None,
            llm_required=False,
            llm_gate_passed=None,
            hard_fail_reason=None,
            created_at=now,
            updated_at=now,
        ),
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_steps", lambda self, _job_id: []
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_degradations", lambda self, **kwargs: []
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_artifacts_index", lambda self, **kwargs: {}
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_pipeline_final_status",
        lambda self, _job_id, fallback_status: None,
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_notification_retry",
        lambda self, _job_id: None,
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["llm_required"] is False
    assert payload["llm_gate_passed"] is None
    assert payload["hard_fail_reason"] is None


def test_retrieval_search_returns_items(api_client: TestClient, monkeypatch) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_search(self, *, query, top_k, mode, filters):
        assert query == "timeout"
        assert top_k == 2
        assert mode == "keyword"
        assert filters == {"platform": "youtube"}
        return {
            "query": query,
            "top_k": top_k,
            "filters": filters,
            "items": [
                {
                    "job_id": "00000000-0000-0000-0000-000000000001",
                    "video_id": "00000000-0000-0000-0000-000000000010",
                    "platform": "youtube",
                    "video_uid": "abc123",
                    "source_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Demo",
                    "kind": "video_digest_v1",
                    "mode": "full",
                    "source": "digest",
                    "snippet": "timeout happened in provider step",
                    "score": 2.5,
                }
            ],
        }

    monkeypatch.setattr(retrieval_router.RetrievalService, "search", fake_search)

    response = api_client.post(
        "/api/v1/retrieval/search",
        json={"query": "timeout", "top_k": 2, "filters": {"platform": "youtube"}},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["query"] == "timeout"
    assert payload["top_k"] == 2
    assert payload["filters"] == {"platform": "youtube"}
    assert payload["items"][0]["source"] == "digest"
    assert payload["items"][0]["score"] == 2.5


def test_retrieval_search_passes_semantic_mode(api_client: TestClient, monkeypatch) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_search(self, *, query, top_k, mode, filters):
        assert query == "retry policy"
        assert top_k == 3
        assert mode == "semantic"
        assert filters == {"platform": "youtube"}
        return {"query": query, "top_k": top_k, "filters": filters, "items": []}

    monkeypatch.setattr(retrieval_router.RetrievalService, "search", fake_search)

    response = api_client.post(
        "/api/v1/retrieval/search",
        json={
            "query": "retry policy",
            "top_k": 3,
            "mode": "semantic",
            "filters": {"platform": "youtube"},
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["query"] == "retry policy"
    assert payload["top_k"] == 3
    assert payload["filters"] == {"platform": "youtube"}
    assert payload["items"] == []


def test_retrieval_search_accepts_knowledge_cards_source(
    api_client: TestClient, monkeypatch
) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_search(self, *, query, top_k, mode, filters):
        del self
        assert query == "takeaway"
        assert top_k == 1
        assert mode == "keyword"
        assert filters == {}
        return {
            "query": query,
            "top_k": top_k,
            "filters": filters,
            "items": [
                {
                    "job_id": "00000000-0000-0000-0000-000000000001",
                    "video_id": "00000000-0000-0000-0000-000000000010",
                    "platform": "youtube",
                    "video_uid": "abc123",
                    "source_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Demo",
                    "kind": "video_digest_v1",
                    "mode": "full",
                    "source": "knowledge_cards",
                    "snippet": "A reusable takeaway card.",
                    "score": 1.5,
                }
            ],
        }

    monkeypatch.setattr(retrieval_router.RetrievalService, "search", fake_search)

    response = api_client.post(
        "/api/v1/retrieval/search",
        json={"query": "takeaway", "top_k": 1},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["source"] == "knowledge_cards"


def test_retrieval_search_semantic_failure_is_observable(
    api_client: TestClient, monkeypatch
) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_search(self, *, query, top_k, mode, filters):
        del self, query, top_k, mode, filters
        raise retrieval_router.ApiServiceError(
            detail="retrieval embedding request failed",
            error_code="RETRIEVAL_EMBEDDING_REQUEST_FAILED",
            status_code=503,
            error_kind="upstream_error",
        )

    monkeypatch.setattr(retrieval_router.RetrievalService, "search", fake_search)

    response = api_client.post(
        "/api/v1/retrieval/search",
        json={
            "query": "retry policy",
            "top_k": 3,
            "mode": "semantic",
            "filters": {"platform": "youtube"},
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "retrieval embedding request failed",
        "error_code": "RETRIEVAL_EMBEDDING_REQUEST_FAILED",
        "error_kind": "upstream_error",
    }


def test_retrieval_answer_returns_structured_contract(api_client: TestClient, monkeypatch) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_answer(self, *, query, watchlist_id, story_id, top_k, mode, filters):
        del self
        assert query == "retry policy"
        assert watchlist_id == "wl-1"
        assert story_id is None
        assert top_k == 4
        assert mode == "keyword"
        assert filters == {"platform": "youtube"}
        return {
            "query": query,
            "context": {
                "watchlist_id": watchlist_id,
                "watchlist_name": "Retry policy",
                "story_id": story_id,
                "selected_story_id": "story-1",
                "story_headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "selection_basis": "query_match",
                "mode": mode,
                "filters": filters,
                "briefing_available": True,
            },
            "selected_story": {
                "story_id": "story-1",
                "story_key": "topic:retry-policy",
                "headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "source_count": 2,
                "run_count": 2,
                "matched_card_count": 1,
                "platforms": ["youtube"],
                "claim_kinds": ["recommendation"],
                "source_urls": ["https://example.com/retry"],
                "latest_run_job_id": "job-2",
                "evidence_cards": [],
                "routes": {
                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
            },
            "answer": {
                "direct_answer": 'For "retry policy", the current briefing most strongly points to "Retry Policy".',
                "summary": "Retry policy currently converges across recent sources.",
                "reason": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
                "confidence": "grounded",
            },
            "changes": {
                "summary": "Added topics: retry-policy.",
                "story_focus_summary": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
                "latest_job_id": "job-2",
                "previous_job_id": "job-1",
                "added_topics": ["retry-policy"],
                "removed_topics": [],
                "added_claim_kinds": ["recommendation"],
                "removed_claim_kinds": [],
                "new_story_keys": ["topic:retry-policy"],
                "removed_story_keys": [],
                "compare_excerpt": "@@ latest diff @@",
                "compare_route": "/jobs?job_id=job-2",
                "has_previous": True,
            },
            "citations": [
                {
                    "kind": "briefing_story",
                    "label": "Retry Policy",
                    "snippet": "Supported across 2 source families.",
                    "source_url": None,
                    "job_id": "job-2",
                    "route": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "route_label": "Open briefing story",
                }
            ],
            "evidence": {
                "briefing_overview": "Retry policy currently converges across recent sources.",
                "selected_story_id": "story-1",
                "selected_story_headline": "Retry Policy",
                "latest_job_id": "job-2",
                "citation_count": 1,
                "retrieval_hit_count": 1,
                "retrieval_items": [
                    {
                        "job_id": "job-2",
                        "video_id": "video-2",
                        "platform": "youtube",
                        "video_uid": "abc123",
                        "source_url": "https://www.youtube.com/watch?v=abc123",
                        "title": "Demo",
                        "kind": "video_digest_v1",
                        "mode": "full",
                        "source": "knowledge_cards",
                        "snippet": "Retry policy evidence",
                        "score": 2.2,
                    }
                ],
                "story_cards": [
                    {
                        "card_id": "card-1",
                        "job_id": "job-2",
                        "platform": "youtube",
                        "source_url": "https://example.com/retry",
                        "title": "Retry policy card",
                        "body": "Retry policy is now explicit.",
                        "source_section": "summary",
                    }
                ],
            },
            "fallback": {
                "status": "grounded",
                "reason": None,
                "suggested_next_step": None,
                "actions": [],
            },
        }

    monkeypatch.setattr(retrieval_router.RetrievalService, "answer", fake_answer)

    response = api_client.post(
        "/api/v1/retrieval/answer",
        json={
            "query": "retry policy",
            "watchlist_id": "wl-1",
            "top_k": 4,
            "filters": {"platform": "youtube"},
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["context"]["selected_story_id"] == "story-1"
    assert payload["context"]["watchlist_name"] == "Retry policy"
    assert payload["context"]["story_headline"] == "Retry Policy"
    assert payload["context"]["selection_basis"] == "query_match"
    assert (
        payload["selected_story"]["routes"]["briefing"]
        == "/briefings?watchlist_id=wl-1&story_id=story-1"
    )
    assert payload["answer"]["confidence"] == "grounded"
    assert payload["answer"]["reason"].startswith('"Retry Policy" is newly surfaced')
    assert payload["changes"]["story_focus_summary"].startswith('"Retry Policy" is newly surfaced')
    assert payload["changes"]["compare_route"] == "/jobs?job_id=job-2"
    assert payload["citations"][0]["kind"] == "briefing_story"
    assert payload["citations"][0]["route_label"] == "Open briefing story"
    assert payload["fallback"]["status"] == "grounded"


def test_retrieval_answer_page_returns_server_owned_payload(
    api_client: TestClient, monkeypatch
) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_answer_page(self, *, query, watchlist_id, story_id, topic_key, top_k, mode, filters):
        del self
        assert query == "retry policy"
        assert watchlist_id == "wl-1"
        assert story_id == "story-1"
        assert topic_key == "retry-policy"
        assert top_k == 4
        assert mode == "keyword"
        assert filters == {"platform": "youtube"}
        return {
            "question": query,
            "mode": mode,
            "top_k": top_k,
            "context": {
                "watchlist_id": watchlist_id,
                "watchlist_name": "Retry policy",
                "story_id": "story-1",
                "selected_story_id": "story-1",
                "story_headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "selection_basis": "requested_story_id",
                "mode": mode,
                "filters": filters,
                "briefing_available": True,
            },
            "answer_state": "briefing_grounded",
            "answer_headline": 'For "retry policy", the current briefing most strongly points to "Retry Policy".',
            "answer_summary": "Retry policy currently converges across recent sources.",
            "answer_reason": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
            "answer_confidence": "grounded",
            "story_change_summary": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
            "story_page": {
                "context": {
                    "watchlist_id": watchlist_id,
                    "watchlist_name": "Retry policy",
                    "story_id": "story-1",
                    "selected_story_id": "story-1",
                    "story_headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "selection_basis": "requested_story_id",
                    "question_seed": "retry policy",
                },
                "briefing": {
                    "watchlist": {
                        "id": "wl-1",
                        "name": "Retry policy",
                        "matcher_type": "topic_key",
                        "matcher_value": "retry-policy",
                        "delivery_channel": "dashboard",
                        "enabled": True,
                        "created_at": "2026-03-31T10:00:00Z",
                        "updated_at": "2026-03-31T10:00:00Z",
                    },
                    "summary": {
                        "overview": "Retry policy currently converges across recent sources.",
                        "source_count": 2,
                        "run_count": 2,
                        "story_count": 1,
                        "matched_cards": 2,
                        "primary_story_headline": "Retry Policy",
                        "signals": [],
                    },
                    "differences": {
                        "latest_job_id": "job-2",
                        "previous_job_id": "job-1",
                        "added_topics": ["retry-policy"],
                        "removed_topics": [],
                        "added_claim_kinds": ["recommendation"],
                        "removed_claim_kinds": [],
                        "new_story_keys": ["topic:retry-policy"],
                        "removed_story_keys": [],
                        "compare": {
                            "job_id": "job-2",
                            "has_previous": True,
                            "previous_job_id": "job-1",
                            "changed": True,
                            "added_lines": 2,
                            "removed_lines": 1,
                            "diff_excerpt": "@@ latest diff @@",
                            "compare_route": "/jobs?job_id=job-2",
                        },
                    },
                    "evidence": {
                        "suggested_story_id": "story-1",
                        "stories": [
                            {
                                "story_id": "story-1",
                                "story_key": "topic:retry-policy",
                                "headline": "Retry Policy",
                                "topic_key": "retry-policy",
                                "topic_label": "Retry Policy",
                                "source_count": 2,
                                "run_count": 2,
                                "matched_card_count": 1,
                                "platforms": ["youtube"],
                                "claim_kinds": ["recommendation"],
                                "source_urls": ["https://example.com/retry"],
                                "latest_run_job_id": "job-2",
                                "evidence_cards": [],
                                "routes": {
                                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                                    "ask": "/ask?watchlist_id=wl-1&question=retry+policy&story_id=story-1&topic_key=retry-policy",
                                    "job_compare": "/jobs?job_id=job-2",
                                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                                },
                            }
                        ],
                        "featured_runs": [],
                    },
                    "selection": {
                        "selected_story_id": "story-1",
                        "selection_basis": "requested_story_id",
                        "story": None,
                    },
                },
                "selected_story": {
                    "story_id": "story-1",
                    "story_key": "topic:retry-policy",
                    "headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "source_count": 2,
                    "run_count": 2,
                    "matched_card_count": 1,
                    "platforms": ["youtube"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/retry"],
                    "latest_run_job_id": "job-2",
                    "evidence_cards": [],
                    "routes": {
                        "watchlist_trend": "/trends?watchlist_id=wl-1",
                        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                        "ask": "/ask?watchlist_id=wl-1&question=retry+policy&story_id=story-1&topic_key=retry-policy",
                        "job_compare": "/jobs?job_id=job-2",
                        "job_bundle": "/api/v1/jobs/job-2/bundle",
                        "job_knowledge_cards": "/knowledge?job_id=job-2",
                    },
                },
                "story_change_summary": '"Retry Policy" is newly surfaced in the latest briefing and is already backed by 2 source families.',
                "citations": [
                    {
                        "kind": "briefing_story",
                        "label": "Retry Policy",
                        "snippet": "Supported across 2 source families.",
                        "source_url": None,
                        "job_id": "job-2",
                        "route": "/briefings?watchlist_id=wl-1&story_id=story-1",
                        "route_label": "Open briefing story",
                    }
                ],
                "routes": {
                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "ask": "/ask?watchlist_id=wl-1&question=retry+policy&story_id=story-1&topic_key=retry-policy",
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
                "ask_route": "/ask?watchlist_id=wl-1&question=retry+policy&story_id=story-1&topic_key=retry-policy",
                "compare_route": "/jobs?job_id=job-2",
                "fallback_reason": None,
                "fallback_next_step": None,
                "fallback_actions": [],
            },
            "briefing": {
                "watchlist": {
                    "id": "wl-1",
                    "name": "Retry policy",
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
                "summary": {
                    "overview": "Retry policy currently converges across recent sources.",
                    "source_count": 2,
                    "run_count": 2,
                    "story_count": 1,
                    "matched_cards": 2,
                    "primary_story_headline": "Retry Policy",
                    "signals": [],
                },
                "differences": {
                    "latest_job_id": "job-2",
                    "previous_job_id": "job-1",
                    "added_topics": ["retry-policy"],
                    "removed_topics": [],
                    "added_claim_kinds": ["recommendation"],
                    "removed_claim_kinds": [],
                    "new_story_keys": ["topic:retry-policy"],
                    "removed_story_keys": [],
                    "compare": {
                        "job_id": "job-2",
                        "has_previous": True,
                        "previous_job_id": "job-1",
                        "changed": True,
                        "added_lines": 2,
                        "removed_lines": 1,
                        "diff_excerpt": "@@ latest diff @@",
                        "compare_route": "/jobs?job_id=job-2",
                    },
                },
                "evidence": {
                    "suggested_story_id": "story-1",
                    "stories": [
                        {
                            "story_id": "story-1",
                            "story_key": "topic:retry-policy",
                            "headline": "Retry Policy",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry Policy",
                            "source_count": 2,
                            "run_count": 2,
                            "matched_card_count": 1,
                            "platforms": ["youtube"],
                            "claim_kinds": ["recommendation"],
                            "source_urls": ["https://example.com/retry"],
                            "latest_run_job_id": "job-2",
                            "evidence_cards": [],
                            "routes": {
                                "watchlist_trend": "/trends?watchlist_id=wl-1",
                                "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                                "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                                "job_compare": "/jobs?job_id=job-2",
                                "job_bundle": "/api/v1/jobs/job-2/bundle",
                                "job_knowledge_cards": "/knowledge?job_id=job-2",
                            },
                        }
                    ],
                    "featured_runs": [],
                },
                "context": {
                    "watchlist_id": "wl-1",
                    "watchlist_name": "Retry policy",
                    "story_id": "story-1",
                    "selected_story_id": "story-1",
                    "story_headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "selection_basis": "requested_story_id",
                    "question_seed": "retry policy",
                },
                "selected_story": {
                    "story_id": "story-1",
                    "story_key": "topic:retry-policy",
                    "headline": "Retry Policy",
                    "topic_key": "retry-policy",
                    "topic_label": "Retry Policy",
                    "source_count": 2,
                    "run_count": 2,
                    "matched_card_count": 1,
                    "platforms": ["youtube"],
                    "claim_kinds": ["recommendation"],
                    "source_urls": ["https://example.com/retry"],
                    "latest_run_job_id": "job-2",
                    "evidence_cards": [],
                    "routes": {
                        "watchlist_trend": "/trends?watchlist_id=wl-1",
                        "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                        "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                        "job_compare": "/jobs?job_id=job-2",
                        "job_bundle": "/api/v1/jobs/job-2/bundle",
                        "job_knowledge_cards": "/knowledge?job_id=job-2",
                    },
                },
                "routes": {
                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
            },
            "selected_story": {
                "story_id": "story-1",
                "story_key": "topic:retry-policy",
                "headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry Policy",
                "source_count": 2,
                "run_count": 2,
                "matched_card_count": 1,
                "platforms": ["youtube"],
                "claim_kinds": ["recommendation"],
                "source_urls": ["https://example.com/retry"],
                "latest_run_job_id": "job-2",
                "evidence_cards": [],
                "routes": {
                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "ask": "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy",
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
            },
            "retrieval": {
                "query": query,
                "top_k": top_k,
                "filters": filters,
                "items": [],
            },
            "citations": [
                {
                    "kind": "briefing_story",
                    "label": "Retry Policy",
                    "snippet": "Supported across 2 source families.",
                    "source_url": None,
                    "job_id": "job-2",
                    "route": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "route_label": "Open briefing story",
                }
            ],
            "fallback_reason": None,
            "fallback_next_step": None,
            "fallback_actions": [],
        }

    monkeypatch.setattr(retrieval_router.RetrievalService, "answer_page", fake_answer_page)

    response = api_client.post(
        "/api/v1/retrieval/answer/page",
        json={
            "query": "retry policy",
            "watchlist_id": "wl-1",
            "story_id": "story-1",
            "topic_key": "retry-policy",
            "top_k": 4,
            "filters": {"platform": "youtube"},
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["context"]["selection_basis"] == "requested_story_id"
    assert (
        payload["story_page"]["selected_story"]["routes"]["briefing"]
        == "/briefings?watchlist_id=wl-1&story_id=story-1"
    )
    assert payload["answer_state"] == "briefing_grounded"
    assert payload["citations"][0]["route_label"] == "Open briefing story"
    assert payload["fallback_actions"] == []


def test_retrieval_answer_page_service_error_is_observable(
    api_client: TestClient, monkeypatch
) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_answer_page(self, *, query, watchlist_id, story_id, topic_key, top_k, mode, filters):
        del self, query, watchlist_id, story_id, topic_key, top_k, mode, filters
        raise retrieval_router.ApiServiceError(
            detail="ask page unavailable",
            error_code="ASK_PAGE_UNAVAILABLE",
            status_code=503,
            error_kind="dependency_error",
        )

    monkeypatch.setattr(retrieval_router.RetrievalService, "answer_page", fake_answer_page)

    response = api_client.post(
        "/api/v1/retrieval/answer/page",
        json={"query": "retry policy", "watchlist_id": "wl-1"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "ask page unavailable",
        "error_code": "ASK_PAGE_UNAVAILABLE",
        "error_kind": "dependency_error",
    }


def test_retrieval_answer_service_error_is_observable(api_client: TestClient, monkeypatch) -> None:
    from apps.api.app.routers import retrieval as retrieval_router

    def fake_answer(self, *, query, watchlist_id, story_id, top_k, mode, filters):
        del self, query, watchlist_id, story_id, top_k, mode, filters
        raise retrieval_router.ApiServiceError(
            detail="briefing unavailable",
            error_code="ASK_BRIEFING_UNAVAILABLE",
            status_code=503,
            error_kind="dependency_error",
        )

    monkeypatch.setattr(retrieval_router.RetrievalService, "answer", fake_answer)

    response = api_client.post(
        "/api/v1/retrieval/answer",
        json={"query": "retry policy", "watchlist_id": "wl-1"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "briefing unavailable",
        "error_code": "ASK_BRIEFING_UNAVAILABLE",
        "error_kind": "dependency_error",
    }


def test_watchlist_briefing_page_returns_server_owned_story_payload(
    api_client: TestClient, monkeypatch
) -> None:
    def fake_get_watchlist_briefing_page(
        self,
        *,
        watchlist_id,
        story_id,
        query,
        limit_runs,
        limit_cards,
        limit_stories,
        limit_evidence_per_story,
    ):
        del self, query, limit_runs, limit_cards, limit_stories, limit_evidence_per_story
        assert watchlist_id == "wl-1"
        assert story_id == "story-1"
        return {
            "context": {
                "watchlist_id": "wl-1",
                "watchlist_name": "Retry policy",
                "story_id": "story-1",
                "selected_story_id": "story-1",
                "story_headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry policy",
                "selection_basis": "requested_story_id",
                "question_seed": "Retry Policy",
            },
            "briefing": {
                "watchlist": {
                    "id": "wl-1",
                    "name": "Retry policy",
                    "matcher_type": "topic_key",
                    "matcher_value": "retry-policy",
                    "delivery_channel": "dashboard",
                    "enabled": True,
                    "created_at": "2026-03-31T10:00:00Z",
                    "updated_at": "2026-03-31T10:00:00Z",
                },
                "summary": {
                    "overview": "Retry policy currently converges across recent sources.",
                    "source_count": 2,
                    "run_count": 2,
                    "story_count": 1,
                    "matched_cards": 2,
                    "primary_story_headline": "Retry Policy",
                    "signals": [],
                },
                "differences": {
                    "latest_job_id": "job-2",
                    "previous_job_id": "job-1",
                    "added_topics": ["retry-policy"],
                    "removed_topics": [],
                    "added_claim_kinds": ["recommendation"],
                    "removed_claim_kinds": [],
                    "new_story_keys": ["topic:retry-policy"],
                    "removed_story_keys": [],
                    "compare": {
                        "job_id": "job-2",
                        "has_previous": True,
                        "previous_job_id": "job-1",
                        "changed": True,
                        "added_lines": 2,
                        "removed_lines": 1,
                        "diff_excerpt": "@@ latest diff @@",
                        "compare_route": "/jobs?job_id=job-2",
                    },
                },
                "evidence": {
                    "suggested_story_id": "story-1",
                    "stories": [
                        {
                            "story_id": "story-1",
                            "story_key": "topic:retry-policy",
                            "headline": "Retry Policy",
                            "topic_key": "retry-policy",
                            "topic_label": "Retry policy",
                            "source_count": 2,
                            "run_count": 2,
                            "matched_card_count": 1,
                            "platforms": ["youtube"],
                            "claim_kinds": ["recommendation"],
                            "source_urls": ["https://example.com/retry"],
                            "latest_run_job_id": "job-2",
                            "evidence_cards": [],
                            "routes": {
                                "watchlist_trend": "/trends?watchlist_id=wl-1",
                                "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                                "ask": "/ask?watchlist_id=wl-1&question=Retry+Policy&story_id=story-1&topic_key=retry-policy",
                                "job_compare": "/jobs?job_id=job-2",
                                "job_bundle": "/api/v1/jobs/job-2/bundle",
                                "job_knowledge_cards": "/knowledge?job_id=job-2",
                            },
                        }
                    ],
                    "featured_runs": [],
                },
                "selection": {
                    "selected_story_id": "story-1",
                    "selection_basis": "requested_story_id",
                    "story": None,
                },
            },
            "selected_story": {
                "story_id": "story-1",
                "story_key": "topic:retry-policy",
                "headline": "Retry Policy",
                "topic_key": "retry-policy",
                "topic_label": "Retry policy",
                "source_count": 2,
                "run_count": 2,
                "matched_card_count": 1,
                "platforms": ["youtube"],
                "claim_kinds": ["recommendation"],
                "source_urls": ["https://example.com/retry"],
                "latest_run_job_id": "job-2",
                "evidence_cards": [],
                "routes": {
                    "watchlist_trend": "/trends?watchlist_id=wl-1",
                    "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "ask": "/ask?watchlist_id=wl-1&question=Retry+Policy&story_id=story-1&topic_key=retry-policy",
                    "job_compare": "/jobs?job_id=job-2",
                    "job_bundle": "/api/v1/jobs/job-2/bundle",
                    "job_knowledge_cards": "/knowledge?job_id=job-2",
                },
            },
            "story_change_summary": '"Retry Policy" is newly surfaced in the latest briefing.',
            "citations": [
                {
                    "kind": "briefing_story",
                    "label": "Retry Policy",
                    "snippet": "Supported across 2 source families.",
                    "source_url": None,
                    "job_id": "job-2",
                    "route": "/briefings?watchlist_id=wl-1&story_id=story-1",
                    "route_label": "Open briefing story",
                }
            ],
            "routes": {
                "watchlist_trend": "/trends?watchlist_id=wl-1",
                "briefing": "/briefings?watchlist_id=wl-1&story_id=story-1",
                "ask": "/ask?watchlist_id=wl-1&question=Retry+Policy&story_id=story-1&topic_key=retry-policy",
                "job_compare": "/jobs?job_id=job-2",
                "job_bundle": "/api/v1/jobs/job-2/bundle",
                "job_knowledge_cards": "/knowledge?job_id=job-2",
            },
            "ask_route": "/ask?watchlist_id=wl-1&question=Retry+Policy&story_id=story-1&topic_key=retry-policy",
            "compare_route": "/jobs?job_id=job-2",
            "fallback_reason": None,
            "fallback_next_step": None,
            "fallback_actions": [],
        }

    monkeypatch.setattr(
        "apps.api.app.services.watchlists.WatchlistsService.get_watchlist_briefing_page",
        fake_get_watchlist_briefing_page,
    )

    response = api_client.get(
        "/api/v1/watchlists/wl-1/briefing/page",
        params={"story_id": "story-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]["selected_story_id"] == "story-1"
    assert payload["context"]["selection_basis"] == "requested_story_id"
    assert payload["selected_story"]["story_id"] == "story-1"
    assert payload["routes"]["ask"].endswith("story_id=story-1&topic_key=retry-policy")
    assert payload["ask_route"].endswith("story_id=story-1&topic_key=retry-policy")


def test_feed_digests_returns_items(api_client: TestClient, monkeypatch) -> None:
    sub_id = str(uuid.uuid4())

    def fake_list_digest_feed(
        self, *, source, category, feedback, sort, subscription_id, limit, cursor, since
    ):
        assert source == "youtube"
        assert category == "tech"
        assert feedback is None
        assert sort is None
        assert subscription_id == sub_id
        assert limit == 5
        assert cursor is None
        assert since is None
        return {
            "items": [
                {
                    "feed_id": "2026-02-23T09:58:12Z__job-1",
                    "job_id": "job-1",
                    "video_url": "https://www.youtube.com/watch?v=abc123",
                    "title": "Demo Title",
                    "source": "youtube",
                    "source_name": "youtube",
                    "category": "tech",
                    "published_at": "2026-02-23T09:58:12Z",
                    "summary_md": "# Demo\n\nsummary body",
                    "artifact_type": "digest",
                    "content_type": "article",
                }
            ],
            "has_more": True,
            "next_cursor": "2026-02-23T09:58:12Z__job-1",
        }

    monkeypatch.setattr(
        "apps.api.app.services.feed.FeedService.list_digest_feed", fake_list_digest_feed
    )

    response = api_client.get(
        "/api/v1/feed/digests",
        params={"source": "youtube", "category": "tech", "sub": sub_id, "limit": 5},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["has_more"] is True
    assert payload["next_cursor"] == "2026-02-23T09:58:12Z__job-1"
    assert payload["items"][0]["category"] == "tech"
    assert payload["items"][0]["source"] == "youtube"
    assert payload["items"][0]["artifact_type"] == "digest"
    assert payload["items"][0]["content_type"] == "article"


def test_feed_digests_passes_feedback_filter(api_client: TestClient, monkeypatch) -> None:
    def fake_list_digest_feed(
        self, *, source, category, feedback, sort, subscription_id, limit, cursor, since
    ):
        assert source is None
        assert category is None
        assert feedback == "saved"
        assert sort is None
        assert subscription_id is None
        assert limit == 20
        assert cursor is None
        assert since is None
        return {"items": [], "has_more": False, "next_cursor": None}

    monkeypatch.setattr(
        "apps.api.app.services.feed.FeedService.list_digest_feed", fake_list_digest_feed
    )

    response = api_client.get("/api/v1/feed/digests", params={"feedback": "saved"})

    assert response.status_code == 200
    assert response.json() == {"items": [], "has_more": False, "next_cursor": None}


def test_feed_digests_passes_sort_mode(api_client: TestClient, monkeypatch) -> None:
    def fake_list_digest_feed(
        self, *, source, category, feedback, sort, subscription_id, limit, cursor, since
    ):
        assert source == "youtube"
        assert category is None
        assert feedback is None
        assert sort == "curated"
        assert subscription_id is None
        assert limit == 20
        assert cursor is None
        assert since is None
        return {"items": [], "has_more": False, "next_cursor": None}

    monkeypatch.setattr(
        "apps.api.app.services.feed.FeedService.list_digest_feed", fake_list_digest_feed
    )

    response = api_client.get(
        "/api/v1/feed/digests", params={"source": "youtube", "sort": "curated"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "has_more": False, "next_cursor": None}


def test_subscriptions_list_includes_adapter_and_category_fields(
    api_client: TestClient, monkeypatch
) -> None:
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.list_subscriptions",
        lambda self, **kwargs: [
            SimpleNamespace(
                id=uuid.uuid4(),
                platform="youtube",
                source_type="url",
                source_value="https://youtube.com/@demo",
                source_name="https://youtube.com/@demo",
                adapter_type="rss_generic",
                source_url="https://example.com/feed.xml",
                rsshub_route="https://example.com/feed.xml",
                category="tech",
                tags=["ai", "weekly"],
                priority=80,
                enabled=True,
                created_at=now,
                updated_at=now,
            )
        ],
    )

    response = api_client.get("/api/v1/subscriptions")
    payload = response.json()

    assert response.status_code == 200
    assert payload[0]["adapter_type"] == "rss_generic"
    assert payload[0]["source_url"] == "https://example.com/feed.xml"
    assert payload[0]["source_name"] == "https://youtube.com/@demo"
    assert payload[0]["category"] == "tech"
    assert payload[0]["tags"] == ["ai", "weekly"]
    assert payload[0]["priority"] == 80


def test_subscriptions_upsert_passes_adapter_fields(api_client: TestClient, monkeypatch) -> None:
    now = datetime.now(UTC)

    def fake_upsert_subscription(self, **kwargs):
        assert kwargs["adapter_type"] == "rss_generic"
        assert kwargs["source_url"] == "https://example.com/feed.xml"
        assert kwargs["priority"] == 90
        return (
            SimpleNamespace(
                id=uuid.uuid4(),
                platform="youtube",
                source_type="url",
                source_value="https://youtube.com/@demo",
                source_name="https://youtube.com/@demo",
                adapter_type="rss_generic",
                source_url="https://example.com/feed.xml",
                rsshub_route="https://example.com/feed.xml",
                category="ops",
                tags=["incident"],
                priority=90,
                enabled=True,
                created_at=now,
                updated_at=now,
            ),
            True,
        )

    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.upsert_subscription",
        fake_upsert_subscription,
    )

    response = api_client.post(
        "/api/v1/subscriptions",
        json={
            "platform": "youtube",
            "source_type": "url",
            "source_value": "https://youtube.com/@demo",
            "adapter_type": "rss_generic",
            "source_url": "https://example.com/feed.xml",
            "category": "ops",
            "tags": ["incident"],
            "priority": 90,
            "enabled": True,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["created"] is True
    assert payload["subscription"]["adapter_type"] == "rss_generic"
    assert payload["subscription"]["source_url"] == "https://example.com/feed.xml"
    assert payload["subscription"]["source_name"] == "https://youtube.com/@demo"
    assert payload["subscription"]["priority"] == 90


def test_subscriptions_batch_update_category_endpoint(api_client: TestClient, monkeypatch) -> None:
    def fake_batch_update(self, *, ids, category):
        assert len(ids) == 2
        assert category == "macro"
        return 2

    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.batch_update_category",
        fake_batch_update,
    )

    response = api_client.post(
        "/api/v1/subscriptions/batch-update-category",
        json={"ids": [str(uuid.uuid4()), str(uuid.uuid4())], "category": "macro"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["updated"] == 2


def test_computer_use_run_returns_required_fields(api_client: TestClient, monkeypatch) -> None:
    screenshot_b64 = base64.b64encode(b"fake-image-bytes").decode("ascii")
    monkeypatch.setattr(
        "apps.api.app.services.computer_use.ComputerUseService.run",
        lambda self, **kwargs: {
            "actions": [
                {
                    "step": 1,
                    "action": "click",
                    "target": "submit button",
                    "input_text": None,
                    "reasoning": "click submit",
                }
            ],
            "require_confirmation": True,
            "blocked_actions": ["submit"],
            "final_text": "confirmation required",
            "thought_metadata": {"provider": "gemini", "planner": "gemini_computer_use"},
        },
    )

    response = api_client.post(
        "/api/v1/computer-use/run",
        json={
            "instruction": "Open settings; click submit button",
            "screenshot_base64": screenshot_b64,
            "safety": {
                "confirm_before_execute": False,
                "blocked_actions": ["submit"],
                "max_actions": 5,
            },
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert isinstance(payload["actions"], list)
    assert payload["actions"][0]["step"] == 1
    assert payload["require_confirmation"] is True
    assert payload["blocked_actions"] == ["submit"]
    assert isinstance(payload["final_text"], str)
    assert isinstance(payload["thought_metadata"], dict)


def test_computer_use_run_rejects_invalid_screenshot_base64(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/computer-use/run",
        json={
            "instruction": "Open settings",
            "screenshot_base64": "%%%not-base64%%%",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "screenshot must be valid base64"


def test_computer_use_run_redacts_sensitive_error_detail(
    api_client: TestClient, monkeypatch
) -> None:
    screenshot_b64 = base64.b64encode(b"fake-image-bytes").decode("ascii")
    fake_token = "ghp_" + "12345678901234567890"

    def fake_run(self, **kwargs):
        raise ValueError(f"computer_use_provider_error: Bearer {fake_token}")

    monkeypatch.setattr(
        "apps.api.app.services.computer_use.ComputerUseService.run",
        fake_run,
    )

    response = api_client.post(
        "/api/v1/computer-use/run",
        json={
            "instruction": "Open settings",
            "screenshot_base64": screenshot_b64,
        },
    )
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert "Bearer ***REDACTED***" in detail
    assert fake_token not in detail


def test_job_get_infers_llm_gate_fields_from_steps_when_legacy_fields_are_null(
    api_client: TestClient,
    monkeypatch,
) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_job",
        lambda self, query_job_id: SimpleNamespace(
            id=query_job_id,
            video_id=uuid.uuid4(),
            kind="video_digest_v1",
            status="failed",
            mode="refresh_llm",
            idempotency_key="idem-legacy",
            error_message="failed",
            artifact_digest_md=None,
            artifact_root=None,
            llm_required=None,
            llm_gate_passed=None,
            hard_fail_reason=None,
            created_at=now,
            updated_at=now,
        ),
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_steps",
        lambda self, _job_id: [
            {
                "name": "llm_outline",
                "status": "succeeded",
                "attempt": 1,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "error": None,
                "error_kind": None,
                "retry_meta": None,
                "result": None,
                "cache_key": None,
            },
            {
                "name": "llm_digest",
                "status": "failed",
                "attempt": 1,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "error": {"reason": "provider_unavailable"},
                "error_kind": "upstream_error",
                "retry_meta": {"max_attempts": 2},
                "result": None,
                "cache_key": None,
            },
        ],
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_degradations", lambda self, **kwargs: []
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_artifacts_index", lambda self, **kwargs: {}
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_pipeline_final_status",
        lambda self, _job_id, fallback_status: "failed",
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_notification_retry", lambda self, _job_id: None
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["llm_required"] is True
    assert payload["llm_gate_passed"] is False
    assert payload["hard_fail_reason"] == "provider_unavailable"
    assert payload["steps"][0]["thought_metadata"] == {}


def test_job_get_infers_llm_gate_passed_true_when_llm_steps_succeed(
    api_client: TestClient,
    monkeypatch,
) -> None:
    job_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_job",
        lambda self, query_job_id: SimpleNamespace(
            id=query_job_id,
            video_id=uuid.uuid4(),
            kind="video_digest_v1",
            status="succeeded",
            mode="full",
            idempotency_key="idem-legacy-ok",
            error_message=None,
            artifact_digest_md=None,
            artifact_root=None,
            llm_required=None,
            llm_gate_passed=None,
            hard_fail_reason="legacy_reason_should_clear",
            created_at=now,
            updated_at=now,
        ),
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_steps",
        lambda self, _job_id: [
            {
                "name": "llm_outline",
                "status": "succeeded",
                "attempt": 1,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "error": None,
                "error_kind": None,
                "retry_meta": None,
                "result": None,
                "cache_key": None,
            },
            {
                "name": "llm_digest",
                "status": "skipped",
                "attempt": 1,
                "started_at": now.isoformat(),
                "finished_at": now.isoformat(),
                "error": None,
                "error_kind": None,
                "retry_meta": None,
                "result": {"degraded": False},
                "cache_key": None,
            },
        ],
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_degradations", lambda self, **kwargs: []
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_artifacts_index", lambda self, **kwargs: {}
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_pipeline_final_status",
        lambda self, _job_id, fallback_status: "succeeded",
    )
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_notification_retry", lambda self, _job_id: None
    )

    response = api_client.get(f"/api/v1/jobs/{job_id}")
    payload = response.json()

    assert response.status_code == 200
    assert payload["llm_required"] is True
    assert payload["llm_gate_passed"] is True
    assert payload["hard_fail_reason"] is None
    assert payload["steps"][0]["thought_metadata"] == {}


def test_health_providers_returns_rollup(api_client: TestClient, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "apps.api.app.services.health.HealthService.get_provider_health",
        lambda self, window_hours=24: {
            "window_hours": window_hours,
            "providers": [
                {
                    "provider": "rsshub",
                    "ok": 3,
                    "warn": 1,
                    "fail": 0,
                    "last_status": "ok",
                    "last_checked_at": now,
                    "last_error_kind": None,
                    "last_message": "ok",
                }
            ],
        },
    )

    response = api_client.get("/api/v1/health/providers?window_hours=24")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_hours"] == 24
    assert payload["providers"][0]["provider"] == "rsshub"
    assert payload["providers"][0]["ok"] == 3


def _mock_artifact_job(
    monkeypatch,
    *,
    artifact_root: str | None,
    artifact_digest_md: str | None = None,
) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_job",
        lambda self, query_job_id: SimpleNamespace(
            id=query_job_id,
            artifact_root=artifact_root,
            artifact_digest_md=artifact_digest_md,
        ),
    )


def test_artifact_assets_allows_whitelisted_meta(
    api_client: TestClient, monkeypatch, tmp_path
) -> None:
    job_id = uuid.uuid4()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "meta.json").write_text('{"ok": true}', encoding="utf-8")
    _mock_artifact_job(monkeypatch, artifact_root=str(artifact_root))

    response = api_client.get(
        "/api/v1/artifacts/assets",
        params={"job_id": str(job_id), "path": "meta"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_artifact_assets_blocks_path_traversal(
    api_client: TestClient, monkeypatch, tmp_path
) -> None:
    job_id = uuid.uuid4()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    _mock_artifact_job(monkeypatch, artifact_root=str(artifact_root))

    response = api_client.get(
        "/api/v1/artifacts/assets",
        params={"job_id": str(job_id), "path": "../secret.txt"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "artifact asset not found"


def test_artifact_assets_blocks_non_whitelisted_file(
    api_client: TestClient, monkeypatch, tmp_path
) -> None:
    job_id = uuid.uuid4()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "notes.txt").write_text("private", encoding="utf-8")
    _mock_artifact_job(monkeypatch, artifact_root=str(artifact_root))

    response = api_client.get(
        "/api/v1/artifacts/assets",
        params={"job_id": str(job_id), "path": "notes.txt"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "artifact asset not found"


def test_artifact_assets_allows_frame_image(api_client: TestClient, monkeypatch, tmp_path) -> None:
    job_id = uuid.uuid4()
    artifact_root = tmp_path / "artifacts"
    frame_dir = artifact_root / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_path = frame_dir / "frame_001.jpg"
    frame_path.write_bytes(b"\xff\xd8\xff\xd9")
    _mock_artifact_job(monkeypatch, artifact_root=str(artifact_root))

    response = api_client.get(
        "/api/v1/artifacts/assets",
        params={"job_id": str(job_id), "path": "frames/frame_001.jpg"},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"\xff\xd8")
    assert response.headers["content-type"].startswith("image/jpeg")


def test_workflows_run_returns_503_when_temporal_unavailable(
    api_client: TestClient, monkeypatch
) -> None:
    import sys
    import types

    async def fake_connect(*args, **kwargs):
        raise RuntimeError("connection refused")

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")

    class FakeClient:
        connect = staticmethod(fake_connect)

    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": False,
            "payload": {},
        },
    )

    assert response.status_code == 503
    assert "failed to connect temporal" in response.json()["detail"]


def test_workflows_run_requires_write_access_when_api_key_configured(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": False,
            "payload": {},
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "write access token required"


def test_workflows_run_rejects_when_api_key_not_configured_and_unauth_switch_disabled(
    api_client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.delenv("SOURCE_HARBOR_API_KEY", raising=False)
    monkeypatch.delenv("SOURCE_HARBOR_ALLOW_UNAUTH_WRITE", raising=False)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": False,
            "payload": {},
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "write access token required"


def test_workflows_run_cleanup_rejects_parent_traversal_path(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "cleanup",
            "run_once": True,
            "wait_for_result": False,
            "payload": {"workspace_dir": "../outside"},
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "parent traversal" in response.text


def test_subscriptions_write_endpoints_enforce_write_access(
    api_client: TestClient, monkeypatch
) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    monkeypatch.setattr(
        "apps.api.app.services.subscriptions.SubscriptionsService.upsert_subscription",
        lambda self, **kwargs: (
            SimpleNamespace(
                id=uuid.uuid4(),
                platform=kwargs["platform"],
                source_type=kwargs["source_type"],
                source_value=kwargs["source_value"],
                adapter_type=kwargs["adapter_type"],
                source_url=kwargs["source_url"],
                rsshub_route=kwargs["rsshub_route"] or "/youtube/channel/demo",
                category=kwargs["category"],
                tags=kwargs["tags"],
                priority=kwargs["priority"],
                enabled=kwargs["enabled"],
                created_at=now,
                updated_at=now,
            ),
            True,
        ),
    )

    payload = {
        "platform": "youtube",
        "source_type": "url",
        "source_value": "https://youtube.com/@demo",
        "rsshub_route": "/youtube/channel/demo",
        "enabled": True,
    }
    unauth = api_client.post("/api/v1/subscriptions", json=payload)
    forbidden = api_client.post(
        "/api/v1/subscriptions", json=payload, headers={"X-API-Key": "wrong-token"}
    )
    authorized = api_client.post(
        "/api/v1/subscriptions",
        json=payload,
        headers={"Authorization": "Bearer unit-test-token"},
    )

    assert unauth.status_code == status.HTTP_401_UNAUTHORIZED
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert authorized.status_code == status.HTTP_200_OK


def test_execution_endpoints_enforce_write_access(api_client: TestClient, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")

    async def fake_ingest_poll(self, *, subscription_id, platform, max_new_videos):
        del self, subscription_id, platform, max_new_videos
        return {
            "run_id": uuid.uuid4(),
            "workflow_id": "wf-ingest-auth",
            "status": "queued",
            "enqueued": 0,
            "candidates": [],
        }

    async def fake_process_video(self, **kwargs):
        del self, kwargs
        return {
            "job_id": uuid.uuid4(),
            "video_db_id": uuid.uuid4(),
            "video_uid": "abc123",
            "status": "queued",
            "idempotency_key": "idem-key",
            "mode": "full",
            "overrides": {},
            "force": False,
            "reused": False,
            "workflow_id": "wf-1",
        }

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.poll", fake_ingest_poll)

    async def fake_consume(self, **kwargs):
        del self
        return {
            "consumption_batch_id": uuid.uuid4(),
            "workflow_id": "consume-batch-auth",
            "status": "frozen",
            "trigger_mode": kwargs["trigger_mode"],
            "window_id": "2026-04-09@America/Los_Angeles",
            "cutoff_at": now,
            "source_item_count": 0,
            "pending_window_ids": [],
            "track_interval_minutes": 15,
            "auto_cooldown_minutes": 60,
            "cooldown_remaining_seconds": 0,
        }

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.consume", fake_consume)
    monkeypatch.setattr(
        "apps.api.app.services.videos.VideosService.process_video", fake_process_video
    )
    monkeypatch.setattr(
        "apps.api.app.services.computer_use.ComputerUseService.run",
        lambda self, **kwargs: {
            "actions": [
                {
                    "step": 1,
                    "action": "click",
                    "target": "#submit",
                    "input_text": None,
                    "reasoning": None,
                }
            ],
            "require_confirmation": True,
            "blocked_actions": [],
            "final_text": "ok",
            "thought_metadata": {},
        },
    )
    monkeypatch.setattr(
        "apps.api.app.services.ui_audit.UiAuditService.run",
        lambda self, **kwargs: {
            "run_id": "run-1",
            "job_id": None,
            "artifact_root": kwargs.get("artifact_root"),
            "status": "completed",
            "created_at": now.isoformat(),
            "summary": {"artifact_count": 0, "finding_count": 0, "severity_counts": {}},
        },
    )
    monkeypatch.setattr(
        "apps.api.app.services.ui_audit.UiAuditService.autofix",
        lambda self, **kwargs: {
            "run_id": kwargs["run_id"],
            "mode": "dry-run",
            "autofix_applied": False,
            "summary": {"finding_count": 0, "high_or_worse_count": 0},
            "guardrails": {"max_files": 1, "max_changed_lines": 10, "note": "test"},
            "suggested_actions": [],
        },
    )

    endpoints = [
        ("/api/v1/ingest/poll", {"platform": "youtube", "max_new_videos": 1}),
        (
            "/api/v1/ingest/consume",
            {"trigger_mode": "manual", "timezone_name": "America/Los_Angeles"},
        ),
        (
            "/api/v1/videos/process",
            {"video": {"platform": "youtube", "url": "https://www.youtube.com/watch?v=abc123"}},
        ),
        (
            "/api/v1/computer-use/run",
            {"instruction": "open submit button", "screenshot_base64": "ZmFrZQ=="},
        ),
        ("/api/v1/ui-audit/run", {"artifact_root": tempfile.gettempdir()}),
        (
            "/api/v1/ui-audit/run-1/autofix",
            {"mode": "dry-run", "max_files": 1, "max_changed_lines": 10},
        ),
    ]

    for path, payload in endpoints:
        unauth = api_client.post(path, json=payload)
        forbidden = api_client.post(path, json=payload, headers={"X-API-Key": "wrong-token"})
        authorized = api_client.post(
            path, json=payload, headers={"Authorization": "Bearer unit-test-token"}
        )

        assert unauth.status_code == status.HTTP_401_UNAUTHORIZED
        assert forbidden.status_code == status.HTTP_403_FORBIDDEN
        assert authorized.status_code in {
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
        }


def test_artifact_markdown_contract_switches_by_include_meta(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.jobs.JobsService.get_artifact_payload",
        lambda self, **kwargs: {"markdown": "# Digest", "meta": {"source": "test"}},
    )

    markdown_response = api_client.get(
        "/api/v1/artifacts/markdown",
        params={"job_id": str(uuid.uuid4())},
    )
    meta_response = api_client.get(
        "/api/v1/artifacts/markdown",
        params={"job_id": str(uuid.uuid4()), "include_meta": True},
    )

    assert markdown_response.status_code == status.HTTP_200_OK
    assert markdown_response.text == "# Digest"
    assert markdown_response.headers["content-type"].startswith("text/markdown")

    assert meta_response.status_code == status.HTTP_200_OK
    assert meta_response.json() == {"markdown": "# Digest", "meta": {"source": "test"}}
    assert meta_response.headers["content-type"].startswith("application/json")


def test_artifact_markdown_openapi_declares_dual_response_content(api_client: TestClient) -> None:
    openapi = api_client.get("/openapi.json").json()
    content = openapi["paths"]["/api/v1/artifacts/markdown"]["get"]["responses"]["200"]["content"]

    assert "application/json" in content
    assert "text/markdown" in content


def test_ingest_poll_maps_value_error_to_404_for_missing_resource(
    api_client: TestClient, monkeypatch
) -> None:
    async def fake_poll(self, *, subscription_id, platform, max_new_videos):
        del subscription_id, platform, max_new_videos
        raise ValueError("subscription does not exist")

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.poll", fake_poll)
    response = api_client.post(
        "/api/v1/ingest/poll", json={"platform": "youtube", "max_new_videos": 10}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "subscription does not exist"


def test_ingest_poll_maps_value_error_to_400_for_invalid_argument(
    api_client: TestClient, monkeypatch
) -> None:
    async def fake_poll(self, *, subscription_id, platform, max_new_videos):
        del subscription_id, platform, max_new_videos
        raise ValueError("invalid poll filters")

    monkeypatch.setattr("apps.api.app.services.ingest.IngestService.poll", fake_poll)
    response = api_client.post(
        "/api/v1/ingest/poll", json={"platform": "youtube", "max_new_videos": 10}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "invalid poll filters"


def test_sanitize_exception_detail_redacts_basic_userinfo_and_common_tokens() -> None:
    # Build the credential-bearing URL at runtime so secret scanners do not flag
    # this safety regression test as a committed secret.
    message = (
        "upstream failed Authorization: Basic dXNlcjpwYXNz "
        "https://alice"
        ":"
        "secret@example.com/cb?access_token=abc&id_token=def&refresh_token=ghi&jwt=xyz"
    )
    sanitized = sanitize_exception_detail(RuntimeError(message))

    assert "Basic ***REDACTED***" in sanitized
    assert "https://***:***@example.com" in sanitized
    assert "access_token=***REDACTED***" in sanitized
    assert "id_token=***REDACTED***" in sanitized
    assert "refresh_token=***REDACTED***" in sanitized
    assert "jwt=***REDACTED***" in sanitized
    assert "dXNlcjpwYXNz" not in sanitized
    assert "alice:secret" not in sanitized


def test_sanitize_exception_detail_redacts_json_like_sensitive_values() -> None:
    message = '{"password":"abc","token":"def","api_key":"ghi","secret":"jkl","safe":"ok"}'
    sanitized = sanitize_exception_detail(RuntimeError(message))

    assert '"password":***REDACTED***' in sanitized
    assert '"token":***REDACTED***' in sanitized
    assert '"api_key":***REDACTED***' in sanitized
    assert '"secret":***REDACTED***' in sanitized
    assert '"safe":"ok"' in sanitized
    assert '"password":"abc"' not in sanitized
    assert '"token":"def"' not in sanitized
    assert '"api_key":"ghi"' not in sanitized
    assert '"secret":"jkl"' not in sanitized


def test_sanitize_exception_detail_redacts_aws_access_key_prefixes() -> None:
    akia_token = "AKIA" + "0ABCDEF123456789"
    asia_token = "ASIA" + "0ABCDEF123456789"
    message = f"keys {akia_token} and {asia_token} should be hidden"
    sanitized = sanitize_exception_detail(RuntimeError(message))

    assert "AKIA***REDACTED***" in sanitized
    assert "ASIA***REDACTED***" in sanitized
    assert akia_token not in sanitized
    assert asia_token not in sanitized


def test_workflows_run_returns_already_running_when_conflict(
    api_client: TestClient, monkeypatch
) -> None:
    import sys
    import types

    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs

            class _Connected:
                async def start_workflow(self, *a, **kw):
                    del a, kw
                    raise FakeWorkflowAlreadyStartedError

            return _Connected()

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": False,
            "wait_for_result": False,
            "workflow_id": "provider-canary-workflow",
            "payload": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "already_running"
    assert payload["workflow_id"] == "provider-canary-workflow"


def test_workflows_run_maps_connect_timeout_to_504(api_client: TestClient, monkeypatch) -> None:
    import sys
    import types

    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs
            return object()

    async def _timeout_wait_for(awaitable, timeout):
        del timeout
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError("connect timeout")

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)
    monkeypatch.setattr("apps.api.app.routers.workflows.asyncio.wait_for", _timeout_wait_for)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": False,
            "payload": {},
        },
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "temporal connect timed out after 5.0s"


def test_workflows_run_maps_start_timeout_to_504(api_client: TestClient, monkeypatch) -> None:
    import sys
    import types

    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    class _Connected:
        async def start_workflow(self, *args, **kwargs):
            del args, kwargs
            return object()

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs
            return _Connected()

    call_count = {"n": 0}

    async def _start_timeout_wait_for(awaitable, timeout):
        del timeout
        call_count["n"] += 1
        if call_count["n"] == 2:
            close = getattr(awaitable, "close", None)
            if callable(close):
                close()
            raise TimeoutError("start timeout")
        return await awaitable

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)
    monkeypatch.setattr("apps.api.app.routers.workflows.asyncio.wait_for", _start_timeout_wait_for)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": False,
            "payload": {},
        },
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "temporal workflow start timed out after 10.0s"


def test_workflows_run_wait_for_result_maps_timeout_to_504(
    api_client: TestClient,
    monkeypatch,
) -> None:
    import sys
    import types

    class FakeWorkflowAlreadyStartedError(Exception):
        pass

    class _Handle:
        id = "wf-id-1"
        run_id = "run-id-1"
        first_execution_run_id = "run-id-1"

        async def result(self):
            raise TimeoutError("workflow result timeout")

    class _Connected:
        async def start_workflow(self, *args, **kwargs):
            del args, kwargs
            return _Handle()

    class FakeClient:
        @staticmethod
        async def connect(*args, **kwargs):
            del args, kwargs
            return _Connected()

    fake_temporalio = types.ModuleType("temporalio")
    fake_client_module = types.ModuleType("temporalio.client")
    fake_exceptions_module = types.ModuleType("temporalio.exceptions")
    fake_client_module.Client = FakeClient
    fake_exceptions_module.WorkflowAlreadyStartedError = FakeWorkflowAlreadyStartedError
    fake_temporalio.client = fake_client_module  # type: ignore[attr-defined]
    fake_temporalio.exceptions = fake_exceptions_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "temporalio", fake_temporalio)
    monkeypatch.setitem(sys.modules, "temporalio.client", fake_client_module)
    monkeypatch.setitem(sys.modules, "temporalio.exceptions", fake_exceptions_module)

    response = api_client.post(
        "/api/v1/workflows/run",
        json={
            "workflow": "provider_canary",
            "run_once": True,
            "wait_for_result": True,
            "payload": {},
        },
    )

    assert response.status_code == 504
    assert response.json()["detail"].startswith("workflow result timed out after ")


def test_notification_html_renderer_supports_markdown() -> None:
    from apps.api.app.services.notifications import _to_html

    html = _to_html("# 标题\n\n- 一\n- 二\n\n[链接](https://example.com)")
    assert "<h1>标题</h1>" in html
    assert "<li>一</li>" in html
    assert '<a href="https://example.com">链接</a>' in html


def test_ui_audit_run_and_get_endpoints(api_client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(tmp_path))
    artifact_root = tmp_path / "ui-audit-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    report_path = artifact_root / "playwright-axe-report.json"
    report_path.write_text(
        '{"violations":[{"id":"color-contrast","impact":"serious","help":"Color contrast","description":"Insufficient contrast"}]}',
        encoding="utf-8",
    )

    run_response = api_client.post(
        "/api/v1/ui-audit/run", json={"artifact_root": "ui-audit-artifacts"}
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "completed_with_gemini_skipped"
    assert run_payload["summary"]["artifact_count"] >= 1
    assert run_payload["summary"]["finding_count"] == 1
    assert run_payload["summary"]["severity_counts"]["high"] == 1

    run_id = run_payload["run_id"]
    from apps.api.app.services.ui_audit import UiAuditService

    with UiAuditService._store_lock:
        UiAuditService._run_store.clear()

    get_response = api_client.get(f"/api/v1/ui-audit/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json()["run_id"] == run_id

    findings_response = api_client.get(f"/api/v1/ui-audit/{run_id}/findings")
    assert findings_response.status_code == 200
    findings_payload = findings_response.json()
    assert findings_payload["items"][0]["rule"] == "color-contrast"
    assert findings_payload["items"][0]["severity"] == "high"

    artifacts_response = api_client.get(f"/api/v1/ui-audit/{run_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifacts_payload = artifacts_response.json()
    assert artifacts_payload["items"][0]["key"] == "playwright-axe-report.json"


def test_ui_audit_get_artifact_returns_base64(
    api_client: TestClient, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(tmp_path))
    artifact_root = tmp_path / "ui-audit-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    report_path = artifact_root / "playwright-log.json"
    report_path.write_text(
        '{"findings":[{"id":"f-1","severity":"low","title":"Sample","message":"ok"}]}',
        encoding="utf-8",
    )

    run_response = api_client.post(
        "/api/v1/ui-audit/run", json={"artifact_root": "ui-audit-artifacts"}
    )
    run_id = run_response.json()["run_id"]

    response = api_client.get(
        f"/api/v1/ui-audit/{run_id}/artifact",
        params={"key": "playwright-log.json", "include_base64": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["exists"] is True
    assert isinstance(payload["base64"], str)


def test_ui_audit_run_includes_gemini_review_findings(
    api_client: TestClient, monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(tmp_path))
    artifact_root = tmp_path / "ui-audit-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "playwright-axe-report.json").write_text(
        '{"violations":[{"id":"color-contrast","impact":"serious","help":"Color contrast","description":"Insufficient contrast"}]}',
        encoding="utf-8",
    )
    (artifact_root / "ui-home.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setenv("UI_AUDIT_GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "high")

    class _FakeModels:
        def generate_content(self, **kwargs):
            del kwargs
            return types.SimpleNamespace(
                text='{"overall_assessment":"Buttons are usable but spacing is inconsistent.","findings":[{"severity":"medium","title":"Inconsistent spacing","message":"Primary CTA spacing differs across panels.","artifact_key":"ui-home.png","rule":"layout-consistency"}],"suggested_actions":["Align spacing tokens for CTA containers."]}'
            )

    class _FakeClient:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self.models = _FakeModels()

    class _FakePart:
        @staticmethod
        def from_bytes(*, data, mime_type):
            return {"mime_type": mime_type, "size": len(data)}

    class _FakeTypes:
        Part = _FakePart

        class GenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class ThinkingConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.Client = _FakeClient
    fake_genai_module.types = _FakeTypes

    fake_google_module = types.ModuleType("google")
    fake_google_module.genai = fake_genai_module

    monkeypatch.setitem(sys.modules, "google", fake_google_module)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_module)

    run_response = api_client.post(
        "/api/v1/ui-audit/run", json={"artifact_root": "ui-audit-artifacts"}
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "completed"
    assert run_payload["summary"]["finding_count"] >= 2

    run_id = run_payload["run_id"]
    findings_response = api_client.get(f"/api/v1/ui-audit/{run_id}/findings")
    assert findings_response.status_code == 200
    findings = findings_response.json()["items"]
    assert any(item["rule"] == "layout-consistency" for item in findings)
    assert any(item["rule"] == "gemini-overall-assessment" for item in findings)

    autofix_response = api_client.post(
        f"/api/v1/ui-audit/{run_id}/autofix",
        json={"mode": "dry-run", "max_files": 2, "max_changed_lines": 80},
    )
    assert autofix_response.status_code == 200
    assert (
        "Align spacing tokens for CTA containers." in autofix_response.json()["suggested_actions"]
    )


def test_ui_audit_autofix_endpoint_returns_summary(
    api_client: TestClient, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    monkeypatch.setenv("UI_AUDIT_ARTIFACT_BASE_ROOT", str(tmp_path))
    artifact_root = tmp_path / "ui-audit-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    report_path = artifact_root / "playwright-axe-report.json"
    report_path.write_text(
        '{"violations":[{"id":"color-contrast","impact":"serious","help":"Color contrast","description":"Insufficient contrast"}]}',
        encoding="utf-8",
    )

    run_response = api_client.post(
        "/api/v1/ui-audit/run", json={"artifact_root": "ui-audit-artifacts"}
    )
    run_id = run_response.json()["run_id"]

    response = api_client.post(
        f"/api/v1/ui-audit/{run_id}/autofix",
        json={"mode": "dry-run", "max_files": 2, "max_changed_lines": 80},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == run_id
    assert payload["mode"] == "dry-run"
    assert payload["autofix_applied"] is False
    assert payload["summary"]["finding_count"] == 1
    assert payload["summary"]["high_or_worse_count"] == 1
    assert payload["guardrails"]["max_files"] == 2
    assert payload["guardrails"]["max_changed_lines"] == 80
    assert payload["guardrails"]["requested_mode"] == "dry-run"
    assert payload["guardrails"]["effective_mode"] == "dry-run"
    assert isinstance(payload["suggested_actions"], list)


def test_ui_audit_autofix_apply_request_returns_honest_dry_run_mode(
    api_client: TestClient, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    artifact_root = tmp_path / "ui-audit-artifacts"
    artifact_root.mkdir(parents=True, exist_ok=True)
    (artifact_root / "playwright-axe-report.json").write_text(
        '{"violations":[{"id":"color-contrast","impact":"serious","help":"Color contrast","description":"Insufficient contrast"}]}',
        encoding="utf-8",
    )

    run_response = api_client.post(
        "/api/v1/ui-audit/run", json={"artifact_root": str(artifact_root)}
    )
    run_id = run_response.json()["run_id"]

    response = api_client.post(
        f"/api/v1/ui-audit/{run_id}/autofix",
        json={"mode": "apply", "max_files": 2, "max_changed_lines": 80},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "dry-run"
    assert payload["autofix_applied"] is False
    assert payload["guardrails"]["requested_mode"] == "apply"
    assert payload["guardrails"]["effective_mode"] == "dry-run"
    assert "not supported yet" in payload["guardrails"]["note"]


def test_ui_audit_autofix_endpoint_returns_404_for_missing_run(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/ui-audit/missing-run/autofix",
        json={"mode": "dry-run", "max_files": 3, "max_changed_lines": 120},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "ui audit run not found"


def test_ui_audit_read_endpoints_require_write_access_when_api_key_configured(
    api_client: TestClient, monkeypatch, tmp_path
) -> None:
    from apps.api.app.services.ui_audit import UiAuditService

    monkeypatch.setenv("SOURCE_HARBOR_API_KEY", "unit-test-token")
    monkeypatch.setenv("UI_AUDIT_RUN_STORE_DIR", str(tmp_path / "ui-audit-runs"))
    service = UiAuditService()
    service._save_run(  # noqa: SLF001
        {
            "run_id": "secured-run",
            "status": "completed",
            "created_at": datetime.now(UTC).isoformat(),
            "summary": {"artifact_count": 0, "finding_count": 0, "severity_counts": {}},
            "findings": [],
            "artifacts": [],
        }
    )

    for path in (
        "/api/v1/ui-audit/secured-run",
        "/api/v1/ui-audit/secured-run/findings",
        "/api/v1/ui-audit/secured-run/artifacts",
        "/api/v1/ui-audit/secured-run/artifact?key=missing",
    ):
        response = api_client.get(path)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "write access token required"

    authorized = api_client.get(
        "/api/v1/ui-audit/secured-run",
        headers={"X-API-Key": "unit-test-token"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["run_id"] == "secured-run"

    for path, detail in (
        ("/api/v1/ui-audit/missing-run", "ui audit run not found"),
        ("/api/v1/ui-audit/missing-run/findings", "ui audit run not found"),
        ("/api/v1/ui-audit/missing-run/artifacts", "ui audit run not found"),
        ("/api/v1/ui-audit/secured-run/artifact?key=missing", "ui audit artifact not found"),
    ):
        response = api_client.get(path, headers={"X-API-Key": "unit-test-token"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == detail
