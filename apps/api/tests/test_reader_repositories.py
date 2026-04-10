from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from apps.api.app.models import ConsumptionBatch, IngestRun, IngestRunItem, PublishedReaderDocument
from apps.api.app.models.consumption_batch import ConsumptionBatchItem
from apps.api.app.repositories.consumption_batches import ConsumptionBatchesRepository
from apps.api.app.repositories.published_reader_documents import (
    PublishedReaderDocumentsRepository,
)


class _ScalarResult:
    def __init__(self, items):
        self._items = list(items)

    def all(self):
        return list(self._items)


class _FakeDb:
    def __init__(self) -> None:
        self.execute_rows = []
        self.scalar_queue = []
        self.scalars_items = []
        self.get_map = {}
        self.added = []
        self.flushed = 0
        self.commits = 0
        self.refreshed = []

    def execute(self, _stmt):
        return SimpleNamespace(all=lambda: list(self.execute_rows))

    def scalar(self, _stmt):
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        return None

    def scalars(self, _stmt):
        return _ScalarResult(self.scalars_items)

    def get(self, model, key):
        return self.get_map.get((model, key))

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed += 1
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj) -> None:
        self.refreshed.append(obj)


def test_consumption_batches_repository_covers_pending_batch_and_lifecycle() -> None:
    now = datetime(2026, 4, 9, 12, 0, tzinfo=UTC)
    run = IngestRun(status="succeeded")
    item = IngestRunItem(
        id=uuid.uuid4(),
        ingest_run_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        ingest_event_id=uuid.uuid4(),
        platform="youtube",
        video_uid="abc",
        source_url="https://www.youtube.com/watch?v=abc",
        title="Hello",
        published_at=now,
        entry_hash="hash-1",
        pipeline_mode="full",
        content_type="video",
        item_status="pending_consume",
    )
    item.created_at = now
    run.filters_json = {"platform": "youtube"}
    db = _FakeDb()
    db.execute_rows = [(item, run)]
    db.get_map[(IngestRunItem, item.id)] = item
    repo = ConsumptionBatchesRepository(db)

    pending = repo.list_pending_items(subscription_id=item.subscription_id, platform="youtube")
    assert pending[0]["job_id"] == item.job_id
    assert pending[0]["filters_json"] == {"platform": "youtube"}

    batch = repo.create_batch(
        trigger_mode="manual",
        window_id="2026-04-09@America/Los_Angeles",
        timezone_name="America/Los_Angeles",
        cutoff_at=now,
        requested_by="tester",
        requested_trace_id="trace-1",
        filters_json={"platform": "youtube"},
        base_published_doc_versions=[],
        items=[
            {
                "ingest_run_item_id": item.id,
                "subscription_id": item.subscription_id,
                "video_id": item.video_id,
                "job_id": item.job_id,
                "ingest_event_id": item.ingest_event_id,
                "platform": item.platform,
                "video_uid": item.video_uid,
                "source_url": item.source_url,
                "title": item.title,
                "published_at": item.published_at,
                "source_effective_at": now,
                "discovered_at": now,
                "entry_hash": item.entry_hash,
                "pipeline_mode": item.pipeline_mode,
                "content_type": item.content_type,
                "source_origin": "subscription_tracked",
            }
        ],
    )

    assert batch.status == "frozen"
    assert batch.source_item_count == 1
    batch_items = [obj for obj in db.added if isinstance(obj, ConsumptionBatchItem)]
    assert len(batch_items) == 1
    assert item.item_status == "batch_assigned"
    batch.items = batch_items

    db.get_map[(ConsumptionBatch, batch.id)] = batch
    repo.mark_workflow_started(batch_id=batch.id, workflow_id="wf-1")
    repo.mark_materialized(batch_id=batch.id, process_results=[{"ok": True}, {"ok": False}])
    judged = repo.mark_judged(
        batch_id=batch.id,
        manifest_id=uuid.uuid4(),
        manifest_status="ready",
        cluster_count=1,
        singleton_count=0,
    )
    closed = repo.close_batch(batch_id=batch.id)
    assert closed.status == "closed"
    failed = repo.mark_failed(batch_id=batch.id, error_message="boom")

    assert batch.workflow_id == "wf-1"
    assert batch.processed_job_count == 2
    assert judged.process_summary_json["reader_stage"] == "judged"
    assert item.item_status == "pending_consume"
    assert failed.error_message == "boom"

    db.scalar_queue = [batch, batch]
    db.scalars_items = [batch]
    assert repo.latest_batch() is batch
    assert repo.list_recent(limit=5) == [batch]
    assert repo.get_with_items(batch_id=batch.id) is batch


def test_published_reader_documents_repository_replaces_current_and_supports_queries() -> None:
    now = datetime(2026, 4, 9, 12, 0, tzinfo=UTC)
    previous = PublishedReaderDocument(
        id=uuid.uuid4(),
        stable_key="topic-ai-2026-04-09",
        slug="ai-2026-04-09-v1",
        window_id="2026-04-09@America/Los_Angeles",
        topic_key="ai",
        topic_label="AI",
        title="AI",
        summary="Old",
        markdown="# Old",
        reader_output_locale="zh-CN",
        reader_style_profile="briefing",
        materialization_mode="merge_then_polish",
        version=1,
        published_with_gap=False,
        is_current=True,
        source_item_count=1,
        warning_json={},
        coverage_ledger_json={},
        traceability_pack_json={},
        source_refs_json=[],
        sections_json=[],
        repair_history_json=[],
    )
    previous.created_at = now
    previous.updated_at = now
    db = _FakeDb()
    db.scalar_queue = [previous, previous, previous]
    db.scalars_items = [previous]
    db.get_map[(PublishedReaderDocument, previous.id)] = previous
    repo = PublishedReaderDocumentsRepository(db)

    listed = repo.list_current(limit=10, window_id=None)
    assert listed == [previous]
    assert repo.get(document_id=previous.id) is previous
    assert repo.get_current_by_stable_key(stable_key=previous.stable_key) is previous

    replacement = repo.replace_current(
        stable_key=previous.stable_key,
        slug="ai-2026-04-09-v2",
        window_id=previous.window_id,
        topic_key="ai",
        topic_label="AI",
        title="AI Updated",
        summary="New",
        markdown="# New",
        reader_output_locale="zh-CN",
        reader_style_profile="briefing",
        materialization_mode="repair_patch",
        published_with_gap=True,
        source_item_count=2,
        warning_json={"status": "published_with_gap"},
        coverage_ledger_json={"status": "gap_detected"},
        traceability_pack_json={"status": "ready"},
        source_refs_json=[{"source_item_id": "item-1"}],
        sections_json=[{"section_id": "sec-1"}],
        repair_history_json=[{"strategy": "patch"}],
        consumption_batch_id=None,
        cluster_verdict_manifest_id=None,
    )

    assert previous.is_current is False
    assert replacement.version == 2
    assert replacement.supersedes_document_id == previous.id
    assert replacement.source_refs_json == [{"source_item_id": "item-1"}]

    db.scalar_queue = [replacement]
    assert repo.get_by_slug(slug="ai-2026-04-09-v2") is replacement
