from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

from worker.temporal import activities_poll
from worker.temporal.activities_poll import (
    _build_rss_transcript,
    _resolve_content_type,
    _resolve_job_idempotency_key,
    _resolve_platform,
    _resolve_video_uid,
)


def test_resolve_platform_uses_normalized_platform_first() -> None:
    platform = _resolve_platform(
        normalized={"video_platform": "youtube"},
        subscription={"platform": "rss_generic"},
    )
    assert platform == "youtube"


def test_resolve_platform_falls_back_to_subscription_platform() -> None:
    platform = _resolve_platform(
        normalized={"video_platform": None},
        subscription={"platform": "rss_generic"},
    )
    assert platform == "rss_generic"


def test_resolve_platform_falls_back_to_generic_when_missing() -> None:
    platform = _resolve_platform(
        normalized={"video_platform": "  "},
        subscription={"platform": " "},
    )
    assert platform == "generic"


def test_resolve_video_uid_falls_back_to_entry_hash() -> None:
    uid = _resolve_video_uid(normalized={"video_uid": "", "entry_hash": "abc123"})
    assert uid == "abc123"


def test_resolve_video_uid_returns_unknown_without_hash() -> None:
    uid = _resolve_video_uid(normalized={"video_uid": "", "entry_hash": ""})
    assert uid == "unknown"


def test_resolve_content_type_keeps_video_for_strong_video_subscription() -> None:
    content_type = _resolve_content_type(
        normalized={"content_type": "video"},
        subscription={"platform": "youtube", "source_type": "youtube_channel_id"},
    )
    assert content_type == "video"


def test_resolve_content_type_forces_article_for_generic_rsshub_route() -> None:
    content_type = _resolve_content_type(
        normalized={"content_type": "video"},
        subscription={"platform": "rsshub", "source_type": "rsshub_route"},
    )
    assert content_type == "article"


def test_resolve_video_uid_can_force_entry_hash_for_article_lane() -> None:
    uid = _resolve_video_uid(
        normalized={"video_uid": "yt-1", "entry_hash": "hash-article"},
        force_entry_hash=True,
    )
    assert uid == "hash-article"


def test_resolve_job_idempotency_key_uses_article_formula_when_forced() -> None:
    key = _resolve_job_idempotency_key(
        normalized={"idempotency_key": "video-idem", "entry_hash": "hash-article"},
        content_type="article",
        force_article_key=True,
    )
    assert key != "video-idem"


def test_build_rss_transcript_uses_summary_when_content_missing() -> None:
    transcript = _build_rss_transcript(
        {
            "title": "Daily Brief",
            "summary": "summary text",
            "link": "https://example.com/feed/1",
            "published_at": "2026-03-08T00:00:00Z",
        }
    )
    assert transcript is not None
    assert "# Daily Brief" in transcript
    assert "summary text" in transcript
    assert "Source: https://example.com/feed/1" in transcript
    assert "Published: 2026-03-08T00:00:00Z" in transcript


def test_build_rss_transcript_returns_none_when_all_fields_empty() -> None:
    assert _build_rss_transcript({}) is None


def _poll_settings() -> SimpleNamespace:
    return SimpleNamespace(
        sqlite_path="/tmp/worker-state.db",
        database_url="postgresql://example.invalid/sourceharbor",
        lock_ttl_seconds=90,
        request_timeout_seconds=10,
        request_retry_attempts=1,
        request_retry_backoff_seconds=0.1,
        rsshub_public_fallback_base_url=None,
        rsshub_fallback_base_urls=[],
    )


def test_run_poll_feeds_once_skips_when_pg_lock_busy(monkeypatch) -> None:
    calls = {"sqlite_acquire": 0}

    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            calls["sqlite_acquire"] += 1
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, None, None

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))

    assert result == {"ok": True, "skipped": True, "reason": "lock_not_acquired"}
    assert calls["sqlite_acquire"] == 0


