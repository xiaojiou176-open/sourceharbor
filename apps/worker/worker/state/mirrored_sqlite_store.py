from __future__ import annotations

from pathlib import Path
from typing import Any

from .sqlite_store import SQLiteStateStore


class MirroredSQLiteStateStore(SQLiteStateStore):
    """Primary SQLite state store with optional mirrored write targets.

    Read and lock semantics stay on the primary store. Step/checkpoint writes are
    mirrored to any configured secondary stores so API-side state views can
    consume the same execution trace without changing the primary worker path.
    """

    def __init__(self, primary: SQLiteStateStore, mirrors: list[SQLiteStateStore]) -> None:
        self._primary = primary
        self._mirrors = mirrors

    @classmethod
    def from_paths(
        cls, *, primary_path: str, mirror_paths: list[str] | None = None
    ) -> MirroredSQLiteStateStore:
        primary = SQLiteStateStore(primary_path)
        resolved_primary = Path(primary_path).expanduser().resolve()
        mirrors: list[SQLiteStateStore] = []
        for raw_path in mirror_paths or []:
            candidate = str(raw_path or "").strip()
            if not candidate:
                continue
            resolved_candidate = Path(candidate).expanduser().resolve()
            if resolved_candidate == resolved_primary:
                continue
            if any(Path(store._db_path).resolve() == resolved_candidate for store in mirrors):  # noqa: SLF001
                continue
            mirrors.append(SQLiteStateStore(str(resolved_candidate)))
        return cls(primary=primary, mirrors=mirrors)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._primary, name)

    def next_attempt(self, *, job_id: str) -> int:
        return self._primary.next_attempt(job_id=job_id)

    def acquire_lock(self, lock_key: str, owner: str, ttl_seconds: int) -> bool:
        return self._primary.acquire_lock(lock_key, owner, ttl_seconds)

    def release_lock(self, lock_key: str, owner: str) -> None:
        self._primary.release_lock(lock_key, owner)

    def mark_step_running(
        self, *, job_id: str, step_name: str, attempt: int, cache_key: str | None = None
    ) -> None:
        self._primary.mark_step_running(
            job_id=job_id,
            step_name=step_name,
            attempt=attempt,
            cache_key=cache_key,
        )
        for store in self._mirrors:
            store.mark_step_running(
                job_id=job_id,
                step_name=step_name,
                attempt=attempt,
                cache_key=cache_key,
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
        self._primary.mark_step_finished(
            job_id=job_id,
            step_name=step_name,
            attempt=attempt,
            status=status,
            error_payload=error_payload,
            error_kind=error_kind,
            retry_meta=retry_meta,
            result_payload=result_payload,
            cache_key=cache_key,
        )
        for store in self._mirrors:
            store.mark_step_finished(
                job_id=job_id,
                step_name=step_name,
                attempt=attempt,
                status=status,
                error_payload=error_payload,
                error_kind=error_kind,
                retry_meta=retry_meta,
                result_payload=result_payload,
                cache_key=cache_key,
            )

    def update_checkpoint(
        self,
        *,
        job_id: str,
        last_completed_step: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._primary.update_checkpoint(
            job_id=job_id,
            last_completed_step=last_completed_step,
            payload=payload,
        )
        for store in self._mirrors:
            store.update_checkpoint(
                job_id=job_id,
                last_completed_step=last_completed_step,
                payload=payload,
            )

    def get_checkpoint(self, job_id: str) -> dict[str, Any] | None:
        return self._primary.get_checkpoint(job_id)
