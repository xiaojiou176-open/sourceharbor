from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from apps.api.app.repositories.subscriptions import SubscriptionsRepository
from apps.api.app.repositories.videos import VideosRepository


class _FakeScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeMappingsResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappingsResult:
        return self

    def one(self) -> dict[str, Any]:
        return self._rows[0]

    def __iter__(self):
        return iter(self._rows)


@dataclass
class _FakeVideo:
    id: uuid.UUID
    platform: str
    video_uid: str
    source_url: str
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class _FakeSubscription:
    id: uuid.UUID
    platform: str
    source_type: str
    source_value: str
    adapter_type: str
    source_url: str | None
    rsshub_route: str
    category: str
    tags: list[str]
    priority: int
    enabled: bool


class _FakeBind:
    def __init__(self, dialect_name: str) -> None:
        self.dialect = SimpleNamespace(name=dialect_name)


class _FakeSession:
    def __init__(self, *, dialect_name: str = "sqlite") -> None:
        self.bind = _FakeBind(dialect_name)
        self.executed: list[tuple[Any, dict[str, Any] | None]] = []
        self.scalar_value: Any = None
        self.scalars_rows: list[Any] = []
        self.get_value: Any = None
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.commits = 0
        self.refreshes: list[Any] = []

    def execute(self, stmt: Any, params: dict[str, Any] | None = None) -> _FakeMappingsResult:
        self.executed.append((stmt, params))
        return _FakeMappingsResult([{"id": uuid.uuid4(), "created": True}])

    def scalars(self, stmt: Any) -> _FakeScalarResult:
        self.executed.append((stmt, None))
        return _FakeScalarResult(self.scalars_rows)

    def scalar(self, stmt: Any) -> Any:
        self.executed.append((stmt, None))
        return self.scalar_value

    def get(self, _model: Any, _id: Any) -> Any:
        return self.get_value

    def add(self, item: Any) -> None:
        self.added.append(item)

    def delete(self, item: Any) -> None:
        self.deleted.append(item)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, item: Any) -> None:
        self.refreshes.append(item)


def test_videos_repository_list_and_list_recent_cover_query_paths() -> None:
    session = _FakeSession()
    repo = VideosRepository(session)  # type: ignore[arg-type]
    session.scalars_rows = [
        _FakeVideo(
            uuid.uuid4(),
            "youtube",
            "a",
            "https://example.com/a",
            datetime.now(UTC),
            datetime.now(UTC),
        )
    ]

    session.execute = lambda stmt, params=None: _FakeMappingsResult(  # type: ignore[method-assign]
        [
            {
                "id": "1",
                "platform": "youtube",
                "video_uid": "abc",
                "source_url": "https://example.com",
                "title": "Demo",
                "published_at": None,
                "first_seen_at": None,
                "last_seen_at": None,
                "latest_job_status": "queued",
                "latest_job_id": "job-1",
            }
        ]
    )

    rows = repo.list(platform="youtube", status="queued", limit=5)
    recent = repo.list_recent(platform="youtube", limit=1)

    assert rows[0]["latest_job_id"] == "job-1"
    assert len(recent) == 1


def test_videos_repository_list_by_ids_preserves_input_order_and_limit() -> None:
    session = _FakeSession()
    repo = VideosRepository(session)  # type: ignore[arg-type]
    v1 = _FakeVideo(
        uuid.uuid4(), "youtube", "v1", "https://example.com/1", datetime.now(UTC), datetime.now(UTC)
    )
    v2 = _FakeVideo(
        uuid.uuid4(), "youtube", "v2", "https://example.com/2", datetime.now(UTC), datetime.now(UTC)
    )
    session.scalars_rows = [v2, v1]

    ordered = repo.list_by_ids(video_ids=[v1.id, v2.id, v1.id], platform="youtube", limit=1)

    assert [item.id for item in ordered] == [v1.id]


def test_videos_repository_upsert_for_processing_sqlite_create_and_update_paths() -> None:
    session = _FakeSession(dialect_name="sqlite")
    repo = VideosRepository(session)  # type: ignore[arg-type]

    session.scalar_value = None
    created = repo.upsert_for_processing(
        platform="youtube",
        video_uid="abc",
        source_url="https://example.com/a",
    )
    assert created in session.added
    assert session.commits == 1
    assert session.refreshes[-1] is created

    existing = _FakeVideo(
        uuid.uuid4(), "youtube", "abc", "https://old", datetime.now(UTC), datetime.now(UTC)
    )
    session.scalar_value = existing
    updated = repo.upsert_for_processing(
        platform="youtube",
        video_uid="abc",
        source_url="https://example.com/b",
    )
    assert updated is existing
    assert updated.source_url == "https://example.com/b"
    assert session.commits == 2


