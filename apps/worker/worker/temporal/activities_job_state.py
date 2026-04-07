from __future__ import annotations

from os import getenv
from typing import Any

from worker.config import Settings
from worker.state.mirrored_sqlite_store import MirroredSQLiteStateStore
from worker.state.postgres_store import PostgresBusinessStore

try:
    from temporalio import activity
except ModuleNotFoundError:  # pragma: no cover

    class _ActivityFallback:
        @staticmethod
        def defn(name: str | None = None):
            def _decorator(func):
                return func

            return _decorator

    activity = _ActivityFallback()


PIPELINE_FINAL_STATUSES = {"succeeded", "degraded", "failed"}
SQLiteStateStore = MirroredSQLiteStateStore


def _build_runtime_sqlite_store(settings: Settings) -> Any:
    mirror_paths: list[str] = []
    api_state_path = str(getenv("SQLITE_STATE_PATH", "")).strip()
    if api_state_path:
        mirror_paths.append(api_state_path)
    store_cls = SQLiteStateStore
    if hasattr(store_cls, "from_paths"):
        return store_cls.from_paths(
            primary_path=settings.sqlite_path,
            mirror_paths=mirror_paths,
        )
    return store_cls(settings.sqlite_path)


def _to_pipeline_final_status(value: Any, *, fallback: str | None) -> str | None:
    for candidate in (value, fallback):
        if not isinstance(candidate, str):
            continue
        normalized = candidate.strip().lower()
        if normalized in PIPELINE_FINAL_STATUSES:
            return normalized
    return None


def _coerce_non_negative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str):
        raw = value.strip()
        if raw.isdigit():
            return int(raw)
    return None


def _resolve_degradation_count(payload: dict[str, Any]) -> int | None:
    explicit = _coerce_non_negative_int(payload.get("degradation_count"))
    if explicit is not None:
        return explicit
    degradations = payload.get("degradations")
    if isinstance(degradations, list):
        return len(degradations)
    return 0


def _sanitize_error_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    code = normalized.splitlines()[0].strip()
    if not code:
        return None
    return code[:128]


def _derive_error_code(value: Any) -> str | None:
    raw = _sanitize_error_code(value)
    if raw is None:
        return None
    prefix = raw.split(":", 1)[0].strip()
    return (prefix or raw)[:128]


def _resolve_last_error_code(payload: dict[str, Any]) -> str | None:
    direct = _sanitize_error_code(payload.get("last_error_code")) or _sanitize_error_code(
        payload.get("error_code")
    )
    if direct is not None:
        return direct

    degradations = payload.get("degradations")
    if isinstance(degradations, list):
        for item in reversed(degradations):
            if not isinstance(item, dict):
                continue
            for key in ("error_code", "error_kind", "reason"):
                candidate = _sanitize_error_code(item.get(key))
                if candidate is not None:
                    return candidate

    return _derive_error_code(payload.get("fatal_error")) or _derive_error_code(
        payload.get("error")
    )


@activity.defn(name="mark_running_activity")
async def mark_running_activity(job_id: str) -> dict[str, Any]:
    settings = Settings.from_env()
    sqlite_store = _build_runtime_sqlite_store(settings)
    pg_store = PostgresBusinessStore(settings.database_url)

    attempt = sqlite_store.next_attempt(job_id=job_id)
    sqlite_store.mark_step_running(job_id=job_id, step_name="mark_running", attempt=attempt)

    running_job = pg_store.mark_job_running(job_id=job_id)
    if running_job.get("transitioned") is not True:
        reason = str(running_job.get("conflict") or f"invalid_status:{running_job.get('status')}")
        sqlite_store.mark_step_finished(
            job_id=job_id,
            step_name="mark_running",
            attempt=attempt,
            status="failed",
            error_payload={"reason": reason},
        )
        raise ValueError(f"job {job_id} is not runnable, reason={reason}")

    sqlite_store.mark_step_finished(
        job_id=job_id,
        step_name="mark_running",
        attempt=attempt,
        status="succeeded",
    )
    sqlite_store.update_checkpoint(job_id=job_id, last_completed_step="mark_running")
    return {"job_id": job_id, "attempt": attempt, "status": "running"}


