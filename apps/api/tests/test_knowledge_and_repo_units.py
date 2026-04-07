from __future__ import annotations

import uuid
from types import SimpleNamespace

from apps.api.app.models.feed_feedback import FeedFeedback
from apps.api.app.models.ingest_run import IngestRun
from apps.api.app.repositories.feed_feedback import FeedFeedbackRepository
from apps.api.app.repositories.ingest_runs import IngestRunsRepository
from apps.api.app.repositories.knowledge_cards import KnowledgeCardsRepository
from apps.api.app.services.knowledge import KnowledgeService


class _ScalarListResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, *, scalar_result=None, scalars_result=None, get_result=None) -> None:
        self.scalar_result = scalar_result
        self.scalars_result = scalars_result or []
        self.get_result = get_result
        self.added = []
        self.committed = 0
        self.refreshed = []
        self.scalar_stmt = None
        self.scalars_stmt = None
        self.get_calls = []

    def scalar(self, stmt):
        self.scalar_stmt = stmt
        return self.scalar_result

    def scalars(self, stmt):
        self.scalars_stmt = stmt
        return _ScalarListResult(self.scalars_result)

    def get(self, model, value):
        self.get_calls.append((model, value))
        return self.get_result

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.committed += 1

    def refresh(self, row):
        self.refreshed.append(row)


def test_knowledge_service_filters_topic_claim_and_limit() -> None:
    service = KnowledgeService(db=object())
    captured = {}

    rows = [
        SimpleNamespace(
            metadata_json={"topic_key": "alpha", "claim_kind": "forecast"},
            ordinal=1,
        ),
        SimpleNamespace(
            metadata_json={"topic_key": "beta", "claim_kind": "forecast"},
            ordinal=2,
        ),
        SimpleNamespace(
            metadata_json={"topic_key": "alpha", "claim_kind": "evidence"},
            ordinal=3,
        ),
        SimpleNamespace(
            metadata_json={"topic_key": "alpha", "claim_kind": "forecast"},
            ordinal=4,
        ),
    ]

    class _FakeRepo:
        def list(self, **kwargs):
            captured.update(kwargs)
            return rows

    service.repo = _FakeRepo()

    result = service.list_cards(
        topic_key=" Alpha ",
        claim_kind=" FORECAST ",
        limit=2,
    )

    assert captured["limit"] == 8
    assert [row.ordinal for row in result] == [1, 4]


def test_knowledge_service_handles_blank_filters_and_non_dict_metadata() -> None:
    service = KnowledgeService(db=object())

    rows = [
        SimpleNamespace(metadata_json=None, ordinal=1),
        SimpleNamespace(metadata_json={"topic_key": "alpha"}, ordinal=2),
    ]

    class _FakeRepo:
        def list(self, **_kwargs):
            return rows

    service.repo = _FakeRepo()

    result = service.list_cards(topic_key="  ", claim_kind=None, limit=1)

    assert [row.ordinal for row in result] == [1]


def test_feed_feedback_repository_get_and_create_upsert() -> None:
    job_id = uuid.uuid4()
    session = _FakeSession(scalar_result=None)
    repo = FeedFeedbackRepository(session)

    assert repo.get_by_job_id(job_id=job_id) is None

    created = repo.upsert(job_id=job_id, saved=True, feedback_label="useful")

    assert isinstance(created, FeedFeedback)
    assert created.job_id == job_id
    assert created.saved is True
    assert created.feedback_label == "useful"
    assert session.committed == 1
    assert session.refreshed == [created]


def test_feed_feedback_repository_updates_existing_row() -> None:
    existing = FeedFeedback(job_id=uuid.uuid4(), saved=False, feedback_label=None)
    session = _FakeSession(scalar_result=existing)
    repo = FeedFeedbackRepository(session)

    updated = repo.upsert(job_id=existing.job_id, saved=True, feedback_label="noisy")

    assert updated is existing
    assert existing.saved is True
    assert existing.feedback_label == "noisy"
    assert session.committed == 1
    assert session.refreshed == [existing]


def test_knowledge_cards_repository_list_returns_scalars() -> None:
    row = SimpleNamespace(card_type="topic")
    session = _FakeSession(scalars_result=[row])
    repo = KnowledgeCardsRepository(session)

    result = repo.list(
        job_id=uuid.uuid4(),
        video_id=uuid.uuid4(),
        card_type="topic",
        limit=5,
    )

    assert result == [row]
    assert "knowledge_cards" in str(session.scalars_stmt).lower()


def test_ingest_runs_repository_create_persists_and_refreshes() -> None:
    session = _FakeSession()
    repo = IngestRunsRepository(session)

    created = repo.create(
        subscription_id=None,
        platform="youtube",
        max_new_videos=5,
        filters_json={"platform": "youtube"},
        requested_by="tester",
        requested_trace_id="trace-1",
    )

    assert isinstance(created, IngestRun)
    assert created.status == "queued"
    assert created.platform == "youtube"
    assert session.committed == 1
    assert session.refreshed == [created]


def test_ingest_runs_repository_mark_methods_cover_success_and_missing() -> None:
    run = IngestRun(platform="youtube", max_new_videos=1, filters_json={})
    run.id = uuid.uuid4()
    session = _FakeSession(get_result=run)
    repo = IngestRunsRepository(session)

    updated = repo.mark_workflow_started(run_id=run.id, workflow_id="wf-1")
    assert updated.workflow_id == "wf-1"
    assert updated.status == "queued"

    failed = repo.mark_failed(run_id=run.id, error_message="boom")
    assert failed.status == "failed"
    assert failed.error_message == "boom"
    assert failed.completed_at is not None

    missing_session = _FakeSession(get_result=None)
    missing_repo = IngestRunsRepository(missing_session)
    missing_run_id = uuid.uuid4()

    try:
        missing_repo.mark_workflow_started(run_id=missing_run_id, workflow_id="wf-x")
    except ValueError as exc:
        assert str(missing_run_id) in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for missing ingest run")

    try:
        missing_repo.mark_failed(run_id=missing_run_id, error_message="missing")
    except ValueError as exc:
        assert str(missing_run_id) in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for missing ingest run")


def test_ingest_runs_repository_get_with_items_and_list_recent() -> None:
    run = IngestRun(platform="rss", max_new_videos=3, filters_json={})
    session = _FakeSession(scalar_result=run, scalars_result=[run])
    repo = IngestRunsRepository(session)

    assert repo.get_with_items(run_id=uuid.uuid4()) is run
    result = repo.list_recent(limit=3, status="completed", platform="rss")

    assert result == [run]
    stmt_text = str(session.scalars_stmt).lower()
    assert "order by" in stmt_text
    assert "limit" in stmt_text
