from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from worker.temporal import activities_entry


class _StoreStub:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_consumption_batch(self, *, batch_id: str) -> dict[str, object]:
        self.calls.append(("get", {"batch_id": batch_id}))
        return {"id": batch_id, "status": "frozen"}

    def prepare_consumption_batch(self, **kwargs) -> dict[str, object]:
        self.calls.append(("prepare", dict(kwargs)))
        return {"ok": True, "consumption_batch_id": "batch-1"}

    def mark_consumption_batch_materialized(self, **kwargs) -> dict[str, object]:
        self.calls.append(("materialized", dict(kwargs)))
        return {"id": kwargs["batch_id"], "status": "materialized"}

    def mark_consumption_batch_closed(self, **kwargs) -> dict[str, object]:
        self.calls.append(("closed", dict(kwargs)))
        return {"id": kwargs["batch_id"], "status": "closed"}

    def mark_consumption_batch_failed(self, **kwargs) -> dict[str, object]:
        self.calls.append(("failed", dict(kwargs)))
        return {"id": kwargs["batch_id"], "status": "failed"}


def test_reader_batch_activity_wrappers_delegate_to_store(monkeypatch: pytest.MonkeyPatch) -> None:
    created_stores: list[_StoreStub] = []

    def _factory(database_url: str) -> _StoreStub:
        store = _StoreStub(database_url)
        created_stores.append(store)
        return store

    monkeypatch.setattr(
        activities_entry.Settings,
        "from_env",
        staticmethod(lambda: SimpleNamespace(database_url="postgresql://sourceharbor")),
    )
    monkeypatch.setattr(activities_entry, "PostgresBusinessStore", _factory)

    assert asyncio.run(
        activities_entry.load_consumption_batch_activity({"consumption_batch_id": "batch-1"})
    ) == {"id": "batch-1", "status": "frozen"}
    assert asyncio.run(
        activities_entry.prepare_consumption_batch_activity(
            {
                "trigger_mode": "manual",
                "timezone_name": "America/Los_Angeles",
                "requested_by": "tester",
                "requested_trace_id": "trace-1",
                "subscription_id": "sub-1",
                "platform": "youtube",
                "max_items": 5,
            }
        )
    ) == {"ok": True, "consumption_batch_id": "batch-1"}
    assert asyncio.run(
        activities_entry.mark_consumption_batch_materialized_activity(
            {
                "consumption_batch_id": "batch-1",
                "processed_job_count": 2,
                "succeeded_job_count": 1,
                "failed_job_count": 1,
                "process_summary_json": {"jobs": ["job-1"]},
            }
        )
    ) == {"id": "batch-1", "status": "materialized"}
    assert asyncio.run(
        activities_entry.mark_consumption_batch_closed_activity(
            {
                "consumption_batch_id": "batch-1",
                "process_summary_json": {"status": "done"},
            }
        )
    ) == {"id": "batch-1", "status": "closed"}
    assert asyncio.run(
        activities_entry.mark_consumption_batch_failed_activity(
            {
                "consumption_batch_id": "batch-1",
                "error": "boom",
                "reset_items_to_pending": False,
            }
        )
    ) == {"id": "batch-1", "status": "failed"}

    assert all(store.database_url == "postgresql://sourceharbor" for store in created_stores)
    assert created_stores[0].calls == [("get", {"batch_id": "batch-1"})]
    assert created_stores[1].calls[0][0] == "prepare"
    assert created_stores[2].calls == [
        (
            "materialized",
            {
                "batch_id": "batch-1",
                "processed_job_count": 2,
                "succeeded_job_count": 1,
                "failed_job_count": 1,
                "process_summary_json": {"jobs": ["job-1"]},
            },
        )
    ]
    assert created_stores[3].calls == [
        ("closed", {"batch_id": "batch-1", "process_summary_json": {"status": "done"}})
    ]
    assert created_stores[4].calls == [
        (
            "failed",
            {
                "batch_id": "batch-1",
                "error_message": "boom",
                "reset_items_to_pending": False,
            },
        )
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"consumption_batch_id": ""},
    ],
)
def test_reader_batch_activity_wrappers_require_batch_id(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="consumption_batch_id is required"):
        asyncio.run(activities_entry.load_consumption_batch_activity(payload))
    with pytest.raises(ValueError, match="consumption_batch_id is required"):
        asyncio.run(activities_entry.materialize_reader_batch_activity(payload))


def test_materialize_reader_batch_activity_uses_reader_pipeline_service_and_closes_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = SimpleNamespace(closed=False)

    def _close() -> None:
        db.closed = True

    db.close = _close

    class _ReaderPipelineServiceStub:
        def __init__(self, _db) -> None:
            assert _db is db

        def materialize_batch(self, *, batch_id: uuid.UUID) -> dict[str, object]:
            return {"consumption_batch_id": str(batch_id), "published_document_count": 1}

    monkeypatch.setattr(activities_entry, "SessionLocal", lambda: db)
    monkeypatch.setattr(activities_entry, "ReaderPipelineService", _ReaderPipelineServiceStub)

    payload = asyncio.run(
        activities_entry.materialize_reader_batch_activity(
            {"consumption_batch_id": str(uuid.uuid4())}
        )
    )

    assert payload["published_document_count"] == 1
    assert db.closed is True
