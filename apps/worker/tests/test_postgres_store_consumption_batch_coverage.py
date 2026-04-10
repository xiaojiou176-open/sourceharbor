from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from worker.state.postgres_store import PostgresBusinessStore


class _FakeResult:
    def __init__(self, rows=None, scalar=None) -> None:
        self._rows = list(rows or [])
        self._scalar = scalar

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def one(self):
        return self._rows[0]

    def scalar(self):
        return self._scalar


class _FakeConnection:
    def __init__(self, results) -> None:
        self._results = list(results)
        self.executed: list[tuple[str, dict[str, object] | None]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params))
        if not self._results:
            raise AssertionError("no fake result left for execute()")
        return self._results.pop(0)


class _FakeBegin:
    def __init__(self, conn: _FakeConnection) -> None:
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeEngine:
    def __init__(self, connections: list[_FakeConnection]) -> None:
        self._connections = list(connections)
        self.used_connections: list[_FakeConnection] = []

    def begin(self):
        if not self._connections:
            raise AssertionError("no fake connection left for begin()")
        conn = self._connections.pop(0)
        self.used_connections.append(conn)
        return _FakeBegin(conn)


def _make_store(*connections: _FakeConnection) -> tuple[PostgresBusinessStore, _FakeEngine]:
    store = PostgresBusinessStore.__new__(PostgresBusinessStore)
    engine = _FakeEngine(list(connections))
    store._engine = engine
    return store, engine


def test_prepare_consumption_batch_returns_no_pending_items_and_defaults_window_id() -> None:
    store, _engine = _make_store(_FakeConnection([_FakeResult(rows=[])]))

    payload = store.prepare_consumption_batch(
        trigger_mode="manual",
        window_id=None,
        timezone_name="Not/AZone",
        requested_by="tester",
        requested_trace_id="trace-1",
        max_items=0,
    )

    assert payload["status"] == "no_pending_items"
    assert payload["trigger_mode"] == "manual"
    assert payload["timezone_name"] == "UTC"
    assert payload["source_item_count"] == 0
    assert payload["job_ids"] == []
    assert payload["pending_window_ids"] == []


def test_prepare_consumption_batch_freezes_selected_items_and_marks_assigned() -> None:
    first = {
        "ingest_run_item_id": "item-1",
        "subscription_id": "sub-1",
        "video_id": "video-1",
        "job_id": "job-1",
        "ingest_event_id": "evt-1",
        "platform": "youtube",
        "video_uid": "abc",
        "source_url": "https://www.youtube.com/watch?v=abc",
        "title": "First",
        "published_at": datetime(2026, 4, 9, 15, 0, tzinfo=UTC),
        "discovered_at": datetime(2026, 4, 9, 15, 1, tzinfo=UTC),
        "entry_hash": "hash-1",
        "pipeline_mode": "full",
        "content_type": "video",
    }
    second = {
        **first,
        "ingest_run_item_id": "item-2",
        "video_id": "video-2",
        "job_id": "job-2",
        "ingest_event_id": "evt-2",
        "title": "Second",
        "video_uid": "def",
        "source_url": "https://www.youtube.com/watch?v=def",
    }
    other_window = {
        **first,
        "ingest_run_item_id": "item-3",
        "video_id": "video-3",
        "job_id": "job-3",
        "ingest_event_id": "evt-3",
        "title": "Later",
        "published_at": datetime(2026, 4, 10, 8, 0, tzinfo=UTC),
        "discovered_at": datetime(2026, 4, 10, 8, 1, tzinfo=UTC),
    }
    select_result = _FakeResult(rows=[first, second, other_window])
    insert_batch_result = _FakeResult(rows=[{"id": "batch-1"}])
    conn = _FakeConnection(
        [
            select_result,
            insert_batch_result,
            _FakeResult(),
            _FakeResult(),
            _FakeResult(),
            _FakeResult(),
        ]
    )
    store, engine = _make_store(conn)

    payload = store.prepare_consumption_batch(
        trigger_mode="auto",
        window_id=None,
        timezone_name="America/Los_Angeles",
        requested_by="robot",
        requested_trace_id="trace-2",
        subscription_id="sub-1",
        platform="youtube",
        max_items=2,
    )

    assert payload["status"] == "frozen"
    assert payload["consumption_batch_id"] == "batch-1"
    assert payload["trigger_mode"] == "auto"
    assert payload["source_item_count"] == 2
    assert payload["job_ids"] == ["job-1", "job-2"]
    assert payload["source_item_ids"] == ["item-1", "item-2"]
    assert payload["pending_window_ids"] == ["2026-04-09@America/Los_Angeles"]
    assert engine.used_connections[0].executed[0][1]["scan_limit"] == 50