def test_run_poll_feeds_once_falls_back_to_sqlite_when_pg_lock_unavailable(
    monkeypatch,
    caplog,
) -> None:
    calls = {"sqlite_acquire": 0, "sqlite_release": 0}

    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            calls["sqlite_acquire"] += 1
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            calls["sqlite_release"] += 1

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return False, None, "advisory_unsupported:OperationalError"

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            assert subscription_id is None
            assert platform is None
            return []

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)

    caplog.set_level(logging.WARNING)
    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))

    assert result["ok"] is True
    assert result["feeds_polled"] == 0
    assert calls["sqlite_acquire"] == 1
    assert calls["sqlite_release"] == 1
    assert "poll_advisory_lock_unavailable" in caplog.text


def test_run_poll_feeds_once_skips_when_sqlite_lock_not_acquired(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return False

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            raise AssertionError("release_lock should not run")

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return False, None, "advisory_unsupported:OperationalError"

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))
    assert result == {"ok": True, "skipped": True, "reason": "lock_not_acquired"}


def test_run_poll_feeds_once_releases_pg_lock_when_acquired(monkeypatch) -> None:
    calls = {"pg_release": 0, "sqlite_acquire": 0}
    lease = object()

    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            calls["sqlite_acquire"] += 1
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, lease, None

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return []

        def release_advisory_lock(self, value) -> None:
            assert value is lease
            calls["pg_release"] += 1

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))

    assert result["ok"] is True
    assert calls["pg_release"] == 1
    assert calls["sqlite_acquire"] == 0


def test_run_poll_feeds_once_collects_article_candidates_and_overrides(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            self.created_jobs: list[dict[str, object]] = []

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return False, None, "advisory_unsupported"

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return [
                {
                    "id": "sub-1",
                    "platform": "rss",
                    "adapter_type": "rss_generic",
                    "source_url": "https://example.com/feed.xml",
                }
            ]

        def upsert_video(self, **kwargs):
            self.upsert_kwargs = kwargs
            return {
                "id": "video-1",
                "platform": kwargs["platform"],
                "video_uid": kwargs["video_uid"],
                "source_url": kwargs["source_url"],
                "title": kwargs["title"],
                "published_at": kwargs["published_at"],
            }

        def create_ingest_event(self, **kwargs):
            self.ingest_kwargs = kwargs
            return ({"id": "ingest-1"}, True)

        def find_active_job(self, *, idempotency_key):
            self.idempotency_key = idempotency_key
            return

        def create_queued_job(self, **kwargs):
            self.created_jobs.append(kwargs)
            return ({"id": "job-1"}, True)

    async def _fake_poll_subscription_entries(**_kwargs):
        return (
            1,
            [
                {
                    "video_platform": "",
                    "video_uid": "",
                    "entry_hash": "hash-1",
                    "idempotency_key": "idem-1",
                    "guid": "guid-1",
                    "link": "https://example.com/articles/1",
                    "title": "Article Title",
                    "published_at": "2026-03-08T00:00:00Z",
                    "content_type": "article",
                    "content": "Full RSS body",
                    "summary": "Fallback summary",
                }
            ],
        )

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)
    monkeypatch.setattr(
        activities_poll, "resolve_feed_url", lambda _settings, item: item["source_url"]
    )
    monkeypatch.setattr(
        activities_poll, "poll_subscription_entries", _fake_poll_subscription_entries
    )

    result = asyncio.run(
        activities_poll.run_poll_feeds_once(_poll_settings(), filters={"max_new_videos": 1})
    )

    assert result["jobs_created"] == 1
    assert result["entries_normalized"] == 1
    assert result["candidates"][0]["pipeline_mode"] == "text_only"
    assert "Full RSS body" in result["candidates"][0]["rss_transcript"]


