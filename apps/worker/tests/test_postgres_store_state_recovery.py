from __future__ import annotations

from types import TracebackType
from typing import Any

from worker.state.postgres_store import PostgresBusinessStore


class _FakeMappingsResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappingsResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows

    def one(self) -> dict[str, Any]:
        return self._rows[0]


class _CaptureConn:
    def __init__(self) -> None:
        self.executed_sql: str | None = None
        self.executed_params: dict[str, Any] | None = None

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeMappingsResult:
        sql = getattr(statement, "text", str(statement))
        self.executed_sql = " ".join(sql.split())
        self.executed_params = dict(params or {})
        return _FakeMappingsResult(
            [
                {
                    "id": "job-1",
                    "status": "failed",
                    "updated_at": "2026-03-02T00:00:00+00:00",
                    "hard_fail_reason": "dispatch_timeout",
                    "error_message": "workflow_dispatch_timeout",
                }
            ]
        )


class _CaptureUpsertConn:
    def __init__(self) -> None:
        self.executed_sql: str | None = None
        self.executed_params: dict[str, Any] | None = None

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeMappingsResult:
        sql = getattr(statement, "text", str(statement))
        self.executed_sql = " ".join(sql.split())
        self.executed_params = dict(params or {})
        return _FakeMappingsResult(
            [
                {
                    "id": "video-1",
                    "platform": "generic",
                    "video_uid": "uid-1",
                    "source_url": "https://example.com/a",
                    "title": "A",
                    "published_at": None,
                    "content_type": "article",
                }
            ]
        )


class _FakeBegin:
    def __init__(self, conn: _CaptureConn) -> None:
        self._conn = conn

    def __enter__(self) -> _CaptureConn:
        return self._conn

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class _FakeEngine:
    def __init__(self, conn: _CaptureConn) -> None:
        self._conn = conn

    def begin(self) -> _FakeBegin:
        return _FakeBegin(self._conn)


def test_fail_stale_queued_jobs_sets_pipeline_final_status_failed() -> None:
    conn = _CaptureConn()
    store = PostgresBusinessStore.__new__(PostgresBusinessStore)
    store._engine = _FakeEngine(conn)  # type: ignore[attr-defined]

    rows = store.fail_stale_queued_jobs(timeout_seconds=120, limit=5)

    assert rows[0]["status"] == "failed"
    assert conn.executed_sql is not None
    assert "pipeline_final_status = 'failed'" in conn.executed_sql
    assert "status = 'failed'" in conn.executed_sql
    assert conn.executed_params is not None
    assert conn.executed_params["timeout_seconds"] == 120
    assert conn.executed_params["limit"] == 5


def test_upsert_video_conflict_update_syncs_content_type() -> None:
    conn = _CaptureUpsertConn()
    store = PostgresBusinessStore.__new__(PostgresBusinessStore)
    store._engine = _FakeEngine(conn)  # type: ignore[attr-defined]

    row = store.upsert_video(
        platform="generic",
        video_uid="uid-1",
        source_url="https://example.com/a",
        title="A",
        published_at=None,
        content_type="article",
    )

    assert row["content_type"] == "article"
    assert conn.executed_sql is not None
    assert "content_type = EXCLUDED.content_type" in conn.executed_sql
    assert conn.executed_params is not None
    assert conn.executed_params["content_type"] == "article"