def test_consumption_batch_lifecycle_methods_cover_get_and_mark_operations() -> None:
    get_conn = _FakeConnection(
        [
            _FakeResult(
                rows=[
                    {
                        "id": "batch-1",
                        "workflow_id": "wf-1",
                        "status": "frozen",
                        "trigger_mode": "manual",
                        "window_id": "2026-04-09@UTC",
                        "timezone_name": "UTC",
                        "cutoff_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        "requested_by": None,
                        "requested_trace_id": None,
                        "filters_json": {},
                        "base_published_doc_versions": [],
                        "source_item_count": 1,
                        "processed_job_count": 0,
                        "succeeded_job_count": 0,
                        "failed_job_count": 0,
                        "process_summary_json": {},
                        "error_message": None,
                        "materialized_at": None,
                        "closed_at": None,
                        "created_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        "updated_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                    }
                ]
            ),
            _FakeResult(
                rows=[
                    {
                        "id": "item-1",
                        "consumption_batch_id": "batch-1",
                        "ingest_run_item_id": "ing-1",
                        "subscription_id": "sub-1",
                        "video_id": "video-1",
                        "job_id": "job-1",
                        "ingest_event_id": "evt-1",
                        "platform": "youtube",
                        "video_uid": "abc",
                        "source_url": "https://www.youtube.com/watch?v=abc",
                        "title": "Hello",
                        "published_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        "source_effective_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        "discovered_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        "entry_hash": "hash-1",
                        "pipeline_mode": "full",
                        "content_type": "video",
                        "source_origin": "subscription_tracked",
                        "created_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                        "updated_at": datetime(2026, 4, 9, 12, 0, tzinfo=UTC),
                    }
                ]
            ),
        ]
    )
    workflow_conn = _FakeConnection(
        [_FakeResult(rows=[{"id": "batch-1", "workflow_id": "wf-2", "status": "frozen"}])]
    )
    materialized_conn = _FakeConnection(
        [
            _FakeResult(
                rows=[
                    {
                        "id": "batch-1",
                        "status": "materialized",
                        "materialized_at": datetime(2026, 4, 9, 12, 30, tzinfo=UTC),
                        "updated_at": datetime(2026, 4, 9, 12, 30, tzinfo=UTC),
                    }
                ]
            )
        ]
    )
    closed_conn = _FakeConnection(
        [
            _FakeResult(),
            _FakeResult(
                rows=[
                    {
                        "id": "batch-1",
                        "status": "closed",
                        "closed_at": datetime(2026, 4, 9, 12, 45, tzinfo=UTC),
                        "updated_at": datetime(2026, 4, 9, 12, 45, tzinfo=UTC),
                    }
                ]
            ),
        ]
    )
    failed_conn = _FakeConnection(
        [
            _FakeResult(),
            _FakeResult(
                rows=[
                    {
                        "id": "batch-1",
                        "status": "failed",
                        "error_message": "boom",
                        "closed_at": datetime(2026, 4, 9, 13, 0, tzinfo=UTC),
                    }
                ]
            ),
        ]
    )
    store, _engine = _make_store(
        get_conn, workflow_conn, materialized_conn, closed_conn, failed_conn
    )

    payload = store.get_consumption_batch(batch_id="batch-1")
    assert payload["id"] == "batch-1"
    assert payload["items"][0]["job_id"] == "job-1"

    workflow_payload = store.mark_consumption_batch_workflow_started(
        batch_id="batch-1", workflow_id="wf-2"
    )
    assert workflow_payload["workflow_id"] == "wf-2"

    materialized_payload = store.mark_consumption_batch_materialized(
        batch_id="batch-1",
        processed_job_count=2,
        succeeded_job_count=1,
        failed_job_count=1,
        process_summary_json={"jobs": ["job-1"]},
    )
    assert materialized_payload["status"] == "materialized"

    closed_payload = store.mark_consumption_batch_closed(
        batch_id="batch-1",
        process_summary_json={"status": "done"},
    )
    assert closed_payload["status"] == "closed"

    failed_payload = store.mark_consumption_batch_failed(
        batch_id="batch-1",
        error_message="boom",
    )
    assert failed_payload["status"] == "failed"
    assert failed_payload["error_message"] == "boom"


def test_batch_timezone_helpers_cover_invalid_zone_and_naive_timestamps() -> None:
    zone, name = PostgresBusinessStore._resolve_batch_timezone("Not/AZone")
    assert zone is UTC
    assert name == "UTC"

    window_id, effective_at, discovered_at = PostgresBusinessStore._window_id_for_item(
        published_at=datetime(2026, 4, 9, 8, 0),
        discovered_at=datetime(2026, 4, 9, 9, 0),
        timezone_name="America/Los_Angeles",
    )

    assert window_id.endswith("@America/Los_Angeles")
    assert effective_at.tzinfo is UTC
    assert discovered_at.tzinfo is UTC
    assert effective_at.astimezone(ZoneInfo("America/Los_Angeles")).date().isoformat() in window_id
