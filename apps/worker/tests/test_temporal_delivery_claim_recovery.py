from __future__ import annotations

import importlib
from typing import Any

from worker.temporal import activities_delivery


class _FakeMappingsResult:
    def __init__(self, *, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def mappings(self) -> _FakeMappingsResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _CaptureClaimConn:
    def __init__(self) -> None:
        self.executed_sql: str | None = None
        self.executed_params: dict[str, Any] | None = None

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeMappingsResult:
        sql = getattr(statement, "text", str(statement))
        self.executed_sql = " ".join(sql.split())
        self.executed_params = dict(params or {})
        return _FakeMappingsResult(rows=[{"delivery_id": "delivery-1", "status": "queued"}])


def test_claim_due_failed_deliveries_reclaims_stale_queued_rows() -> None:
    module = importlib.reload(activities_delivery)
    conn = _CaptureClaimConn()

    rows = module._claim_due_failed_deliveries(conn, limit=20)

    assert rows == [{"delivery_id": "delivery-1", "status": "queued"}]
    assert conn.executed_sql is not None
    assert "status = 'failed'" in conn.executed_sql
    assert "status = 'queued'" in conn.executed_sql
    assert "attempt_count > 0" in conn.executed_sql
    assert "next_retry_at IS NULL" in conn.executed_sql
    assert "attempt_count = 0" in conn.executed_sql
    assert (
        "updated_at <= NOW() - ( CAST(:claim_timeout_minutes AS TEXT) || ' minutes' )::INTERVAL"
        in (conn.executed_sql)
    )
    assert conn.executed_params is not None
    assert conn.executed_params["limit"] == 20
    assert (
        conn.executed_params["claim_timeout_minutes"] == module.DELIVERY_RETRY_CLAIM_TIMEOUT_MINUTES
    )
