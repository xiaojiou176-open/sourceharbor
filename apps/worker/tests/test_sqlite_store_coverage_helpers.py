from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Self

from apps.worker.worker.state import sqlite_store
from apps.worker.worker.state.sqlite_store import SQLiteStateStore


class _ModelV2:
    def model_dump(self) -> dict[str, Any]:
        return {"v2": True}


class _ModelV1:
    def dict(self) -> dict[str, Any]:
        return {"v1": True}


class _IsoValue:
    def isoformat(self) -> str:
        return "custom-iso"


class _IsoRaises:
    def isoformat(self) -> str:
        raise RuntimeError("boom")

    def __str__(self) -> str:
        return "iso-fallback"


def test_json_helpers_cover_serialization_edge_branches(tmp_path: Path) -> None:
    now = datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
    payload = {
        "list": [1, 2],
        "tuple": ("a", "b"),
        "set": {"x", "y"},
        "non_ascii": "你好",
        "date": date(2026, 3, 1),
        "datetime": now,
        "path": tmp_path / "artifact.txt",
        "model_v2": _ModelV2(),
        "model_v1": _ModelV1(),
        "iso": _IsoValue(),
        "fallback": object(),
    }

    dumped = sqlite_store._json_dumps(payload)
    assert dumped is not None
    assert "你好" in dumped
    assert "\\u4f60\\u597d" not in dumped
    loaded = sqlite_store._json_loads(dumped)
    assert loaded is not None
    assert loaded["tuple"] == ["a", "b"]
    assert sorted(loaded["set"]) == ["x", "y"]
    assert loaded["path"].endswith("artifact.txt")
    assert loaded["model_v2"] == {"v2": True}
    assert loaded["model_v1"] == {"v1": True}
    assert loaded["iso"] == "custom-iso"
    assert loaded["fallback"].startswith("<object object")

    assert sqlite_store._json_dumps(None) is None
    assert sqlite_store._json_loads("{broken-json") is None
    assert sqlite_store._json_fallback(now) == now.isoformat()
    assert sqlite_store._json_fallback(tmp_path / "x.txt").endswith("x.txt")
    assert sqlite_store._json_fallback(("a", "b")) == ["a", "b"]
    assert sqlite_store._json_fallback(_ModelV2()) == {"v2": True}
    assert sqlite_store._json_fallback(_ModelV1()) == {"v1": True}
    assert sqlite_store._json_fallback(_IsoValue()) == "custom-iso"
    assert sqlite_store._json_fallback(_IsoRaises()) == "iso-fallback"
    assert sqlite_store._json_fallback(object()).startswith("<object object")
    assert sqlite_store._to_jsonable(_IsoRaises()) == "iso-fallback"
    assert sqlite_store._is_expired(None) is True


def test_utc_now_iso_returns_utc_timestamp_without_microseconds() -> None:
    value = sqlite_store._utc_now_iso()

    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo == UTC
    assert parsed.microsecond == 0


class _EnsureColumnConn:
    def __init__(self) -> None:
        self.alter_sql: list[str] = []

    def execute(self, sql: str):
        if sql.startswith("PRAGMA table_info"):
            return self
        if sql.startswith("ALTER TABLE"):
            self.alter_sql.append(sql)
            return self
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchall(self) -> list[dict[str, Any]]:
        return [{"name": "existing_col"}]


def test_ensure_column_adds_missing_column() -> None:
    store = SQLiteStateStore.__new__(SQLiteStateStore)
    conn = _EnsureColumnConn()
    store._ensure_column(conn, "step_runs", "new_col", "TEXT")
    assert conn.alter_sql == ["ALTER TABLE step_runs ADD COLUMN new_col TEXT"]


def test_ensure_column_skips_existing_column() -> None:
    store = SQLiteStateStore.__new__(SQLiteStateStore)
    conn = _EnsureColumnConn()
    store._ensure_column(conn, "step_runs", "existing_col", "TEXT")
    assert conn.alter_sql == []


