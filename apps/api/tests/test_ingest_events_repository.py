from __future__ import annotations

import uuid
from typing import Any

from apps.api.app.repositories.ingest_events import IngestEventsRepository


class _FakeExecuteResult:
    def __init__(self, rows: list[tuple[uuid.UUID]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[uuid.UUID]]:
        return list(self._rows)


class _FakeSession:
    def __init__(self, rows: list[tuple[uuid.UUID]]) -> None:
        self.rows = rows
        self.added: list[Any] = []
        self.flush_called = 0
        self.last_stmt: Any = None

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_called += 1

    def execute(self, stmt: Any) -> _FakeExecuteResult:
        self.last_stmt = stmt
        return _FakeExecuteResult(self.rows)


def test_create_persists_ingest_event_and_flushes() -> None:
    sub_id = uuid.uuid4()
    video_id = uuid.uuid4()
    session = _FakeSession(rows=[])
    repo = IngestEventsRepository(db=session)  # type: ignore[arg-type]

    created = repo.create(
        subscription_id=sub_id,
        feed_guid="guid-1",
        feed_link="https://example.com/feed",
        entry_hash="entry-1",
        video_id=video_id,
    )

    assert session.flush_called == 1
    assert len(session.added) == 1
    assert created.subscription_id == sub_id
    assert created.video_id == video_id
    assert created.entry_hash == "entry-1"


def test_list_recent_video_ids_deduplicates_preserving_first_order() -> None:
    v1 = uuid.uuid4()
    v2 = uuid.uuid4()
    v3 = uuid.uuid4()
    session = _FakeSession(rows=[(v1,), (v2,), (v1,), (v3,), (v2,)])
    repo = IngestEventsRepository(db=session)  # type: ignore[arg-type]

    result = repo.list_recent_video_ids(subscription_id=uuid.uuid4(), limit=10)

    assert result == [v1, v2, v3]
    assert session.last_stmt is not None