@activity.defn(name="reconcile_stale_queued_jobs_activity")
async def reconcile_stale_queued_jobs_activity(
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = Settings.from_env()
    pg_store = PostgresBusinessStore(settings.database_url)
    payload = payload or {}

    timeout_minutes = _coerce_non_negative_int(payload.get("timeout_minutes"))
    if timeout_minutes is None:
        timeout_minutes = 15
    limit = _coerce_non_negative_int(payload.get("limit"))
    if limit is None or limit <= 0:
        limit = 200

    stale_jobs = pg_store.fail_stale_queued_jobs(
        timeout_seconds=max(60, timeout_minutes * 60),
        limit=limit,
    )
    return {
        "ok": True,
        "timeout_minutes": timeout_minutes,
        "checked_limit": limit,
        "recovered": len(stale_jobs),
        "job_ids": [str(item["id"]) for item in stale_jobs],
    }


@activity.defn(name="run_pipeline_activity")
async def run_pipeline_activity(payload: dict[str, Any]) -> dict[str, Any]:
    from worker.pipeline.runner import run_pipeline

    settings = Settings.from_env()
    sqlite_store = _build_runtime_sqlite_store(settings)
    pg_store = PostgresBusinessStore(settings.database_url)

    job_id = str(payload["job_id"])
    attempt = int(payload["attempt"])
    mode = str(payload.get("mode") or "").strip() or None
    payload_overrides = payload.get("overrides")
    overrides = dict(payload_overrides) if isinstance(payload_overrides, dict) else None
    job_record = pg_store.get_job_with_video(job_id=job_id)
    if mode is None:
        mode = str(job_record.get("mode") or "").strip() or "full"
    if overrides is None:
        job_overrides = job_record.get("overrides_json")
        if isinstance(job_overrides, dict):
            overrides = dict(job_overrides)
    content_type = str(job_record.get("content_type") or "video").strip().lower()
    if content_type not in ("video", "article"):
        content_type = "video"

    return await run_pipeline(
        settings,
        sqlite_store,
        pg_store,
        job_id=job_id,
        attempt=attempt,
        mode=mode,
        overrides=overrides,
        content_type=content_type,
    )


@activity.defn(name="mark_succeeded_activity")
async def mark_succeeded_activity(payload: dict[str, Any]) -> dict[str, Any]:
    settings = Settings.from_env()
    sqlite_store = _build_runtime_sqlite_store(settings)
    pg_store = PostgresBusinessStore(settings.database_url)

    job_id = str(payload["job_id"])
    attempt = int(payload["attempt"])
    final_status = str(payload.get("final_status", "succeeded"))
    artifacts = payload.get("artifacts") or {}
    digest_path = artifacts.get("digest")
    artifact_root = payload.get("artifact_dir")
    pipeline_final_status = (
        _to_pipeline_final_status(payload.get("pipeline_final_status"), fallback=final_status)
        or "succeeded"
    )
    degradation_count = _resolve_degradation_count(payload)
    last_error_code = _resolve_last_error_code(payload)
    llm_required = payload.get("llm_required")
    if not isinstance(llm_required, bool):
        llm_required = None
    llm_gate_passed = payload.get("llm_gate_passed")
    if not isinstance(llm_gate_passed, bool):
        llm_gate_passed = None
    hard_fail_reason = payload.get("hard_fail_reason")
    if not isinstance(hard_fail_reason, str) or not hard_fail_reason.strip():
        hard_fail_reason = None
    step_name = "mark_succeeded"

    sqlite_store.mark_step_running(job_id=job_id, step_name=step_name, attempt=attempt)
    job = pg_store.mark_job_succeeded(
        job_id=job_id,
        status="succeeded",
        artifact_digest_md=str(digest_path) if digest_path else None,
        artifact_root=str(artifact_root) if artifact_root else None,
        pipeline_final_status=pipeline_final_status,
        degradation_count=degradation_count,
        last_error_code=last_error_code,
        llm_required=llm_required,
        llm_gate_passed=llm_gate_passed,
        hard_fail_reason=hard_fail_reason,
    )
    if job.get("transitioned", True) is not True:
        reason = str(job.get("conflict") or f"invalid_status:{job.get('status')}")
        sqlite_store.mark_step_finished(
            job_id=job_id,
            step_name=step_name,
            attempt=attempt,
            status="failed",
            error_payload={"reason": reason},
        )
        raise ValueError(f"job {job_id} terminal update blocked, reason={reason}")
    sqlite_store.mark_step_finished(
        job_id=job_id,
        step_name=step_name,
        attempt=attempt,
        status="succeeded",
    )
    sqlite_store.update_checkpoint(job_id=job_id, last_completed_step=step_name)
    return {
        "job_id": job_id,
        "attempt": attempt,
        "status": final_status,
        "db_status": job["status"],
        "pipeline_final_status": job.get("pipeline_final_status"),
        "degradation_count": job.get("degradation_count"),
        "last_error_code": job.get("last_error_code"),
        "llm_required": job.get("llm_required"),
        "llm_gate_passed": job.get("llm_gate_passed"),
        "hard_fail_reason": job.get("hard_fail_reason"),
    }


@activity.defn(name="mark_failed_activity")
async def mark_failed_activity(payload: dict[str, Any]) -> dict[str, Any]:
    settings = Settings.from_env()
    sqlite_store = _build_runtime_sqlite_store(settings)
    pg_store = PostgresBusinessStore(settings.database_url)

    job_id = str(payload["job_id"])
    attempt = int(payload["attempt"])
    error = str(payload.get("error", "unknown_error"))
    pipeline_final_status = (
        _to_pipeline_final_status(payload.get("pipeline_final_status"), fallback="failed")
        or "failed"
    )
    degradation_count = _resolve_degradation_count(payload)
    last_error_code = _resolve_last_error_code(payload)
    llm_required = payload.get("llm_required")
    if not isinstance(llm_required, bool):
        llm_required = True
    llm_gate_passed = payload.get("llm_gate_passed")
    if not isinstance(llm_gate_passed, bool):
        llm_gate_passed = False
    hard_fail_reason = payload.get("hard_fail_reason")
    if not isinstance(hard_fail_reason, str) or not hard_fail_reason.strip():
        hard_fail_reason = _derive_error_code(error) or "pipeline_failed"
    step_name = "mark_failed"

    sqlite_store.mark_step_running(job_id=job_id, step_name=step_name, attempt=attempt)
    job = pg_store.mark_job_failed(
        job_id=job_id,
        error_message=error,
        pipeline_final_status=pipeline_final_status,
        degradation_count=degradation_count,
        last_error_code=last_error_code,
        llm_required=llm_required,
        llm_gate_passed=llm_gate_passed,
        hard_fail_reason=hard_fail_reason,
    )
    if job.get("transitioned", True) is not True:
        reason = str(job.get("conflict") or f"invalid_status:{job.get('status')}")
        sqlite_store.mark_step_finished(
            job_id=job_id,
            step_name=step_name,
            attempt=attempt,
            status="failed",
            error_payload={"reason": reason},
        )
        raise ValueError(f"job {job_id} terminal update blocked, reason={reason}")
    sqlite_store.mark_step_finished(
        job_id=job_id,
        step_name=step_name,
        attempt=attempt,
        status="failed",
        error_payload={"error": error, "last_error_code": last_error_code},
    )
    sqlite_store.update_checkpoint(job_id=job_id, last_completed_step=step_name)
    return {
        "job_id": job_id,
        "attempt": attempt,
        "status": job["status"],
        "last_error_code": job.get("last_error_code"),
        "llm_required": job.get("llm_required"),
        "llm_gate_passed": job.get("llm_gate_passed"),
        "hard_fail_reason": job.get("hard_fail_reason"),
    }
