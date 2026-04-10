from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from apps.api.app.services.reader_pipeline import ReaderPipelineService


class _DummyDb:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, _obj) -> None:
        return None

    def add(self, _obj) -> None:
        return None


class _BatchRepoStub:
    def __init__(self, batch) -> None:
        self.batch = batch
        self.marked_judged: list[dict[str, object]] = []

    def get_with_items(self, *, batch_id):
        return self.batch if batch_id == self.batch.id else None

    def mark_judged(self, **kwargs):
        self.marked_judged.append(dict(kwargs))
        return self.batch


class _ManifestRepoStub:
    def __init__(self) -> None:
        self.instance = None

    def get_by_batch_id(self, *, consumption_batch_id):
        if self.instance and self.instance.consumption_batch_id == consumption_batch_id:
            return self.instance
        return None

    def upsert_for_batch(self, **kwargs):
        self.instance = SimpleNamespace(
            id=uuid.uuid4(),
            consumption_batch_id=kwargs["consumption_batch_id"],
            window_id=kwargs["window_id"],
            status=kwargs["status"],
            manifest_json=kwargs["manifest_json"],
            source_item_count=kwargs["source_item_count"],
            cluster_count=kwargs["cluster_count"],
            singleton_count=kwargs["singleton_count"],
            summary_markdown=kwargs["summary_markdown"],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return self.instance


class _PublishedRepoStub:
    def __init__(self) -> None:
        self.documents: list[SimpleNamespace] = []

    def list_current(self, *, limit=20, window_id=None):
        items = [item for item in self.documents if bool(getattr(item, "is_current", False))]
        if window_id is not None:
            items = [item for item in items if item.window_id == window_id]
        return items[:limit]

    def get(self, *, document_id):
        for item in self.documents:
            if item.id == document_id:
                return item
        return None

    def get_by_slug(self, *, slug):
        for item in self.documents:
            if item.slug == slug:
                return item
        return None

    def get_current_by_stable_key(self, *, stable_key):
        current = [
            item
            for item in self.documents
            if item.stable_key == stable_key and bool(item.is_current)
        ]
        current.sort(key=lambda item: int(getattr(item, "version", 0) or 0), reverse=True)
        return current[0] if current else None

    def replace_current(self, **kwargs):
        previous = self.get_current_by_stable_key(stable_key=kwargs["stable_key"])
        version = int(getattr(previous, "version", 0) or 0) + 1
        if previous is not None:
            previous.is_current = False
        document = SimpleNamespace(
            id=uuid.uuid4(),
            stable_key=kwargs["stable_key"],
            slug=kwargs["slug"],
            window_id=kwargs["window_id"],
            topic_key=kwargs["topic_key"],
            topic_label=kwargs["topic_label"],
            title=kwargs["title"],
            summary=kwargs["summary"],
            markdown=kwargs["markdown"],
            reader_output_locale=kwargs["reader_output_locale"],
            reader_style_profile=kwargs["reader_style_profile"],
            materialization_mode=kwargs["materialization_mode"],
            version=version,
            published_with_gap=kwargs["published_with_gap"],
            is_current=True,
            source_item_count=kwargs["source_item_count"],
            consumption_batch_id=kwargs["consumption_batch_id"],
            cluster_verdict_manifest_id=kwargs["cluster_verdict_manifest_id"],
            supersedes_document_id=getattr(previous, "id", None),
            warning_json=dict(kwargs["warning_json"]),
            coverage_ledger_json=dict(kwargs["coverage_ledger_json"]),
            traceability_pack_json=dict(kwargs["traceability_pack_json"]),
            source_refs_json=list(kwargs["source_refs_json"]),
            sections_json=list(kwargs["sections_json"]),
            repair_history_json=list(kwargs["repair_history_json"]),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.documents.append(document)
        return document


class _JobsServiceStub:
    def __init__(self, digest_map, cards_map, bundle_map=None) -> None:
        self.digest_map = digest_map
        self.cards_map = cards_map
        self.bundle_map = bundle_map or {}

    def get_artifact_digest_md(self, *, job_id, video_url):
        del video_url
        return self.digest_map.get(job_id)

    def get_knowledge_cards(self, *, job_id):
        return self.cards_map.get(job_id, [])

    def build_evidence_bundle(self, *, job_id):
        return self.bundle_map.get(job_id) or {
            "job": {"pipeline_final_status": "succeeded"},
            "trace_summary": {"degradations": []},
            "bundle_route": f"/api/v1/jobs/{job_id}/bundle",
        }


def _build_service(*, batch, digest_map, cards_map, bundle_map=None):
    service = ReaderPipelineService.__new__(ReaderPipelineService)
    service.db = _DummyDb()
    service.batch_repo = _BatchRepoStub(batch)
    service.manifest_repo = _ManifestRepoStub()
    service.document_repo = _PublishedRepoStub()
    service.jobs_service = _JobsServiceStub(digest_map, cards_map, bundle_map=bundle_map)
    return service


def _sample_batch() -> tuple[
    SimpleNamespace, dict[uuid.UUID, str], dict[uuid.UUID, list[dict[str, str]]]
]:
    batch_id = uuid.uuid4()
    job_one = uuid.uuid4()
    job_two = uuid.uuid4()
    job_three = uuid.uuid4()
    now = datetime(2026, 4, 9, 8, 30, tzinfo=UTC)
    batch = SimpleNamespace(
        id=batch_id,
        window_id="2026-04-09@America/Los_Angeles",
        items=[
            SimpleNamespace(
                id=uuid.uuid4(),
                ingest_run_item_id=uuid.uuid4(),
                job_id=job_one,
                platform="youtube",
                source_origin="subscription_tracked",
                content_type="video",
                title="Agents recap",
                source_url="https://example.com/agents-1",
                published_at=now,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                ingest_run_item_id=uuid.uuid4(),
                job_id=job_two,
                platform="bilibili",
                source_origin="manual_injected",
                content_type="video",
                title="Agents follow-up",
                source_url="https://example.com/agents-2",
                published_at=now,
            ),
            SimpleNamespace(
                id=uuid.uuid4(),
                ingest_run_item_id=uuid.uuid4(),
                job_id=job_three,
                platform="youtube",
                source_origin="subscription_tracked",
                content_type="video",
                title="Databases weekly",
                source_url="https://example.com/db",
                published_at=now,
            ),
        ],
    )
    digest_map = {
        job_one: "# Digest\n\nAgents one preview",
        job_two: "# Digest\n\nAgents two preview",
        job_three: "# Digest\n\nDatabases preview",
    }
    cards_map = {
        job_one: [{"topic_key": "ai-agents", "topic_label": "AI Agents", "claim_kind": "summary"}],
        job_two: [{"topic_key": "ai-agents", "topic_label": "AI Agents", "claim_kind": "change"}],
        job_three: [{"topic_key": "postgres", "topic_label": "Postgres", "claim_kind": "summary"}],
    }
    return batch, digest_map, cards_map


def test_judge_batch_groups_shared_topics_and_keeps_singletons() -> None:
    batch, digest_map, cards_map = _sample_batch()
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)

    payload = service.judge_batch(batch_id=batch.id)

    assert payload["consumption_batch_id"] == str(batch.id)
    assert payload["cluster_count"] == 1
    assert payload["singleton_count"] == 1
    cluster = payload["manifest"]["clusters"][0]
    assert cluster["topic_key"] == "ai-agents"
    assert cluster["decision"] == "merge_then_polish"
    assert len(cluster["source_item_ids"]) == 2
    singleton = payload["manifest"]["singletons"][0]
    assert singleton["decision"] == "polish_only"
    assert singleton["topic_key"] == "postgres"


def test_materialize_batch_creates_cluster_and_singleton_documents() -> None:
    batch, digest_map, cards_map = _sample_batch()
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)

    payload = service.materialize_batch(batch_id=batch.id)

    assert payload["consumption_batch_id"] == str(batch.id)
    assert payload["published_document_count"] == 2
    modes = sorted(item["materialization_mode"] for item in payload["documents"])
    assert modes == ["merge_then_polish", "polish_only"]
    merge_doc = next(
        item for item in payload["documents"] if item["materialization_mode"] == "merge_then_polish"
    )
    assert isinstance(merge_doc["published_with_gap"], bool)
    assert merge_doc["coverage_ledger"]["status"] == "pass"
    assert merge_doc["coverage_ledger"]["published_doc_id"] == merge_doc["id"]
    assert merge_doc["traceability_pack"]["status"] == "ready"
    assert merge_doc["traceability_pack"]["published_doc_id"] == merge_doc["id"]
    assert merge_doc["traceability_pack"]["stable_key"] == merge_doc["stable_key"]
    assert merge_doc["traceability_pack"]["version"] == merge_doc["version"]
    assert isinstance(merge_doc["traceability_pack"]["source_items"], list)
    assert len(merge_doc["source_refs"]) == 2