def test_run_poll_feeds_once_forces_generic_rsshub_route_into_article_lane(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            self.created_jobs: list[dict[str, object]] = []

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, object(), None

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return [
                {
                    "id": "sub-2",
                    "platform": "rsshub",
                    "source_type": "rsshub_route",
                    "adapter_type": "rsshub_route",
                    "rsshub_route": "/36kr/newsflashes",
                }
            ]

        def upsert_video(self, **kwargs):
            self.upsert_kwargs = kwargs
            return {
                "id": "video-2",
                "platform": kwargs["platform"],
                "video_uid": kwargs["video_uid"],
                "source_url": kwargs["source_url"],
                "title": kwargs["title"],
                "published_at": kwargs["published_at"],
            }

        def create_ingest_event(self, **kwargs):
            return ({"id": "ingest-2"}, True)

        def find_active_job(self, *, idempotency_key):
            self.idempotency_key = idempotency_key
            return

        def create_queued_job(self, **kwargs):
            self.created_jobs.append(kwargs)
            return ({"id": "job-2"}, True)

        def release_advisory_lock(self, _lease) -> None:
            return None

    async def _fake_poll_subscription_entries(**_kwargs):
        return (
            1,
            [
                {
                    "video_platform": "youtube",
                    "video_uid": "yt-article-1",
                    "entry_hash": "entry-hash-2",
                    "idempotency_key": "video-idem-2",
                    "guid": "guid-2",
                    "link": "https://www.youtube.com/watch?v=yt-article-1",
                    "title": "Cross-posted article",
                    "published_at": "2026-03-08T00:00:00Z",
                    "content_type": "video",
                    "content": "Article body wins over embedded video links.",
                    "summary": "Summary text",
                }
            ],
        )

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)
    monkeypatch.setattr(
        activities_poll,
        "resolve_feed_url",
        lambda _settings, _item: "https://rsshub.app/36kr/newsflashes",
    )
    monkeypatch.setattr(
        activities_poll, "poll_subscription_entries", _fake_poll_subscription_entries
    )

    result = asyncio.run(
        activities_poll.run_poll_feeds_once(_poll_settings(), filters={"max_new_videos": 1})
    )

    assert result["jobs_created"] == 1
    assert result["candidates"][0]["content_type"] == "article"
    assert result["candidates"][0]["pipeline_mode"] == "text_only"
    assert result["candidates"][0]["video_uid"] == "entry-hash-2"


def test_run_poll_feeds_once_skips_duplicate_jobs(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, object(), None

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return [{"id": "sub-1", "platform": "youtube", "adapter_type": "rsshub_route"}]

        def upsert_video(self, **kwargs):
            return {
                "id": "video-1",
                "platform": kwargs["platform"],
                "video_uid": kwargs["video_uid"],
                "source_url": kwargs["source_url"],
                "title": kwargs["title"],
                "published_at": kwargs["published_at"],
            }

        def create_ingest_event(self, **kwargs):
            return ({"id": "ingest-1"}, False)

        def find_active_job(self, *, idempotency_key):
            assert idempotency_key == "idem-dup"
            return {"id": "existing-job"}

        def release_advisory_lock(self, _lease) -> None:
            return None

    async def _fake_poll_subscription_entries(**_kwargs):
        return (
            1,
            [
                {
                    "video_platform": "youtube",
                    "video_uid": "yt-1",
                    "entry_hash": "hash-dup",
                    "idempotency_key": "idem-dup",
                    "guid": "guid-dup",
                    "link": "https://youtube.com/watch?v=1",
                    "title": "Video Title",
                    "published_at": "2026-03-08T00:00:00Z",
                }
            ],
        )

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)
    monkeypatch.setattr(
        activities_poll, "resolve_feed_url", lambda _settings, _item: "https://example.com/feed.xml"
    )
    monkeypatch.setattr(
        activities_poll, "poll_subscription_entries", _fake_poll_subscription_entries
    )

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))

    assert result["jobs_created"] == 0
    assert result["job_duplicates"] == 1
    assert result["ingest_event_duplicates"] == 1


def test_run_poll_feeds_once_skips_invalid_feed_route(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, object(), None

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return [{"id": "sub-bad", "platform": "youtube", "adapter_type": "rsshub_route"}]

        def release_advisory_lock(self, _lease) -> None:
            return None

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)
    monkeypatch.setattr(
        activities_poll,
        "resolve_feed_url",
        lambda _settings, _item: (_ for _ in ()).throw(ValueError("invalid route")),
    )

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))
    assert result["feeds_polled"] == 0
    assert result["entries_fetched"] == 0


