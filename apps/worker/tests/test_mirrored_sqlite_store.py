from __future__ import annotations

from pathlib import Path

from worker.state.mirrored_sqlite_store import MirroredSQLiteStateStore
from worker.state.sqlite_store import SQLiteStateStore


def test_mirrored_store_writes_step_runs_and_checkpoints_to_secondary_db(tmp_path: Path) -> None:
    primary = tmp_path / "worker.db"
    mirror = tmp_path / "api.db"
    store = MirroredSQLiteStateStore.from_paths(
        primary_path=str(primary),
        mirror_paths=[str(mirror)],
    )

    attempt = store.next_attempt(job_id="job-1")
    assert attempt == 1

    store.mark_step_running(job_id="job-1", step_name="mark_running", attempt=attempt)
    store.mark_step_finished(
        job_id="job-1",
        step_name="mark_running",
        attempt=attempt,
        status="succeeded",
        result_payload={"ok": True},
    )
    store.update_checkpoint(
        job_id="job-1",
        last_completed_step="mark_running",
        payload={"status": "succeeded"},
    )

    primary_store = SQLiteStateStore(str(primary))
    mirror_store = SQLiteStateStore(str(mirror))

    assert primary_store.next_attempt(job_id="job-1") == 2
    assert mirror_store.next_attempt(job_id="job-1") == 2
    assert primary_store.get_checkpoint("job-1") is not None
    assert mirror_store.get_checkpoint("job-1") is not None


def test_mirrored_store_dedupes_blank_and_primary_paths(tmp_path: Path) -> None:
    primary = tmp_path / "state.db"
    store = MirroredSQLiteStateStore.from_paths(
        primary_path=str(primary),
        mirror_paths=["", str(primary)],
    )

    store.mark_step_running(job_id="job-2", step_name="step", attempt=1)
    store.mark_step_finished(job_id="job-2", step_name="step", attempt=1, status="succeeded")

    primary_store = SQLiteStateStore(str(primary))
    assert primary_store.next_attempt(job_id="job-2") == 2