def test_reader_pipeline_getters_navigation_and_warning_helpers_cover_tail_paths() -> None:
    batch, digest_map, cards_map = _sample_batch()
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)
    payload = service.materialize_batch(batch_id=batch.id)
    document = payload["documents"][0]

    assert service.list_documents(limit=5)[0]["id"] == document["id"]
    assert service.get_navigation_brief(limit=1)["document_count"] == 1
    assert service.get_document(document_id=uuid.UUID(document["id"]))["slug"] == document["slug"]
    assert service.get_document_by_slug(slug=document["slug"])["id"] == document["id"]
    assert service.get_published_document_by_slug(slug="missing") is None
    assert service.build_navigation_brief(window_id=None, limit=0)["window_id"]

    coverage_ledger = {
        "status": "gap_detected",
        "gap_reasons": ["missing_topics"],
        "entries": [
            {
                "source_item_id": "item-1",
                "status": "gap_detected",
                "missing_digest": True,
            }
        ],
    }
    warning = service._build_warning_json(
        coverage_ledger=coverage_ledger,
        traceability_pack={"status": "incomplete"},
    )
    assert warning["published_with_gap"] is True
    assert "missing digest output" in " ".join(warning["reasons"])

    assert service._digest_preview(None, fallback="fallback") == "fallback"
    assert service._digest_preview("# Title", fallback="fallback") == "# Title"
    assert (
        service._isoformat(datetime(2026, 4, 9, 8, 0))
        == datetime(2026, 4, 9, 8, 0, tzinfo=UTC).isoformat()
    )
    assert service._isoformat("bad") is None