def test_run_poll_feeds_once_counts_create_queued_job_duplicates(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, object(), None

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return [{"id": "sub-1", "platform": "youtube", "adapter_type": "rsshub_route"}]

        def upsert_video(self, **kwargs):
            return {
                "id": "video-1",
                "platform": kwargs["platform"],
                "video_uid": kwargs["video_uid"],
                "source_url": kwargs["source_url"],
                "title": kwargs["title"],
                "published_at": kwargs["published_at"],
            }

        def create_ingest_event(self, **kwargs):
            return ({"id": "ingest-1"}, True)

        def find_active_job(self, *, idempotency_key):
            assert idempotency_key == "idem-1"
            return

        def create_queued_job(self, **kwargs):
            assert kwargs["overrides_json"] is None
            return ({"id": "job-existing"}, False)

        def release_advisory_lock(self, _lease) -> None:
            return None

    async def _fake_poll_subscription_entries(**_kwargs):
        return (
            1,
            [
                {
                    "video_platform": "youtube",
                    "video_uid": "yt-1",
                    "entry_hash": "hash-1",
                    "idempotency_key": "idem-1",
                    "guid": "guid-1",
                    "link": "https://youtube.com/watch?v=1",
                    "title": "Video Title",
                    "published_at": "2026-03-08T00:00:00Z",
                    "content_type": "podcast",
                }
            ],
        )

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)
    monkeypatch.setattr(
        activities_poll, "resolve_feed_url", lambda _settings, _item: "https://example.com/feed.xml"
    )
    monkeypatch.setattr(
        activities_poll, "poll_subscription_entries", _fake_poll_subscription_entries
    )

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))
    assert result["jobs_created"] == 0
    assert result["job_duplicates"] == 1


def test_run_poll_feeds_once_ignores_subscription_poll_value_error(monkeypatch) -> None:
    class _FakeSQLiteStore:
        def __init__(self, _path: str) -> None:
            pass

        def acquire_lock(self, _lock_key: str, _owner: str, _ttl: int) -> bool:
            return True

        def release_lock(self, _lock_key: str, _owner: str) -> None:
            return None

    class _FakePostgresStore:
        def __init__(self, _database_url: str) -> None:
            pass

        def try_acquire_advisory_lock(self, *, lock_key: str):
            assert lock_key == "phase2.poll_feeds"
            return True, object(), None

        def list_subscriptions(self, *, subscription_id=None, platform=None):
            return [{"id": "sub-1", "platform": "youtube", "adapter_type": "rsshub_route"}]

        def release_advisory_lock(self, _lease) -> None:
            return None

    async def _failing_poll_subscription_entries(**_kwargs):
        raise ValueError("malformed feed")

    monkeypatch.setattr(activities_poll, "SQLiteStateStore", _FakeSQLiteStore)
    monkeypatch.setattr(activities_poll, "PostgresBusinessStore", _FakePostgresStore)
    monkeypatch.setattr(
        activities_poll, "resolve_feed_url", lambda _settings, _item: "https://example.com/feed.xml"
    )
    monkeypatch.setattr(
        activities_poll, "poll_subscription_entries", _failing_poll_subscription_entries
    )

    result = asyncio.run(activities_poll.run_poll_feeds_once(_poll_settings()))
    assert result["entries_fetched"] == 0
    assert result["entries_normalized"] == 0


def test_poll_feeds_activity_delegates_to_run_poll_feeds_once(monkeypatch) -> None:
    observed: dict[str, Any] = {}
    sentinel_settings = object()

    async def _fake_run_poll_feeds_once(settings: object, filters: dict[str, Any] | None = None):
        observed["settings"] = settings
        observed["filters"] = filters
        return {"ok": True, "phase": "phase2"}

    monkeypatch.setattr(
        activities_poll.Settings,
        "from_env",
        staticmethod(lambda: sentinel_settings),
    )
    monkeypatch.setattr(activities_poll, "run_poll_feeds_once", _fake_run_poll_feeds_once)

    result = asyncio.run(activities_poll.poll_feeds_activity(filters={"platform": "youtube"}))
    assert result == {"ok": True, "phase": "phase2"}
    assert observed == {
        "settings": sentinel_settings,
        "filters": {"platform": "youtube"},
    }
