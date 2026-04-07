from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _is_expired(ts: str | None) -> bool:
    if not ts:
        return True
    try:
        return datetime.fromisoformat(ts) <= datetime.now(UTC)
    except ValueError:
        return True


def _json_dumps(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    normalized = _to_jsonable(payload)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _json_fallback(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, tuple)):
        return list(value)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump()  # pydantic v2
    if hasattr(value, "dict") and callable(value.dict):
        return value.dict()  # pydantic v1 compatibility
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    # Never fail step persistence because of metadata shape.
    return str(value)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return _to_jsonable(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):
        return _to_jsonable(value.dict())
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _json_loads(payload: str | None) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


class SQLiteStateStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _ensure_column(
        self, conn: sqlite3.Connection, table_name: str, column_name: str, definition: str
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in rows}
        if column_name in existing:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS step_runs (
                    job_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error_json TEXT,
                    error_kind TEXT,
                    retry_meta_json TEXT,
                    result_json TEXT,
                    cache_key TEXT,
                    UNIQUE(job_id, step_name, attempt)
                );
                CREATE INDEX IF NOT EXISTS idx_step_runs_job_id_step_name
                    ON step_runs(job_id, step_name);

                CREATE TABLE IF NOT EXISTS locks (
                    lock_key TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_locks_expires_at
                    ON locks(expires_at);

                CREATE TABLE IF NOT EXISTS checkpoints (
                    job_id TEXT PRIMARY KEY,
                    last_completed_step TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT
                );
                """
            )
            self._ensure_column(conn, "step_runs", "error_kind", "TEXT")
            self._ensure_column(conn, "step_runs", "retry_meta_json", "TEXT")
            self._ensure_column(conn, "step_runs", "result_json", "TEXT")
            self._ensure_column(conn, "step_runs", "cache_key", "TEXT")
            self._ensure_column(conn, "checkpoints", "payload_json", "TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_step_runs_job_id_step_name_cache_key
                    ON step_runs(job_id, step_name, cache_key)
                """
            )

    def next_attempt(self, *, job_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(attempt), 0) + 1 AS next_attempt FROM step_runs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return int(row["next_attempt"])

    def acquire_lock(self, lock_key: str, owner: str, ttl_seconds: int) -> bool:
        expires_at = (
            (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).replace(microsecond=0).isoformat()
        )
        with self._connect() as conn:
            row = conn.execute(
                "SELECT owner, expires_at FROM locks WHERE lock_key = ?",
                (lock_key,),
            ).fetchone()
            if row is None:
                try:
                    conn.execute(
                        "INSERT INTO locks (lock_key, owner, expires_at) VALUES (?, ?, ?)",
                        (lock_key, owner, expires_at),
                    )
                    return True
                except sqlite3.IntegrityError:
                    # Another worker won the race between SELECT and INSERT.
                    row = conn.execute(
                        "SELECT owner, expires_at FROM locks WHERE lock_key = ?",
                        (lock_key,),
                    ).fetchone()
                    if row is None:
                        return False

            if row["owner"] != owner and not _is_expired(row["expires_at"]):
                return False

            conn.execute(
                """
                UPDATE locks
                SET owner = ?, expires_at = ?
                WHERE lock_key = ?
                """,
                (owner, expires_at, lock_key),
            )
            return True

    def release_lock(self, lock_key: str, owner: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM locks WHERE lock_key = ? AND owner = ?",
                (lock_key, owner),
            )

    def mark_step_running(
        self, *, job_id: str, step_name: str, attempt: int, cache_key: str | None = None
    ) -> None:
        started_at = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO step_runs (
                    job_id, step_name, status, attempt, started_at, finished_at, error_json,
                    error_kind, retry_meta_json, result_json, cache_key
                ) VALUES (?, ?, 'running', ?, ?, NULL, NULL, NULL, NULL, NULL, ?)
                ON CONFLICT(job_id, step_name, attempt) DO UPDATE SET
                    status = 'running',
                    started_at = excluded.started_at,
                    finished_at = NULL,
                    error_json = NULL,
                    error_kind = NULL,
                    retry_meta_json = NULL,
                    result_json = NULL,
                    cache_key = excluded.cache_key
                """,
                (job_id, step_name, attempt, started_at, cache_key),
            )

    def mark_step_finished(
        self,
        *,
        job_id: str,
        step_name: str,
        attempt: int,
        status: str,
        error_payload: dict[str, Any] | None = None,
        error_kind: str | None = None,
        retry_meta: dict[str, Any] | None = None,
        result_payload: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> None:
        if status not in {"succeeded", "failed", "skipped"}:
            raise ValueError("status must be succeeded, failed, or skipped")

        now = _utc_now_iso()
        error_json = _json_dumps(error_payload)
        retry_meta_json = _json_dumps(retry_meta)
        result_json = _json_dumps(result_payload)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO step_runs (
                    job_id, step_name, status, attempt, started_at, finished_at, error_json,
                    error_kind, retry_meta_json, result_json, cache_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, step_name, attempt) DO UPDATE SET
                    status = excluded.status,
                    finished_at = excluded.finished_at,
                    error_json = excluded.error_json,
                    error_kind = excluded.error_kind,
                    retry_meta_json = excluded.retry_meta_json,
                    result_json = excluded.result_json,
                    cache_key = excluded.cache_key
                """,
                (
                    job_id,
                    step_name,
                    status,
                    attempt,
                    now,
                    now,
                    error_json,
                    error_kind,
                    retry_meta_json,
                    result_json,
                    cache_key,
                ),
            )

    def update_checkpoint(
        self,
        *,
        job_id: str,
        last_completed_step: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        now = _utc_now_iso()
        payload_json = _json_dumps(payload)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO checkpoints (job_id, last_completed_step, updated_at, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    last_completed_step = excluded.last_completed_step,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (job_id, last_completed_step, now, payload_json),
            )

    def get_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, last_completed_step, updated_at, payload_json
                FROM checkpoints
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            payload = dict(row)
            payload["payload"] = _json_loads(payload.get("payload_json"))
            return payload

    def get_latest_step_run(
        self,
        *,
        job_id: str,
        step_name: str,
        status: str | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any] | None:
        clauses = ["job_id = ?", "step_name = ?"]
        params: list[Any] = [job_id, step_name]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if cache_key:
            clauses.append("cache_key = ?")
            params.append(cache_key)

        query = f"""
            SELECT
                job_id,
                step_name,
                status,
                attempt,
                started_at,
                finished_at,
                error_json,
                error_kind,
                retry_meta_json,
                result_json,
                cache_key
            FROM step_runs
            WHERE {" AND ".join(clauses)}
            ORDER BY attempt DESC
            LIMIT 1
        """
        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            if row is None:
                return None
            payload = dict(row)
            payload["error"] = _json_loads(payload.get("error_json"))
            payload["retry_meta"] = _json_loads(payload.get("retry_meta_json"))
            payload["result"] = _json_loads(payload.get("result_json"))
            return payload