def test_reader_pipeline_repair_document_handles_patch_section_cluster_and_errors() -> None:
    batch, digest_map, cards_map = _sample_batch()
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)
    materialized = service.materialize_batch(batch_id=batch.id)
    document = service.document_repo.documents[0]

    patch_payload = service.repair_document(document_id=document.id, repair_mode="patch")
    assert patch_payload["materialization_mode"] == "repair_patch"

    section_payload = service.repair_document(document_id=document.id, repair_mode="section")
    assert section_payload["materialization_mode"] == "repair_section"

    cluster_payload = service.repair_document(document_id=document.id, repair_mode="cluster")
    assert cluster_payload["stable_key"] == materialized["documents"][0]["stable_key"]

    document_without_batch = service.document_repo.documents[-1]
    document_without_batch.consumption_batch_id = None
    with pytest.raises(ValueError, match="cluster repair requires consumption batch context"):
        service.repair_document(document_id=document_without_batch.id, repair_mode="cluster")

    document_without_refs = service.document_repo.documents[-1]
    document_without_refs.source_refs_json = []
    with pytest.raises(ValueError, match="no source refs"):
        service.repair_document(document_id=document_without_refs.id, repair_mode="patch")

    with pytest.raises(ValueError, match="must be one of"):
        service.repair_document(document_id=document.id, repair_mode="invalid")

    with pytest.raises(ValueError, match="published reader document not found"):
        service.repair_document(document_id=uuid.uuid4(), repair_mode="patch")


def test_materialize_batch_marks_document_with_gap_when_digest_is_missing() -> None:
    batch_id = uuid.uuid4()
    job_id = uuid.uuid4()
    now = datetime(2026, 4, 9, 8, 30, tzinfo=UTC)
    batch = SimpleNamespace(
        id=batch_id,
        window_id="2026-04-09@America/Los_Angeles",
        items=[
            SimpleNamespace(
                id=uuid.uuid4(),
                ingest_run_item_id=uuid.uuid4(),
                job_id=job_id,
                platform="youtube",
                source_origin="manual_injected",
                content_type="video",
                title="Broken source",
                source_url="https://example.com/broken",
                published_at=now,
            ),
        ],
    )
    service = _build_service(
        batch=batch,
        digest_map={job_id: None},
        cards_map={job_id: []},
        bundle_map={
            job_id: {
                "job": {"pipeline_final_status": "succeeded"},
                "trace_summary": {"degradations": []},
            }
        },
    )

    payload = service.materialize_batch(batch_id=batch_id)

    document = payload["documents"][0]
    assert document["published_with_gap"] is True
    assert document["warning"]["warning_kind"] == "coverage_gap"
    assert document["warning"]["published_with_gap"] is True
    assert document["warning"]["missing_digest_count"] == 1
    assert document["coverage_ledger"]["status"] == "gap_detected"


def test_repair_document_creates_new_version_with_history() -> None:
    batch, digest_map, cards_map = _sample_batch()
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)
    created = service.materialize_batch(batch_id=batch.id)
    document_id = next(
        item["id"] for item in created["documents"] if item["materialization_mode"] == "polish_only"
    )

    repaired = service.repair_document(
        document_id=uuid.UUID(document_id),
        repair_mode="section",
    )

    assert repaired["version"] == 2
    assert repaired["materialization_mode"] == "repair_section"
    assert repaired["stable_key"].startswith("topic-postgres") or repaired["stable_key"].startswith(
        "item-"
    )
    assert repaired["repair_history"][0]["repair_mode"] == "section"


def test_materialize_batch_marks_published_with_gap_when_digest_is_missing() -> None:
    batch, digest_map, cards_map = _sample_batch()
    missing_job_id = batch.items[0].job_id
    digest_map = dict(digest_map)
    digest_map[missing_job_id] = None
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)

    payload = service.materialize_batch(batch_id=batch.id)

    merge_doc = next(
        item for item in payload["documents"] if item["materialization_mode"] == "merge_then_polish"
    )
    assert merge_doc["published_with_gap"] is True
    assert merge_doc["warning"]["warning_kind"] == "coverage_gap"
    assert merge_doc["warning"]["missing_digest_count"] == 1
    assert "missing digest" in " ".join(merge_doc["warning"]["reasons"])
    assert payload["published_with_gap_count"] >= 1


def test_judge_batch_raises_for_missing_batch() -> None:
    batch, digest_map, cards_map = _sample_batch()
    service = _build_service(batch=batch, digest_map=digest_map, cards_map=cards_map)

    try:
        service.judge_batch(batch_id=uuid.uuid4())
    except ValueError as exc:
        assert str(exc) == "consumption batch not found"
    else:
        raise AssertionError("expected ValueError")