def test_videos_repository_upsert_for_processing_postgres_path_and_missing_row_guard() -> None:
    session = _FakeSession(dialect_name="postgresql")
    repo = VideosRepository(session)  # type: ignore[arg-type]
    loaded = _FakeVideo(
        uuid.uuid4(),
        "youtube",
        "pg",
        "https://example.com/pg",
        datetime.now(UTC),
        datetime.now(UTC),
    )
    session.get_value = loaded

    result = repo.upsert_for_processing(
        platform="youtube", video_uid="pg", source_url="https://example.com/pg"
    )
    assert result is loaded
    assert session.commits == 1
    assert session.refreshes[-1] is loaded

    session_missing = _FakeSession(dialect_name="postgresql")
    repo_missing = VideosRepository(session_missing)  # type: ignore[arg-type]
    session_missing.get_value = None
    try:
        repo_missing.upsert_for_processing(
            platform="youtube", video_uid="pg", source_url="https://example.com/pg"
        )
    except RuntimeError as exc:
        assert "failed to load video after upsert" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when postgres upsert row cannot be loaded")


def test_subscriptions_repository_list_upsert_batch_get_and_delete_paths() -> None:
    session = _FakeSession(dialect_name="sqlite")
    repo = SubscriptionsRepository(session)  # type: ignore[arg-type]
    sub = _FakeSubscription(
        uuid.uuid4(),
        "youtube",
        "url",
        "https://example.com/feed",
        "rsshub_route",
        None,
        "/youtube/channel/demo",
        "tech",
        ["ai"],
        50,
        True,
    )
    session.scalars_rows = [sub]
    listed = repo.list(platform="youtube", category="tech", enabled_only=True)
    assert listed == [sub]

    session.scalar_value = None
    created, created_flag = repo.upsert(
        platform="youtube",
        source_type="url",
        source_value="https://example.com/feed",
        adapter_type="rsshub_route",
        source_url=None,
        rsshub_route="/youtube/channel/demo",
        category="tech",
        tags=["ai"],
        priority=50,
        enabled=True,
    )
    assert created_flag is True
    assert created in session.added

    existing = _FakeSubscription(
        uuid.uuid4(),
        "youtube",
        "url",
        "https://example.com/feed",
        "rsshub_route",
        None,
        "/youtube/channel/demo",
        "misc",
        [],
        10,
        False,
    )
    session.scalar_value = existing
    updated, created_flag = repo.upsert(
        platform="youtube",
        source_type="url",
        source_value="https://example.com/feed",
        adapter_type="rss_generic",
        source_url="https://example.com/feed.xml",
        rsshub_route="",
        category="ops",
        tags=["infra"],
        priority=80,
        enabled=True,
    )
    assert created_flag is False
    assert updated is existing
    assert existing.adapter_type == "rss_generic"
    assert existing.category == "ops"

    session.scalars_rows = [existing]
    affected = repo.batch_update_category(ids=[existing.id], category="creator")
    assert affected == 1
    assert existing.category == "creator"

    session.get_value = existing
    assert repo.get(existing.id) is existing
    assert repo.delete(existing.id) is True
    assert session.deleted[-1] is existing
    session.get_value = None
    assert repo.delete(existing.id) is False


def test_subscriptions_repository_postgres_upsert_path_and_missing_row_guard() -> None:
    session = _FakeSession(dialect_name="postgresql")
    repo = SubscriptionsRepository(session)  # type: ignore[arg-type]
    existing = _FakeSubscription(
        uuid.uuid4(),
        "youtube",
        "url",
        "https://example.com/feed",
        "rsshub_route",
        None,
        "/youtube/channel/demo",
        "tech",
        [],
        50,
        True,
    )
    session.get_value = existing

    row, created = repo.upsert(
        platform="youtube",
        source_type="url",
        source_value="https://example.com/feed",
        adapter_type="rsshub_route",
        source_url=None,
        rsshub_route="/youtube/channel/demo",
        category="tech",
        tags=[],
        priority=50,
        enabled=True,
    )
    assert row is existing
    assert created is True

    missing_session = _FakeSession(dialect_name="postgresql")
    repo_missing = SubscriptionsRepository(missing_session)  # type: ignore[arg-type]
    try:
        repo_missing.upsert(
            platform="youtube",
            source_type="url",
            source_value="https://example.com/feed",
            adapter_type="rsshub_route",
            source_url=None,
            rsshub_route="/youtube/channel/demo",
            category="tech",
            tags=[],
            priority=50,
            enabled=True,
        )
    except RuntimeError as exc:
        assert "failed to load subscription after upsert" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when postgres upsert row cannot be loaded")
