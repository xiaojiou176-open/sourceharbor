from __future__ import annotations

import sqlite3
from pathlib import Path


def test_sqlite_state_init_schema_matches_runtime_contract(tmp_path) -> None:
    db_path = tmp_path / "state.db"
    sql_path = Path(__file__).resolve().parents[3] / "infra" / "sql" / "sqlite_state_init.sql"

    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(sql_path.read_text(encoding="utf-8"))

        step_runs_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(step_runs)").fetchall()
        }
        checkpoints_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(checkpoints)").fetchall()
        }
        step_runs_indexes = {
            str(row[1]) for row in conn.execute("PRAGMA index_list(step_runs)").fetchall()
        }

    assert {
        "job_id",
        "step_name",
        "status",
        "attempt",
        "started_at",
        "finished_at",
        "error_json",
        "error_kind",
        "retry_meta_json",
        "result_json",
        "cache_key",
    }.issubset(step_runs_columns)
    assert {"job_id", "last_completed_step", "updated_at", "payload_json"}.issubset(
        checkpoints_columns
    )
    assert "idx_step_runs_job_id_step_name_cache_key" in step_runs_indexes