def test_connect_sets_pragmas_and_row_factory(monkeypatch) -> None:
    store = SQLiteStateStore.__new__(SQLiteStateStore)
    store._db_path = Path("/tmp/sqlite-store-connect-test.db")
    calls: list[str] = []

    class _FakeConnection:
        def __init__(self) -> None:
            self.row_factory: Any = None

        def execute(self, sql: str) -> None:
            calls.append(sql)

    fake_conn = _FakeConnection()
    monkeypatch.setattr(sqlite_store.sqlite3, "connect", lambda _: fake_conn)

    connected = store._connect()
    assert connected is fake_conn
    assert fake_conn.row_factory == sqlite3.Row
    assert calls == ["PRAGMA journal_mode=WAL;", "PRAGMA foreign_keys=ON;"]


def test_init_creates_nested_parent_directories_before_opening_db(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "level" / "state.db"
    assert db_path.parent.exists() is False

    store = SQLiteStateStore(str(db_path))

    assert db_path.parent.is_dir()
    assert store.next_attempt(job_id="job-init") == 1


def test_ensure_tables_backfills_legacy_schema_columns_and_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-state.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE step_runs (
                job_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                error_json TEXT,
                UNIQUE(job_id, step_name, attempt)
            );
            CREATE TABLE locks (
                lock_key TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE checkpoints (
                job_id TEXT PRIMARY KEY,
                last_completed_step TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    SQLiteStateStore(str(db_path))
    with sqlite3.connect(str(db_path)) as conn:
        step_runs_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(step_runs)").fetchall()
        }
        step_runs_column_types = {
            str(row[1]): str(row[2])
            for row in conn.execute("PRAGMA table_info(step_runs)").fetchall()
        }
        checkpoints_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(checkpoints)").fetchall()
        }
        checkpoints_column_types = {
            str(row[1]): str(row[2])
            for row in conn.execute("PRAGMA table_info(checkpoints)").fetchall()
        }
        step_runs_indexes = {
            str(row[1]) for row in conn.execute("PRAGMA index_list(step_runs)").fetchall()
        }

    assert {"error_kind", "retry_meta_json", "result_json", "cache_key"}.issubset(step_runs_columns)
    assert "payload_json" in checkpoints_columns
    assert "idx_step_runs_job_id_step_name_cache_key" in step_runs_indexes
    assert step_runs_column_types["error_kind"] == "TEXT"
    assert step_runs_column_types["retry_meta_json"] == "TEXT"
    assert step_runs_column_types["result_json"] == "TEXT"
    assert step_runs_column_types["cache_key"] == "TEXT"
    assert checkpoints_column_types["payload_json"] == "TEXT"


def test_acquire_lock_returns_false_when_insert_race_row_disappears(monkeypatch) -> None:
    store = SQLiteStateStore.__new__(SQLiteStateStore)

    class _RaceConn:
        def __init__(self) -> None:
            self.select_count = 0

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def execute(self, sql: str, params: tuple[Any, ...]):
            if sql.startswith("SELECT owner, expires_at"):
                self.select_count += 1
                return self
            if sql.startswith("INSERT INTO locks"):
                raise sqlite3.IntegrityError("race won by another worker")
            raise AssertionError(f"unexpected SQL: {sql}")

        def fetchone(self):
            return None

    race_conn = _RaceConn()
    monkeypatch.setattr(store, "_connect", lambda: race_conn)
    assert store.acquire_lock("phase2.poll_feeds", "worker-A", 60) is False


def test_get_latest_step_run_returns_none_for_missing_record(tmp_path: Path) -> None:
    store = SQLiteStateStore(str(tmp_path / "state.db"))
    assert store.get_latest_step_run(job_id="job-missing", step_name="step-x") is None


def test_apps_module_next_attempt_and_release_lock_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = sqlite_store.SQLiteStateStore(str(db_path))

    assert store.next_attempt(job_id="job-a") == 1
    store.mark_step_running(job_id="job-a", step_name="step-1", attempt=1)
    store.mark_step_running(job_id="job-a", step_name="step-2", attempt=3)
    assert store.next_attempt(job_id="job-a") == 4
    assert store.next_attempt(job_id="job-b") == 1

    assert store.acquire_lock("lock-a", "owner-a", 60) is True
    assert store.acquire_lock("lock-b", "owner-a", 60) is True

    store.release_lock("lock-a", "owner-b")
    with sqlite3.connect(str(db_path)) as conn:
        still_locked = conn.execute(
            "SELECT COUNT(*) FROM locks WHERE lock_key = ? AND owner = ?",
            ("lock-a", "owner-a"),
        ).fetchone()
    assert still_locked is not None
    assert int(still_locked[0]) == 1

    store.release_lock("lock-a", "owner-a")
    with sqlite3.connect(str(db_path)) as conn:
        lock_a = conn.execute(
            "SELECT COUNT(*) FROM locks WHERE lock_key = ?",
            ("lock-a",),
        ).fetchone()
        lock_b = conn.execute(
            "SELECT COUNT(*) FROM locks WHERE lock_key = ?",
            ("lock-b",),
        ).fetchone()
    assert lock_a is not None
    assert lock_b is not None
    assert int(lock_a[0]) == 0
    assert int(lock_b[0]) == 1


def test_apps_module_next_attempt_scopes_to_job_and_highest_attempt(tmp_path: Path) -> None:
    store = sqlite_store.SQLiteStateStore(str(tmp_path / "state.db"))

    store.mark_step_running(job_id="job-a", step_name="step-1", attempt=2)
    store.mark_step_running(job_id="job-a", step_name="step-2", attempt=5)
    store.mark_step_running(job_id="job-b", step_name="step-1", attempt=1)

    assert store.next_attempt(job_id="job-a") == 6
    assert store.next_attempt(job_id="job-b") == 2
    assert store.next_attempt(job_id="job-c") == 1


def test_apps_module_release_lock_deletes_only_matching_owner(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = sqlite_store.SQLiteStateStore(str(db_path))

    assert store.acquire_lock("lock-a", "owner-a", 60) is True
    assert store.acquire_lock("lock-b", "owner-b", 60) is True

    store.release_lock("lock-a", "owner-b")
    store.release_lock("lock-b", "owner-b")

    with sqlite3.connect(str(db_path)) as conn:
        remaining = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT lock_key, owner FROM locks ORDER BY lock_key"
            ).fetchall()
        }

    assert remaining == {"lock-a": "owner-a"}


