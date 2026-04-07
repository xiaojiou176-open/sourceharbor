from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from worker.state.postgres_store import AdvisoryLockLease, PostgresBusinessStore


class _Result:
    def __init__(self, *, rows: list[dict[str, Any]] | None = None, scalar: Any = None) -> None:
        self._rows = list(rows or [])
        self._scalar = scalar

    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def first(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def one(self) -> dict[str, Any]:
        if not self._rows:
            raise AssertionError("expected at least one row")
        return self._rows[0]

    def scalar(self) -> Any:
        return self._scalar


class _ScriptedConn:
    def __init__(self, scripts: list[tuple[str, Any]]) -> None:
        self._scripts = list(scripts)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        sql = getattr(statement, "text", str(statement))
        normalized_sql = " ".join(sql.split())
        self.calls.append({"sql": normalized_sql, "params": dict(params or {})})
        if not self._scripts:
            raise AssertionError(f"unexpected SQL call: {normalized_sql}")
        expected_fragment, action = self._scripts.pop(0)
        if expected_fragment not in normalized_sql:
            raise AssertionError(
                f"expected SQL containing '{expected_fragment}', got '{normalized_sql}'"
            )
        if isinstance(action, Exception):
            raise action
        if isinstance(action, _Result):
            return action
        if callable(action):
            return action(normalized_sql, dict(params or {}))
        raise AssertionError(f"unsupported scripted action type: {type(action)}")

    def close(self) -> None:
        self.closed = True


class _BeginCtx:
    def __init__(self, conn: _ScriptedConn) -> None:
        self._conn = conn

    def __enter__(self) -> _ScriptedConn:
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _ScriptedEngine:
    def __init__(
        self,
        *,
        begin_conns: list[_ScriptedConn] | None = None,
        connect_conn: _ScriptedConn | None = None,
        connect_error: Exception | None = None,
    ) -> None:
        self._begin_conns = list(begin_conns or [])
        self._connect_conn = connect_conn
        self._connect_error = connect_error

    def begin(self) -> _BeginCtx:
        if not self._begin_conns:
            raise AssertionError("no scripted begin() connection remaining")
        return _BeginCtx(self._begin_conns.pop(0))

    def connect(self) -> _ScriptedConn:
        if self._connect_error is not None:
            raise self._connect_error
        if self._connect_conn is None:
            raise AssertionError("no scripted connect() connection configured")
        return self._connect_conn


def _build_store(engine: _ScriptedEngine) -> PostgresBusinessStore:
    store = PostgresBusinessStore.__new__(PostgresBusinessStore)
    store._engine = engine  # type: ignore[attr-defined]
    return store


def test_try_acquire_advisory_lock_handles_connect_error() -> None:
    store = _build_store(_ScriptedEngine(connect_error=RuntimeError("db down")))
    supported, lease, reason = store.try_acquire_advisory_lock(lock_key="k")
    assert (supported, lease) == (False, None)
    assert reason == "connect_failed:RuntimeError"


def test_constructor_uses_create_engine(monkeypatch) -> None:
    sentinel_engine = object()
    captured: dict[str, Any] = {}

    def _fake_create_engine(database_url: str, *, future: bool, pool_pre_ping: bool) -> object:
        captured["database_url"] = database_url
        captured["future"] = future
        captured["pool_pre_ping"] = pool_pre_ping
        return sentinel_engine

    monkeypatch.setattr("worker.state.postgres_store.create_engine", _fake_create_engine)
    store = PostgresBusinessStore("postgresql://example.invalid/db")
    assert store._engine is sentinel_engine  # type: ignore[attr-defined]
    assert captured == {
        "database_url": "postgresql://example.invalid/db",
        "future": True,
        "pool_pre_ping": True,
    }


def test_try_acquire_advisory_lock_and_release_success_path() -> None:
    conn = _ScriptedConn(
        scripts=[
            ("pg_try_advisory_lock", _Result(scalar=True)),
            ("pg_advisory_unlock", _Result(scalar=True)),
        ]
    )
    store = _build_store(_ScriptedEngine(connect_conn=conn))

    supported, lease, reason = store.try_acquire_advisory_lock(lock_key="job.lock")
    assert supported is True
    assert reason is None
    assert isinstance(lease, AdvisoryLockLease)
    assert lease.lock_key == "job.lock"
    assert conn.closed is False

    store.release_advisory_lock(lease)
    assert conn.closed is True


def test_try_acquire_advisory_lock_busy_and_unsupported() -> None:
    busy_conn = _ScriptedConn(scripts=[("pg_try_advisory_lock", _Result(scalar=False))])
    busy_store = _build_store(_ScriptedEngine(connect_conn=busy_conn))
    supported, lease, reason = busy_store.try_acquire_advisory_lock(lock_key="k")
    assert (supported, lease, reason) == (True, None, None)
    assert busy_conn.closed is True

    unsupported_conn = _ScriptedConn(scripts=[("pg_try_advisory_lock", Exception("unsupported"))])
    unsupported_store = _build_store(_ScriptedEngine(connect_conn=unsupported_conn))
    supported, lease, reason = unsupported_store.try_acquire_advisory_lock(lock_key="k")
    assert (supported, lease) == (False, None)
    assert reason == "advisory_unsupported:Exception"
    assert unsupported_conn.closed is True


def test_list_subscriptions_and_find_job_helpers() -> None:
    conn = _ScriptedConn(
        scripts=[
            (
                "FROM subscriptions",
                _Result(rows=[{"id": "s1", "platform": "youtube", "enabled": True}]),
            ),
            ("FROM jobs", _Result(rows=[{"id": "job-1", "status": "running"}])),
            ("FROM jobs", _Result(rows=[{"id": "job-2", "status": "failed"}])),
        ]
    )
    store = _build_store(_ScriptedEngine(begin_conns=[conn, conn, conn]))

    rows = store.list_subscriptions(subscription_id="sub-1", platform="youtube")
    assert rows == [{"id": "s1", "platform": "youtube", "enabled": True}]
    assert conn.calls[0]["params"] == {"subscription_id": "sub-1", "platform": "youtube"}

    assert store.find_active_job(idempotency_key="idem-1") == {"id": "job-1", "status": "running"}
    assert store.find_job_by_idempotency_key(idempotency_key="idem-2") == {
        "id": "job-2",
        "status": "failed",
    }


def test_create_ingest_event_handles_insert_and_conflict_recovery() -> None:
    insert_conn = _ScriptedConn(
        scripts=[("INSERT INTO ingest_events", _Result(rows=[{"id": "ie-1", "video_id": "v1"}]))]
    )
    store = _build_store(_ScriptedEngine(begin_conns=[insert_conn]))
    payload, created = store.create_ingest_event(
        subscription_id="sub-1",
        feed_guid="g",
        feed_link="https://example.com",
        entry_hash="hash-1",
        video_id="video-1",
    )
    assert (payload, created) == ({"id": "ie-1", "video_id": "v1"}, True)

    conflict_insert = _ScriptedConn(scripts=[("INSERT INTO ingest_events", _Result(rows=[]))])
    conflict_read = _ScriptedConn(
        scripts=[("FROM ingest_events", _Result(rows=[{"id": "ie-2", "video_id": "v2"}]))]
    )
    conflict_store = _build_store(_ScriptedEngine(begin_conns=[conflict_insert, conflict_read]))
    payload, created = conflict_store.create_ingest_event(
        subscription_id="sub-1",
        feed_guid=None,
        feed_link=None,
        entry_hash="hash-2",
        video_id="video-2",
    )
    assert (payload, created) == ({"id": "ie-2", "video_id": "v2"}, False)

    missing_insert = _ScriptedConn(scripts=[("INSERT INTO ingest_events", _Result(rows=[]))])
    missing_read = _ScriptedConn(scripts=[("FROM ingest_events", _Result(rows=[]))])
    missing_store = _build_store(_ScriptedEngine(begin_conns=[missing_insert, missing_read]))
    with pytest.raises(RuntimeError, match="failed to create or fetch ingest_event"):
        missing_store.create_ingest_event(
            subscription_id="sub-1",
            feed_guid=None,
            feed_link=None,
            entry_hash="hash-3",
            video_id="video-3",
        )


def test_create_queued_job_integrity_error_recovers_from_existing() -> None:
    integrity = IntegrityError("INSERT INTO jobs", {"idempotency_key": "dup"}, Exception("dup"))
    insert_conn = _ScriptedConn(scripts=[("INSERT INTO jobs", integrity)])
    read_conn = _ScriptedConn(
        scripts=[("FROM jobs", _Result(rows=[{"id": "job-existing", "status": "queued"}]))]
    )
    store = _build_store(_ScriptedEngine(begin_conns=[insert_conn, read_conn]))
    payload, created = store.create_queued_job(
        video_id="video-1",
        idempotency_key="dup",
        mode="text_only",
    )
    assert (payload, created) == ({"id": "job-existing", "status": "queued"}, False)

    insert_conn_again = _ScriptedConn(scripts=[("INSERT INTO jobs", integrity)])
    read_missing = _ScriptedConn(scripts=[("FROM jobs", _Result(rows=[]))])
    store_raise = _build_store(_ScriptedEngine(begin_conns=[insert_conn_again, read_missing]))
    with pytest.raises(IntegrityError):
        store_raise.create_queued_job(video_id="video-1", idempotency_key="dup")

    success_insert = _ScriptedConn(
        scripts=[
            (
                "INSERT INTO jobs",
                _Result(rows=[{"id": "job-new", "status": "queued", "mode": None}]),
            )
        ]
    )
    success_store = _build_store(_ScriptedEngine(begin_conns=[success_insert]))
    payload, created = success_store.create_queued_job(video_id="video-1", idempotency_key="ok")
    assert created is True
    assert payload["id"] == "job-new"


def test_mark_job_running_handles_transition_conflict_and_missing() -> None:
    transitioned_conn = _ScriptedConn(
        scripts=[("UPDATE jobs", _Result(rows=[{"id": "job-1", "status": "running"}]))]
    )
    transitioned_store = _build_store(_ScriptedEngine(begin_conns=[transitioned_conn]))
    assert transitioned_store.mark_job_running(job_id="job-1") == {
        "id": "job-1",
        "status": "running",
        "transitioned": True,
    }

    conflict_conn = _ScriptedConn(
        scripts=[
            ("UPDATE jobs", _Result(rows=[])),
            ("SELECT id::text AS id, status", _Result(rows=[{"id": "job-2", "status": "running"}])),
        ]
    )
    conflict_store = _build_store(_ScriptedEngine(begin_conns=[conflict_conn]))
    assert conflict_store.mark_job_running(job_id="job-2") == {
        "id": "job-2",
        "status": "running",
        "transitioned": False,
        "conflict": "already_running",
    }

    missing_conn = _ScriptedConn(
        scripts=[
            ("UPDATE jobs", _Result(rows=[])),
            ("SELECT id::text AS id, status", _Result(rows=[])),
        ]
    )
    missing_store = _build_store(_ScriptedEngine(begin_conns=[missing_conn]))
    with pytest.raises(ValueError, match="job not found"):
        missing_store.mark_job_running(job_id="job-missing")


def test_get_job_with_video_and_status_helpers() -> None:
    lookup_conn = _ScriptedConn(
        scripts=[
            (
                "JOIN videos v",
                _Result(
                    rows=[
                        {
                            "job_id": "job-1",
                            "job_status": "queued",
                            "job_kind": "video_digest_v1",
                            "mode": None,
                            "overrides_json": None,
                            "idempotency_key": "idem-1",
                            "video_id": "video-1",
                            "platform": "youtube",
                            "video_uid": "u1",
                            "source_url": "https://example.com",
                            "title": "t",
                            "published_at": None,
                            "content_type": "video",
                        }
                    ]
                ),
            )
        ]
    )
    store = _build_store(_ScriptedEngine(begin_conns=[lookup_conn]))
    assert store.get_job_with_video(job_id="job-1")["job_id"] == "job-1"

    missing_lookup_conn = _ScriptedConn(scripts=[("JOIN videos v", _Result(rows=[]))])
    missing_store = _build_store(_ScriptedEngine(begin_conns=[missing_lookup_conn]))
    with pytest.raises(ValueError, match="job not found"):
        missing_store.get_job_with_video(job_id="job-missing")

    assert PostgresBusinessStore._to_vector_literal([1, 2.5]) == "[1.0000000000,2.5000000000]"
    with pytest.raises(ValueError, match="embedding vector is empty"):
        PostgresBusinessStore._to_vector_literal([])


def test_upsert_video_embeddings_validates_table_and_payload() -> None:
    store = _build_store(_ScriptedEngine(begin_conns=[]))
    assert store.upsert_video_embeddings(video_id="v", job_id="j", model="m", items=[]) == 0

    no_table_conn = _ScriptedConn(
        scripts=[("to_regclass('public.video_embeddings')", _Result(scalar=False))]
    )
    no_table_store = _build_store(_ScriptedEngine(begin_conns=[no_table_conn]))
    assert (
        no_table_store.upsert_video_embeddings(
            video_id="v",
            job_id="j",
            model="m",
            items=[{"content_type": "transcript", "embedding": [0.1], "chunk_text": "a"}],
        )
        == 0
    )

    invalid_type_conn = _ScriptedConn(
        scripts=[
            ("to_regclass('public.video_embeddings')", _Result(scalar=True)),
            ("DELETE FROM video_embeddings", _Result(rows=[])),
        ]
    )
    invalid_type_store = _build_store(_ScriptedEngine(begin_conns=[invalid_type_conn]))
    with pytest.raises(ValueError, match="invalid embedding content_type"):
        invalid_type_store.upsert_video_embeddings(
            video_id="v",
            job_id="j",
            model="m",
            items=[{"content_type": "invalid", "embedding": [0.1]}],
        )

    missing_vector_conn = _ScriptedConn(
        scripts=[
            ("to_regclass('public.video_embeddings')", _Result(scalar=True)),
            ("DELETE FROM video_embeddings", _Result(rows=[])),
        ]
    )
    missing_vector_store = _build_store(_ScriptedEngine(begin_conns=[missing_vector_conn]))
    with pytest.raises(ValueError, match="embedding payload missing numeric vector"):
        missing_vector_store.upsert_video_embeddings(
            video_id="v",
            job_id="j",
            model="m",
            items=[{"content_type": "transcript", "embedding": []}],
        )

    success_conn = _ScriptedConn(
        scripts=[
            ("to_regclass('public.video_embeddings')", _Result(scalar=True)),
            ("DELETE FROM video_embeddings", _Result(rows=[])),
            ("INSERT INTO video_embeddings", _Result(rows=[])),
            ("INSERT INTO video_embeddings", _Result(rows=[])),
        ]
    )
    success_store = _build_store(_ScriptedEngine(begin_conns=[success_conn]))
    count = success_store.upsert_video_embeddings(
        video_id="v",
        job_id="j",
        model="embedding-model",
        items=[
            {
                "content_type": "transcript",
                "chunk_index": 1,
                "chunk_text": "chunk A",
                "embedding": [0.1, 0.2],
                "metadata": {"lang": "en"},
            },
            {
                "content_type": "outline",
                "chunk_index": 2,
                "chunk_text": "chunk B",
                "embedding": [0.3, 0.4],
                "metadata": {},
            },
        ],
    )
    assert count == 2
    assert "CAST(:embedding AS vector(768))" in success_conn.calls[2]["sql"]


def test_search_video_embeddings_and_mark_status_paths() -> None:
    store = _build_store(_ScriptedEngine(begin_conns=[]))
    assert store.search_video_embeddings(query_embedding=[]) == []

    no_table_conn = _ScriptedConn(
        scripts=[("to_regclass('public.video_embeddings')", _Result(scalar=False))]
    )
    no_table_store = _build_store(_ScriptedEngine(begin_conns=[no_table_conn]))
    assert no_table_store.search_video_embeddings(query_embedding=[0.1]) == []

    search_conn = _ScriptedConn(
        scripts=[
            ("to_regclass('public.video_embeddings')", _Result(scalar=True)),
            (
                "FROM video_embeddings",
                _Result(
                    rows=[
                        {"id": "emb-1", "video_id": "v1", "job_id": "j1", "score": 0.9},
                    ]
                ),
            ),
        ]
    )
    search_store = _build_store(_ScriptedEngine(begin_conns=[search_conn]))
    rows = search_store.search_video_embeddings(
        query_embedding=[0.1, 0.2],
        limit=0,
        content_type="  OUTLINE  ",
    )
    assert rows == [{"id": "emb-1", "video_id": "v1", "job_id": "j1", "score": 0.9}]
    assert search_conn.calls[1]["params"]["limit"] == 1
    assert search_conn.calls[1]["params"]["content_type"] == "outline"

    mark_conn = _ScriptedConn(
        scripts=[("UPDATE jobs", _Result(rows=[{"id": "job-1", "status": "succeeded"}]))]
    )
    mark_store = _build_store(_ScriptedEngine(begin_conns=[mark_conn]))
    assert mark_store._mark_job_status(
        job_id="job-1",
        status="succeeded",
        error_message=None,
        artifact_digest_md=None,
        artifact_root=None,
        pipeline_final_status="succeeded",
        degradation_count=0,
        last_error_code=None,
        llm_required=None,
        llm_gate_passed=None,
        hard_fail_reason=None,
    ) == {"id": "job-1", "status": "succeeded", "transitioned": True}

    terminal_conn = _ScriptedConn(
        scripts=[
            ("UPDATE jobs", _Result(rows=[])),
            (
                "SELECT id::text AS id, status",
                _Result(rows=[{"id": "job-2", "status": "failed"}]),
            ),
        ]
    )
    terminal_store = _build_store(_ScriptedEngine(begin_conns=[terminal_conn]))
    assert terminal_store._mark_job_status(
        job_id="job-2",
        status="failed",
        error_message="boom",
        artifact_digest_md=None,
        artifact_root=None,
        pipeline_final_status="failed",
        degradation_count=1,
        last_error_code="ERR",
        llm_required=False,
        llm_gate_passed=False,
        hard_fail_reason="dispatch_timeout",
    ) == {
        "id": "job-2",
        "status": "failed",
        "transitioned": False,
        "conflict": "terminal_status",
    }

    with pytest.raises(ValueError, match="invalid succeeded status"):
        terminal_store.mark_job_succeeded(job_id="j", status="failed")
    with pytest.raises(ValueError, match="invalid pipeline_final_status"):
        terminal_store.mark_job_succeeded(job_id="j", pipeline_final_status="bad")
    with pytest.raises(ValueError, match="degradation_count must be >= 0"):
        terminal_store.mark_job_succeeded(job_id="j", degradation_count=-1)
    with pytest.raises(ValueError, match="invalid pipeline_final_status"):
        terminal_store.mark_job_failed(job_id="j", error_message="x", pipeline_final_status="bad")
    with pytest.raises(ValueError, match="degradation_count must be >= 0"):
        terminal_store.mark_job_failed(job_id="j", error_message="x", degradation_count=-1)

    delegating_store = _build_store(_ScriptedEngine(begin_conns=[]))
    observed: list[dict[str, Any]] = []

    def _capture_mark_job_status(**kwargs: Any) -> dict[str, Any]:
        observed.append(kwargs)
        return {"id": kwargs["job_id"], "status": kwargs["status"], "transitioned": True}

    delegating_store._mark_job_status = _capture_mark_job_status  # type: ignore[method-assign]
    assert (
        delegating_store.mark_job_succeeded(job_id="job-s", degradation_count=0)["status"]
        == "succeeded"
    )
    assert (
        delegating_store.mark_job_failed(job_id="job-f", error_message="boom")["status"] == "failed"
    )
    assert observed[0]["status"] == "succeeded"
    assert observed[1]["status"] == "failed"

    missing_mark_conn = _ScriptedConn(
        scripts=[
            ("UPDATE jobs", _Result(rows=[])),
            ("SELECT id::text AS id, status", _Result(rows=[])),
        ]
    )
    missing_mark_store = _build_store(_ScriptedEngine(begin_conns=[missing_mark_conn]))
    with pytest.raises(ValueError, match="job not found"):
        missing_mark_store._mark_job_status(
            job_id="missing",
            status="failed",
            error_message="boom",
            artifact_digest_md=None,
            artifact_root=None,
            pipeline_final_status="failed",
            degradation_count=0,
            last_error_code=None,
            llm_required=None,
            llm_gate_passed=None,
            hard_fail_reason=None,
        )
