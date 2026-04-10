from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.allow_unauth_write


def _sample_document_payload(now: datetime, *, batch_id: uuid.UUID) -> dict[str, object]:
    document_id = str(uuid.uuid4())
    return {
        "id": document_id,
        "stable_key": "topic-ai-agents-2026-04-09",
        "slug": "ai-agents-2026-04-09-v1",
        "window_id": "2026-04-09@America/Los_Angeles",
        "topic_key": "ai-agents",
        "topic_label": "AI Agents",
        "title": "AI Agents",
        "summary": "Merged reader doc",
        "markdown": "# AI Agents\n\nMerged reader doc",
        "reader_output_locale": "zh-CN",
        "reader_style_profile": "briefing",
        "materialization_mode": "merge_then_polish",
        "version": 1,
        "published_with_gap": False,
        "is_current": True,
        "source_item_count": 2,
        "consumption_batch_id": str(batch_id),
        "cluster_verdict_manifest_id": str(uuid.uuid4()),
        "supersedes_document_id": None,
        "warning": {},
        "coverage_ledger": {"status": "pass"},
        "traceability_pack": {"status": "ready"},
        "source_refs": [],
        "sections": [],
        "repair_history": [],
        "created_at": now,
        "updated_at": now,
    }


def test_reader_batch_judge_route_returns_manifest(api_client, monkeypatch) -> None:
    batch_id = uuid.uuid4()
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.judge_batch",
        lambda self, *, batch_id: {
            "id": str(uuid.uuid4()),
            "consumption_batch_id": str(batch_id),
            "window_id": "2026-04-09@America/Los_Angeles",
            "status": "ready",
            "source_item_count": 2,
            "cluster_count": 1,
            "singleton_count": 0,
            "summary_markdown": "# Manifest",
            "manifest": {
                "manifest_kind": "sourceharbor_cluster_verdict_manifest_v1",
                "generated_at": now.isoformat(),
                "consumption_batch_id": str(batch_id),
                "window_id": "2026-04-09@America/Los_Angeles",
                "status": "ready",
                "source_item_count": 2,
                "cluster_count": 1,
                "singleton_count": 0,
                "clusters": [
                    {
                        "cluster_id": "cluster-ai-agents",
                        "cluster_key": "topic:ai-agents",
                        "topic_key": "ai-agents",
                        "topic_label": "AI Agents",
                        "decision": "merge_then_polish",
                        "source_item_count": 2,
                        "source_item_ids": ["item-1", "item-2"],
                        "job_ids": ["job-1", "job-2"],
                        "platforms": ["youtube"],
                        "claim_kinds": ["summary"],
                        "headline": "AI Agents",
                        "digest_preview": "preview",
                        "members": [],
                    }
                ],
                "singletons": [],
            },
            "created_at": now,
            "updated_at": now,
        },
    )

    response = api_client.post(f"/api/v1/reader/batches/{batch_id}/judge")

    assert response.status_code == 201
    payload = response.json()
    assert payload["consumption_batch_id"] == str(batch_id)
    assert payload["cluster_count"] == 1
    assert payload["manifest"]["clusters"][0]["decision"] == "merge_then_polish"


def test_reader_batch_materialize_route_returns_documents(api_client, monkeypatch) -> None:
    batch_id = uuid.uuid4()
    now = datetime.now(UTC)
    document = _sample_document_payload(now, batch_id=batch_id)

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.materialize_batch",
        lambda self, *, batch_id, reader_output_locale="zh-CN", reader_style_profile="briefing": {
            "consumption_batch_id": str(batch_id),
            "cluster_verdict_manifest_id": str(uuid.uuid4()),
            "window_id": "2026-04-09@America/Los_Angeles",
            "published_document_count": 1,
            "published_with_gap_count": 0,
            "documents": [document],
            "navigation_brief": {
                "brief_kind": "sourceharbor_navigation_brief_v1",
                "generated_at": now.isoformat(),
                "window_id": "2026-04-09@America/Los_Angeles",
                "document_count": 1,
                "published_with_gap_count": 0,
                "summary": "Read 1 published reader documents.",
                "items": [],
            },
        },
    )

    response = api_client.post(f"/api/v1/reader/batches/{batch_id}/materialize")

    assert response.status_code == 201
    payload = response.json()
    assert payload["published_document_count"] == 1
    assert payload["documents"][0]["slug"] == "ai-agents-2026-04-09-v1"