def test_apps_module_checkpoint_roundtrip_with_none_payload_and_json_guard(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = sqlite_store.SQLiteStateStore(str(db_path))

    assert store.get_checkpoint("job-checkpoint") is None

    store.update_checkpoint(
        job_id="job-checkpoint",
        last_completed_step="collect_comments",
        payload=None,
    )
    checkpoint = store.get_checkpoint("job-checkpoint")
    assert checkpoint is not None
    assert checkpoint["last_completed_step"] == "collect_comments"
    assert checkpoint["payload"] is None
    assert checkpoint["payload_json"] is None

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE checkpoints SET payload_json = ? WHERE job_id = ?",
            ("{broken", "job-checkpoint"),
        )

    broken_payload_checkpoint = store.get_checkpoint("job-checkpoint")
    assert broken_payload_checkpoint is not None
    assert broken_payload_checkpoint["payload"] is None

    store.update_checkpoint(
        job_id="job-checkpoint",
        last_completed_step="digest",
        payload={"attempt": 2, "ok": True},
    )
    final_checkpoint = store.get_checkpoint("job-checkpoint")
    assert final_checkpoint is not None
    assert final_checkpoint["last_completed_step"] == "digest"
    assert final_checkpoint["payload"] == {"attempt": 2, "ok": True}
    assert isinstance(final_checkpoint["payload_json"], str)


def test_apps_module_update_and_get_checkpoint_keep_latest_row_state(
    monkeypatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "state.db"
    store = sqlite_store.SQLiteStateStore(str(db_path))
    timestamps = iter(["2026-03-10T12:00:00+00:00", "2026-03-10T12:00:05+00:00"])
    monkeypatch.setattr(sqlite_store, "_utc_now_iso", lambda: next(timestamps))

    store.update_checkpoint(
        job_id="job-upsert",
        last_completed_step="download_media",
        payload={"attempt": 1, "items": ["a"]},
    )
    store.update_checkpoint(
        job_id="job-upsert",
        last_completed_step="extract_frames",
        payload={"attempt": 2, "items": ["b"]},
    )

    checkpoint = store.get_checkpoint("job-upsert")
    assert checkpoint is not None
    assert checkpoint["last_completed_step"] == "extract_frames"
    assert checkpoint["updated_at"] == "2026-03-10T12:00:05+00:00"
    assert checkpoint["payload"] == {"attempt": 2, "items": ["b"]}
    assert checkpoint["payload_json"] == '{"attempt": 2, "items": ["b"]}'
