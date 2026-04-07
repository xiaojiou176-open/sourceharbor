from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from worker.pipeline.policies import (
    build_retry_policy,
    classify_error,
    refresh_llm_media_input_dimension,
    retry_delay_seconds,
)
from worker.pipeline.types import (
    NON_DEGRADING_SKIP_REASONS,
    PIPELINE_MODE_SKIP_UPDATES,
    STEP_INPUT_KEYS,
    STEP_SETTING_KEYS,
    STEP_VERSIONS,
    CommandResult,
    PipelineContext,
    RetryCategory,
    StepExecution,
)

_DEFAULT_ARG_UNSET = object()


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, set):
        return [jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return jsonable(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):
        return jsonable(value.dict())
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.write_text(
        json.dumps(jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _legacy_step_cache_path(ctx: PipelineContext, step_name: str) -> Path:
    return ctx.cache_dir / f"{step_name}.json"


def _truncate_text(value: str, *, keep: int | None = None) -> str:
    resolved_keep = 240 if keep is None else keep
    if len(value) <= resolved_keep:
        return value
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"<<sha256:{digest}|len:{len(value)}>>"


def _normalize_for_signature(value: Any) -> Any:
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, dict):
        return {str(k): _normalize_for_signature(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_signature(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_for_signature(item) for item in value]
    return jsonable(value)


def _settings_subset(settings: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in keys:
        payload[key] = getattr(settings, key, None)
    return payload


def _step_input_payload(
    ctx: PipelineContext, state: dict[str, Any], step_name: str
) -> dict[str, Any]:
    state_keys = STEP_INPUT_KEYS.get(step_name, ())
    settings_keys = STEP_SETTING_KEYS.get(step_name, ())
    state_payload = {key: state.get(key) for key in state_keys}
    return {
        "state": _normalize_for_signature(state_payload),
        "settings": _normalize_for_signature(_settings_subset(ctx.settings, settings_keys)),
    }


def build_step_cache_info(
    ctx: PipelineContext, state: dict[str, Any], step_name: str
) -> dict[str, Any]:
    version = STEP_VERSIONS.get(step_name, "v1")
    payload = {
        "step": step_name,
        "version": version,
        "inputs": _step_input_payload(ctx, state, step_name),
    }
    signature = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()[:24]
    cache_key = f"{step_name}:{version}:{signature}"
    cache_path = ensure_dir(ctx.cache_dir / step_name) / f"{version}_{signature}.json"
    return {
        "step": step_name,
        "version": version,
        "signature": signature,
        "cache_key": cache_key,
        "cache_path": cache_path,
        "legacy_path": _legacy_step_cache_path(ctx, step_name),
    }


def _load_cache_execution(cache_path: Path) -> StepExecution | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(read_text_file(cache_path))
        execution = StepExecution.from_record(dict(payload))
    except Exception:
        return None
    if execution.status != "succeeded":
        return None
    return execution


def _load_step_execution_from_cache(
    cache_info: dict[str, Any],
) -> tuple[StepExecution | None, str | None]:
    cache_path = cache_info["cache_path"]
    execution = _load_cache_execution(cache_path)
    if execution is not None:
        return execution, "cache_hit"

    if str(cache_info.get("version") or "v1") != "v1":
        return None, None

    legacy_path = cache_info["legacy_path"]
    legacy_execution = _load_cache_execution(legacy_path)
    if legacy_execution is not None:
        return legacy_execution, "legacy_cache_hit"
    return None, None


def _write_step_cache(cache_info: dict[str, Any], execution: StepExecution) -> None:
    payload = execution.to_record()
    payload["cache_meta"] = {
        **payload.get("cache_meta", {}),
        "cache_key": cache_info["cache_key"],
        "signature": cache_info["signature"],
        "version": cache_info["version"],
        "cached_at": utc_now_iso(),
    }
    cache_path = cache_info["cache_path"]
    cache_path.write_text(
        json.dumps(jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    legacy_path = cache_info["legacy_path"]
    legacy_path.write_text(
        json.dumps(jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def apply_state_updates(state: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        state[key] = value


def append_degradation(
    state: dict[str, Any],
    step_name: str,
    *,
    status: str,
    reason: str | None = None,
    error: str | None = None,
    error_kind: RetryCategory | None = None,
    retry_meta: dict[str, Any] | None = None,
    cache_meta: dict[str, Any] | None = None,
) -> None:
    state.setdefault("degradations", []).append(
        {
            "step": step_name,
            "status": status,
            "reason": reason,
            "error": error,
            "error_kind": error_kind,
            "retry_meta": retry_meta or {},
            "cache_meta": cache_meta or {},
            "at": utc_now_iso(),
        }
    )


def build_mode_skip_step(
    step_name: str, mode: str
) -> Callable[[PipelineContext, dict[str, Any]], Any]:
    async def _skip(_: PipelineContext, __: dict[str, Any]) -> StepExecution:
        return StepExecution(
            status="skipped",
            output={"skipped_by_mode": mode, "step": step_name},
            state_updates=dict(PIPELINE_MODE_SKIP_UPDATES.get(step_name) or {}),
            reason="mode_matrix_skip",
            degraded=False,
        )

    return _skip


def _build_error_payload(execution: StepExecution) -> dict[str, Any] | None:
    if execution.status == "failed":
        return {
            "reason": execution.reason or "step_failed",
            "error": execution.error or "unknown",
            "error_kind": execution.error_kind,
            "retry_meta": execution.retry_meta,
        }
    if execution.status == "skipped":
        return {
            "reason": execution.reason or "skipped",
            "error_kind": execution.error_kind,
            "retry_meta": execution.retry_meta,
        }
    return None


async def execute_step(
    ctx: PipelineContext,
    state: dict[str, Any],
    *,
    step_name: str,
    step_func: Callable[[PipelineContext, dict[str, Any]], asyncio.Future | Any],
    critical: bool | object = _DEFAULT_ARG_UNSET,
    resume_hint: bool | object = _DEFAULT_ARG_UNSET,
    force_run: bool | object = _DEFAULT_ARG_UNSET,
) -> dict[str, Any]:
    sqlite_store = ctx.sqlite_store
    cache_info = build_step_cache_info(ctx, state, step_name)
    critical = _resolve_optional_flag(critical)
    resume_hint = _resolve_optional_flag(resume_hint)
    force_run = _resolve_force_run_flag(force_run)
    llm_policy = (
        dict(state.get("llm_policy") or {}) if step_name in {"llm_outline", "llm_digest"} else None
    )
    retry_policy = build_retry_policy(
        ctx.settings,
        step_name=step_name,
        llm_policy=llm_policy,
    )

    sqlite_store.mark_step_running(
        job_id=ctx.job_id,
        step_name=step_name,
        attempt=ctx.attempt,
        cache_key=str(cache_info["cache_key"]),
    )

    try:
        execution: StepExecution | None = None
        if not force_run:
            execution, cache_reason = _load_step_execution_from_cache(cache_info)
            if execution is not None:
                execution.status = "skipped"
                execution.reason = (
                    "checkpoint_recovered" if resume_hint else (cache_reason or "cache_hit")
                )
                execution.cache_meta = {
                    **execution.cache_meta,
                    "source": cache_reason or "cache_hit",
                    "cache_key": cache_info["cache_key"],
                    "signature": cache_info["signature"],
                    "version": cache_info["version"],
                }
                execution.retry_meta = {
                    "attempts": 0,
                    "retries_used": 0,
                    "retries_configured": 0,
                    "classification": None,
                    "strategy": "cache",
                    "resume_hint": resume_hint,
                }
            elif resume_hint:
                prior = sqlite_store.get_latest_step_run(
                    job_id=ctx.job_id,
                    step_name=step_name,
                    status="succeeded",
                    cache_key=str(cache_info["cache_key"]),
                )
                result_json = prior.get("result_json") if prior else None
                if isinstance(result_json, str) and result_json.strip():
                    try:
                        payload = json.loads(result_json)
                        execution = StepExecution.from_record(dict(payload))
                        if execution.status == "succeeded":
                            execution.status = "skipped"
                            execution.reason = "checkpoint_recovered"
                            execution.cache_meta = {
                                **execution.cache_meta,
                                "source": "checkpoint",
                                "cache_key": cache_info["cache_key"],
                                "signature": cache_info["signature"],
                                "version": cache_info["version"],
                            }
                            execution.retry_meta = {
                                "attempts": 0,
                                "retries_used": 0,
                                "retries_configured": 0,
                                "classification": None,
                                "strategy": "checkpoint",
                                "resume_hint": True,
                            }
                        else:
                            execution = None
                    except Exception:
                        execution = None

        if execution is None:
            retry_delays: list[float] = []
            retry_categories: list[RetryCategory] = []
            attempts = 0
            failed_attempts = 0
            configured_retries = 0

            while True:
                attempts += 1
                try:
                    maybe_coro = step_func(ctx, state)
                    current = await maybe_coro if asyncio.iscoroutine(maybe_coro) else maybe_coro
                    if not isinstance(current, StepExecution):
                        current = StepExecution(
                            status="failed",
                            error=f"invalid_step_result:{step_name}",
                            degraded=True,
                        )
                except Exception as exc:  # pragma: no cover
                    current = StepExecution(
                        status="failed",
                        reason="unhandled_exception",
                        error=f"unhandled_exception:{exc}",
                        degraded=True,
                    )

                if current.status != "failed":
                    execution = current
                    break

                failed_attempts += 1
                category = current.error_kind or classify_error(current.reason, current.error)
                current.error_kind = category
                retry_categories.append(category)
                policy = retry_policy.get(category, retry_policy["fatal"])
                configured_retries = max(configured_retries, int(policy.get("retries", 0)))
                retries_used = max(0, failed_attempts - 1)
                if retries_used >= int(policy.get("retries", 0)):
                    execution = current
                    break

                delay = retry_delay_seconds(policy, retries_used)
                retry_delays.append(delay)
                if delay > 0:
                    await asyncio.sleep(delay)

            assert execution is not None

            retries_used_total = (
                max(0, failed_attempts - 1) if execution.status == "failed" else failed_attempts
            )
            execution.retry_meta = {
                "attempts": attempts,
                "retries_used": retries_used_total,
                "retries_configured": configured_retries,
                "classification": execution.error_kind,
                "history": retry_categories,
                "delays_seconds": retry_delays,
                "strategy": "retry_wrapper",
                "resume_hint": resume_hint,
            }
        apply_state_updates(state, execution.state_updates)
        refresh_llm_media_input_dimension(state)

        sqlite_store.mark_step_finished(
            job_id=ctx.job_id,
            step_name=step_name,
            attempt=ctx.attempt,
            status=execution.status,
            error_payload=_build_error_payload(execution),
            error_kind=execution.error_kind,
            retry_meta=execution.retry_meta,
            result_payload=execution.to_record(),
            cache_key=str(cache_info["cache_key"]),
        )

        if execution.status in {"succeeded", "skipped"}:
            sqlite_store.update_checkpoint(
                job_id=ctx.job_id,
                last_completed_step=step_name,
                payload={
                    "cache_key": cache_info["cache_key"],
                    "status": execution.status,
                    "reason": execution.reason,
                    "error_kind": execution.error_kind,
                },
            )

        skip_is_degrade = (
            execution.status == "skipped" and execution.reason not in NON_DEGRADING_SKIP_REASONS
        )
        llm_hard_required = bool((state.get("llm_policy") or {}).get("hard_required", True))
        llm_hard_failed = (
            step_name in {"llm_outline", "llm_digest"}
            and execution.status == "failed"
            and llm_hard_required
        )
        if (
            (execution.status == "failed" and not llm_hard_failed)
            or execution.degraded
            or skip_is_degrade
        ):
            append_degradation(
                state,
                step_name,
                status=execution.status,
                reason=execution.reason,
                error=execution.error,
                error_kind=execution.error_kind,
                retry_meta=execution.retry_meta,
                cache_meta=execution.cache_meta,
            )

        if execution.status == "failed" and critical:
            state["fatal_error"] = f"{step_name}:{execution.error or execution.reason or 'failed'}"

        if execution.status == "succeeded":
            execution.cache_meta = {
                **execution.cache_meta,
                "cache_key": cache_info["cache_key"],
                "signature": cache_info["signature"],
                "version": cache_info["version"],
            }
            _write_step_cache(cache_info, execution)

        step_record = execution.to_record()
        state.setdefault("steps", {})[step_name] = step_record
        return step_record
    except asyncio.CancelledError:
        cancelled = StepExecution(
            status="failed",
            reason="cancelled",
            error="step_cancelled",
            error_kind="fatal",
            degraded=True,
            retry_meta={
                "attempts": 1,
                "retries_used": 0,
                "retries_configured": 0,
                "classification": "fatal",
                "history": ["fatal"],
                "delays_seconds": [],
                "strategy": "cancelled",
                "resume_hint": resume_hint,
            },
        )
        sqlite_store.mark_step_finished(
            job_id=ctx.job_id,
            step_name=step_name,
            attempt=ctx.attempt,
            status=cancelled.status,
            error_payload=_build_error_payload(cancelled),
            error_kind=cancelled.error_kind,
            retry_meta=cancelled.retry_meta,
            result_payload=cancelled.to_record(),
            cache_key=str(cache_info["cache_key"]),
        )
        state.setdefault("steps", {})[step_name] = cancelled.to_record()
        append_degradation(
            state,
            step_name,
            status=cancelled.status,
            reason=cancelled.reason,
            error=cancelled.error,
            error_kind=cancelled.error_kind,
            retry_meta=cancelled.retry_meta,
            cache_meta=cancelled.cache_meta,
        )
        raise


def run_command_once(cmd: list[str], timeout_seconds: int) -> CommandResult:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return CommandResult(ok=False, reason="binary_not_found")
    except subprocess.TimeoutExpired:
        return CommandResult(ok=False, reason="timeout")

    return CommandResult(
        ok=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        reason=None if completed.returncode == 0 else "non_zero_exit",
    )


def _decode_subprocess_stream(raw: bytes | None) -> str:
    if not raw:
        return ""
    return str(raw, "utf-8", "ignore")


def _resolve_optional_flag(value: bool | object) -> bool:
    return value is not _DEFAULT_ARG_UNSET and bool(value)


def _resolve_force_run_flag(value: bool | object) -> bool:
    if value is _DEFAULT_ARG_UNSET:
        return False
    return bool(value)


async def run_command(ctx: PipelineContext, cmd: list[str]) -> CommandResult:
    timeout = max(1, int(ctx.settings.pipeline_subprocess_timeout_seconds))
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError:
        return CommandResult(ok=False, reason="binary_not_found")

    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        await _terminate_subprocess(process)
        return CommandResult(ok=False, reason="timeout")
    except asyncio.CancelledError:
        current_task = asyncio.current_task()
        cancelling = current_task.cancelling() if current_task is not None else 0
        if current_task is not None:
            for _ in range(cancelling):
                current_task.uncancel()
        await _terminate_subprocess(process, prefer_process_kill=True)
        raise

    stdout = _decode_subprocess_stream(stdout_raw)
    stderr = _decode_subprocess_stream(stderr_raw)
    return CommandResult(
        ok=process.returncode == 0,
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        reason=None if process.returncode == 0 else "non_zero_exit",
    )


async def _terminate_subprocess(process: Any, *, prefer_process_kill: bool = False) -> None:
    if process.returncode is not None:
        return

    if prefer_process_kill:
        process.kill()
        await process.wait()
        return

    try:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=1.0)
        except TimeoutError:
            process.kill()
            await process.wait()
        return
    except Exception:
        if process.returncode is None:
            process.kill()
            await process.wait()