def test_reader_documents_routes_return_list_and_detail(api_client, monkeypatch) -> None:
    batch_id = uuid.uuid4()
    now = datetime.now(UTC)
    document = _sample_document_payload(now, batch_id=batch_id)

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.list_published_documents",
        lambda self, *, limit, window_id=None: [document],
    )
    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.get_published_document_by_slug",
        lambda self, *, slug: document if slug == document["slug"] else None,
    )
    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.get_published_document",
        lambda self, *, document_id: document if str(document_id) == document["id"] else None,
    )

    list_response = api_client.get("/api/v1/reader/documents")
    slug_response = api_client.get(f"/api/v1/reader/documents/slug/{document['slug']}")
    assert list_response.status_code == 200
    assert list_response.json()[0]["stable_key"] == "topic-ai-agents-2026-04-09"
    assert slug_response.status_code == 200
    assert slug_response.json()["slug"] == document["slug"]

    detail_response = api_client.get(f"/api/v1/reader/documents/{document['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "AI Agents"


def test_reader_document_repair_route_returns_new_version(api_client, monkeypatch) -> None:
    batch_id = uuid.uuid4()
    now = datetime.now(UTC)
    document = {
        **_sample_document_payload(now, batch_id=batch_id),
        "version": 2,
        "materialization_mode": "repair_section",
        "repair_history": [{"strategy": "section"}],
    }

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.repair_document",
        lambda self, *, document_id, repair_mode, section_ids=None, strategy=None: (
            document if str(document_id) and repair_mode == "section" else None
        ),
    )

    response = api_client.post(
        f"/api/v1/reader/documents/{document['id']}/repair",
        json={"repair_mode": "section", "section_ids": []},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["version"] == 2
    assert payload["materialization_mode"] == "repair_section"
    assert payload["repair_history"][0]["strategy"] == "section"


def test_reader_navigation_brief_route_returns_payload(api_client, monkeypatch) -> None:
    now = datetime.now(UTC)
    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.build_navigation_brief",
        lambda self, *, window_id=None, limit=8: {
            "brief_kind": "sourceharbor_navigation_brief_v1",
            "generated_at": now.isoformat(),
            "window_id": window_id or "2026-04-09@America/Los_Angeles",
            "document_count": 1,
            "published_with_gap_count": 1,
            "summary": "Read 1 published reader documents.",
            "items": [{"document_id": str(uuid.uuid4()), "title": "AI Agents"}],
        },
    )

    response = api_client.get("/api/v1/reader/navigation-brief")

    assert response.status_code == 200
    payload = response.json()
    assert payload["brief_kind"] == "sourceharbor_navigation_brief_v1"
    assert payload["document_count"] == 1


def test_reader_batch_manifest_route_returns_404_when_missing(api_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.get_manifest",
        lambda self, *, batch_id: None,
    )

    response = api_client.get(f"/api/v1/reader/batches/{uuid.uuid4()}/manifest")

    assert response.status_code == 404
    assert response.json()["detail"] == "cluster verdict manifest not found"


def test_reader_batch_routes_map_value_errors_and_manifest_payload(api_client, monkeypatch) -> None:
    now = datetime.now(UTC)

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.judge_batch",
        lambda self, *, batch_id: (_ for _ in ()).throw(ValueError("consumption batch not found")),
    )
    missing_response = api_client.post(f"/api/v1/reader/batches/{uuid.uuid4()}/judge")
    assert missing_response.status_code == 404

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.judge_batch",
        lambda self, *, batch_id: (_ for _ in ()).throw(
            ValueError("consumption batch has no items")
        ),
    )
    invalid_response = api_client.post(f"/api/v1/reader/batches/{uuid.uuid4()}/judge")
    assert invalid_response.status_code == 400

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.get_manifest",
        lambda self, *, batch_id: type(
            "_Manifest",
            (),
            {
                "id": uuid.uuid4(),
                "consumption_batch_id": batch_id,
                "window_id": "2026-04-09@America/Los_Angeles",
                "status": "ready",
                "source_item_count": 2,
                "cluster_count": 1,
                "singleton_count": 1,
                "summary_markdown": "# Manifest",
                "manifest_json": {
                    "manifest_kind": "sourceharbor_cluster_verdict_manifest_v1",
                    "generated_at": now.isoformat(),
                    "consumption_batch_id": str(batch_id),
                    "window_id": "2026-04-09@America/Los_Angeles",
                    "status": "ready",
                    "source_item_count": 2,
                    "cluster_count": 1,
                    "singleton_count": 1,
                    "clusters": [],
                    "singletons": [],
                },
                "created_at": now,
                "updated_at": now,
            },
        )(),
    )
    manifest_response = api_client.get(f"/api/v1/reader/batches/{uuid.uuid4()}/manifest")
    assert manifest_response.status_code == 200
    assert manifest_response.json()["manifest"]["clusters"] == []


def test_reader_document_routes_handle_missing_and_repair_errors(api_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.get_published_document_by_slug",
        lambda self, *, slug: None,
    )
    slug_response = api_client.get("/api/v1/reader/documents/slug/missing")
    assert slug_response.status_code == 404

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.get_published_document",
        lambda self, *, document_id: None,
    )
    document_response = api_client.get(f"/api/v1/reader/documents/{uuid.uuid4()}")
    assert document_response.status_code == 404

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.repair_document",
        lambda self, **kwargs: (_ for _ in ()).throw(
            ValueError("published reader document not found")
        ),
    )
    missing_repair = api_client.post(
        f"/api/v1/reader/documents/{uuid.uuid4()}/repair",
        json={"repair_mode": "patch", "section_ids": []},
    )
    assert missing_repair.status_code == 404

    monkeypatch.setattr(
        "apps.api.app.services.reader_pipeline.ReaderPipelineService.repair_document",
        lambda self, **kwargs: (_ for _ in ()).throw(
            ValueError("repair strategy must be one of: patch, section, cluster")
        ),
    )
    invalid_repair = api_client.post(
        f"/api/v1/reader/documents/{uuid.uuid4()}/repair",
        json={"repair_mode": "patch", "section_ids": []},
    )
    assert invalid_repair.status_code == 400
