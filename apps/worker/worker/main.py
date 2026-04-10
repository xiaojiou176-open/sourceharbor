from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from worker.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOG_EVENT_SCRIPT = _REPO_ROOT / "scripts" / "runtime" / "log_jsonl_event.py"
_WORKER_COMMAND_LOG_PATH = _REPO_ROOT / ".runtime-cache" / "logs" / "app" / "worker-commands.jsonl"
_REPO_COMMIT = (
    subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip()
    or "unknown"
)
_ENV_PROFILE = os.getenv("ENV_PROFILE", "unknown")


def _emit_worker_command_log(
    *,
    event: str,
    severity: str,
    message: str,
    run_id: str,
    request_id: str,
    trace_id: str,
) -> None:
    if not _LOG_EVENT_SCRIPT.is_file():
        return
    subprocess.run(
        [
            sys.executable,
            str(_LOG_EVENT_SCRIPT),
            "--path",
            str(_WORKER_COMMAND_LOG_PATH),
            "--run-id",
            run_id,
            "--trace-id",
            trace_id,
            "--request-id",
            request_id,
            "--service",
            "worker",
            "--component",
            "worker-cli",
            "--channel",
            "app",
            "--entrypoint",
            "apps.worker.worker.main:_main_async",
            "--env-profile",
            _ENV_PROFILE,
            "--repo-commit",
            _REPO_COMMIT,
            "--event",
            event,
            "--severity",
            severity,
            "--message",
            message,
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _command_correlation_id(
    command: str, args: argparse.Namespace, output: dict[str, object] | None
) -> str:
    if isinstance(output, dict):
        for key in ("run_id", "workflow_id", "job_id"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for attr in ("job_id", "workflow_id"):
        value = getattr(args, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{command}-{uuid4().hex}"


async def _connect_temporal(settings: Settings):
    from temporalio.client import Client

    return await Client.connect(
        settings.temporal_target_host,
        namespace=settings.temporal_namespace,
    )


async def run_temporal_worker(settings: Settings) -> None:
    from temporalio.worker import Worker

    from worker.temporal.activities import (
        cleanup_workspace_activity,
        load_consumption_batch_activity,
        mark_consumption_batch_closed_activity,
        mark_consumption_batch_failed_activity,
        mark_consumption_batch_materialized_activity,
        mark_failed_activity,
        mark_running_activity,
        mark_succeeded_activity,
        materialize_reader_batch_activity,
        poll_feeds_activity,
        prepare_consumption_batch_activity,
        provider_canary_activity,
        reconcile_stale_queued_jobs_activity,
        resolve_daily_digest_timing_activity,
        retry_failed_deliveries_activity,
        run_pipeline_activity,
        send_daily_digest_activity,
        send_video_digest_activity,
    )
    from worker.temporal.workflows import (
        CleanupWorkspaceWorkflow,
        ConsumeBatchWorkflow,
        ConsumePendingWorkflow,
        DailyDigestWorkflow,
        NotificationRetryWorkflow,
        PollFeedsWorkflow,
        ProcessJobWorkflow,
        ProviderCanaryWorkflow,
    )

    client = await _connect_temporal(settings)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            PollFeedsWorkflow,
            ProcessJobWorkflow,
            DailyDigestWorkflow,
            CleanupWorkspaceWorkflow,
            ConsumeBatchWorkflow,
            ConsumePendingWorkflow,
            NotificationRetryWorkflow,
            ProviderCanaryWorkflow,
        ],
        activities=[
            poll_feeds_activity,
            prepare_consumption_batch_activity,
            load_consumption_batch_activity,
            materialize_reader_batch_activity,
            mark_running_activity,
            mark_consumption_batch_materialized_activity,
            mark_consumption_batch_closed_activity,
            mark_consumption_batch_failed_activity,
            reconcile_stale_queued_jobs_activity,
            run_pipeline_activity,
            mark_succeeded_activity,
            mark_failed_activity,
            send_video_digest_activity,
            resolve_daily_digest_timing_activity,
            send_daily_digest_activity,
            retry_failed_deliveries_activity,
            provider_canary_activity,
            cleanup_workspace_activity,
        ],
    )
    await worker.run()


async def start_poll_workflow(
    settings: Settings,
    *,
    subscription_id: str | None = None,
    platform: str | None = None,
    max_new_videos: int = 50,
    run_once: bool = True,
    interval_minutes: int = 15,
    workflow_id: str = "poll-feeds-workflow",
) -> dict:
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from worker.temporal.workflows import PollFeedsWorkflow

    client = await _connect_temporal(settings)
    filters = {
        "subscription_id": subscription_id,
        "platform": platform,
        "max_new_videos": max_new_videos,
        "run_once": run_once,
        "interval_minutes": max(1, int(interval_minutes)),
    }
    try:
        handle = await client.start_workflow(
            PollFeedsWorkflow.run,
            filters,
            id=f"poll-feeds-{uuid4()}" if run_once else workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        return {
            "ok": True,
            "workflow_id": workflow_id,
            "status": "already_running",
            "run_once": run_once,
            "interval_minutes": filters["interval_minutes"],
        }
    if run_once:
        return await handle.result()
    run_id = getattr(handle, "first_execution_run_id", None) or getattr(handle, "run_id", None)
    return {
        "ok": True,
        "workflow_id": handle.id,
        "run_id": run_id,
        "status": "started",
        "run_once": False,
        "interval_minutes": filters["interval_minutes"],
    }


async def start_process_workflow(settings: Settings, job_id: str) -> dict:
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    from worker.temporal.workflows import ProcessJobWorkflow

    client = await _connect_temporal(settings)
    handle = await client.start_workflow(
        ProcessJobWorkflow.run,
        job_id,
        id=f"process-job-{job_id}",
        task_queue=settings.temporal_task_queue,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return await handle.result()


def _local_utc_offset_minutes() -> int:
    offset = datetime.now().astimezone().utcoffset()
    if offset is None:
        return 0
    return int(offset.total_seconds() // 60)


async def start_daily_workflow(
    settings: Settings,
    *,
    run_once: bool = False,
    local_hour: int | None = None,
    timezone_name: str | None = None,
    timezone_offset_minutes: int | None = None,
    workflow_id: str = "daily-digest-workflow",
) -> dict:
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from worker.temporal.workflows import DailyDigestWorkflow

    offset_minutes = (
        timezone_offset_minutes
        if timezone_offset_minutes is not None
        else _local_utc_offset_minutes()
    )
    client = await _connect_temporal(settings)
    effective_local_hour = int(
        local_hour if local_hour is not None else settings.digest_daily_local_hour
    )
    effective_timezone_name = timezone_name or settings.digest_local_timezone
    payload = {
        "run_once": run_once,
        "local_hour": effective_local_hour,
        "timezone_name": effective_timezone_name,
        "timezone_offset_minutes": int(offset_minutes),
    }
    try:
        handle = await client.start_workflow(
            DailyDigestWorkflow.run,
            payload,
            id=workflow_id if not run_once else f"{workflow_id}-{uuid4()}",
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        return {
            "ok": True,
            "workflow_id": workflow_id,
            "status": "already_running",
            "run_once": run_once,
        }

    if run_once:
        return await handle.result()

    run_id = getattr(handle, "first_execution_run_id", None) or getattr(handle, "run_id", None)
    return {
        "ok": True,
        "workflow_id": handle.id,
        "run_id": run_id,
        "status": "started",
        "run_once": False,
        "local_hour": effective_local_hour,
        "timezone_name": effective_timezone_name,
        "timezone_offset_minutes": int(offset_minutes),
    }


async def start_notification_retry_workflow(
    settings: Settings,
    *,
    run_once: bool = False,
    interval_minutes: int = 10,
    retry_batch_limit: int = 50,
    workflow_id: str = "notification-retry-workflow",
) -> dict:
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from worker.temporal.workflows import NotificationRetryWorkflow

    client = await _connect_temporal(settings)
    payload = {
        "run_once": run_once,
        "interval_minutes": max(1, int(interval_minutes)),
        "retry_batch_limit": max(1, int(retry_batch_limit)),
    }
    try:
        handle = await client.start_workflow(
            NotificationRetryWorkflow.run,
            payload,
            id=workflow_id if not run_once else f"{workflow_id}-{uuid4()}",
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        return {
            "ok": True,
            "workflow_id": workflow_id,
            "status": "already_running",
            "run_once": run_once,
        }

    if run_once:
        return await handle.result()

    run_id = getattr(handle, "first_execution_run_id", None) or getattr(handle, "run_id", None)
    return {
        "ok": True,
        "workflow_id": handle.id,
        "run_id": run_id,
        "status": "started",
        "run_once": False,
        "interval_minutes": payload["interval_minutes"],
        "retry_batch_limit": payload["retry_batch_limit"],
    }


async def start_provider_canary_workflow(
    settings: Settings,
    *,
    run_once: bool = False,
    interval_hours: int = 1,
    timeout_seconds: int = 8,
    workflow_id: str = "provider-canary-workflow",
) -> dict:
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from worker.temporal.workflows import ProviderCanaryWorkflow

    client = await _connect_temporal(settings)
    payload = {
        "run_once": run_once,
        "interval_hours": max(1, int(interval_hours)),
        "timeout_seconds": max(3, int(timeout_seconds)),
    }
    try:
        handle = await client.start_workflow(
            ProviderCanaryWorkflow.run,
            payload,
            id=workflow_id if not run_once else f"{workflow_id}-{uuid4()}",
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        return {
            "ok": True,
            "workflow_id": workflow_id,
            "status": "already_running",
            "run_once": run_once,
        }

    if run_once:
        return await handle.result()

    run_id = getattr(handle, "first_execution_run_id", None) or getattr(handle, "run_id", None)
    return {
        "ok": True,
        "workflow_id": handle.id,
        "run_id": run_id,
        "status": "started",
        "run_once": False,
        "interval_hours": payload["interval_hours"],
        "timeout_seconds": payload["timeout_seconds"],
    }


async def start_cleanup_workflow(
    settings: Settings,
    *,
    run_once: bool = True,
    interval_hours: int = 6,
    older_than_hours: int = 24,
    workspace_dir: str | None = None,
    cache_dir: str | None = None,
    cache_older_than_hours: int | None = None,
    cache_max_size_mb: int | None = None,
    workflow_id: str = "cleanup-workspace-workflow",
) -> dict:
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from worker.temporal.workflows import CleanupWorkspaceWorkflow

    client = await _connect_temporal(settings)
    payload: dict[str, object] = {
        "run_once": run_once,
        "interval_hours": max(1, int(interval_hours)),
        "older_than_hours": max(1, int(older_than_hours)),
        "workspace_dir": workspace_dir,
        "cache_dir": cache_dir,
    }
    if cache_older_than_hours is not None:
        payload["cache_older_than_hours"] = max(1, int(cache_older_than_hours))
    if cache_max_size_mb is not None:
        payload["cache_max_size_mb"] = max(1, int(cache_max_size_mb))

    try:
        handle = await client.start_workflow(
            CleanupWorkspaceWorkflow.run,
            payload,
            id=workflow_id if not run_once else f"{workflow_id}-{uuid4()}",
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        return {
            "ok": True,
            "workflow_id": workflow_id,
            "status": "already_running",
            "run_once": run_once,
        }

    if run_once:
        return await handle.result()

    run_id = getattr(handle, "first_execution_run_id", None) or getattr(handle, "run_id", None)
    return {
        "ok": True,
        "workflow_id": handle.id,
        "run_id": run_id,
        "status": "started",
        "run_once": False,
        "interval_hours": payload["interval_hours"],
        "older_than_hours": payload["older_than_hours"],
        "cache_older_than_hours": payload.get("cache_older_than_hours"),
        "cache_max_size_mb": payload.get("cache_max_size_mb"),
    }


async def _main_async(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    command = str(args.command or "").strip() or "unknown"
    request_id = uuid4().hex
    started_at = time.perf_counter()

    _emit_worker_command_log(
        event="worker_command_started",
        severity="info",
        message=f"worker command started: command={command}",
        run_id=request_id,
        request_id=request_id,
        trace_id=request_id,
    )

    try:
        if args.command == "run-worker":
            _emit_worker_command_log(
                event="worker_loop_started",
                severity="info",
                message=f"temporal worker loop started: task_queue={settings.temporal_task_queue}",
                run_id=request_id,
                request_id=request_id,
                trace_id=request_id,
            )
            await run_temporal_worker(settings)
            _emit_worker_command_log(
                event="worker_loop_exited",
                severity="warning",
                message="temporal worker loop exited without raising an exception",
                run_id=request_id,
                request_id=request_id,
                trace_id=request_id,
            )
            return
        if args.command == "start-poll-workflow":
            output = await start_poll_workflow(
                settings,
                subscription_id=args.subscription_id,
                platform=args.platform,
                max_new_videos=args.max_new_videos,
                run_once=not args.continuous,
                interval_minutes=args.interval_minutes,
                workflow_id=args.workflow_id,
            )
        elif args.command == "start-process-workflow":
            output = await start_process_workflow(settings, job_id=args.job_id)
        elif args.command == "start-daily-workflow":
            output = await start_daily_workflow(
                settings,
                run_once=args.run_once,
                local_hour=args.local_hour,
                timezone_name=args.timezone_name,
                timezone_offset_minutes=args.timezone_offset_minutes,
                workflow_id=args.workflow_id,
            )
        elif args.command == "start-notification-retry-workflow":
            output = await start_notification_retry_workflow(
                settings,
                run_once=args.run_once,
                interval_minutes=args.interval_minutes,
                retry_batch_limit=args.retry_batch_limit,
                workflow_id=args.workflow_id,
            )
        elif args.command == "start-provider-canary-workflow":
            output = await start_provider_canary_workflow(
                settings,
                run_once=args.run_once,
                interval_hours=args.interval_hours,
                timeout_seconds=args.timeout_seconds,
                workflow_id=args.workflow_id,
            )
        elif args.command == "start-cleanup-workflow":
            output = await start_cleanup_workflow(
                settings,
                run_once=args.run_once,
                interval_hours=args.interval_hours,
                older_than_hours=args.older_than_hours,
                workspace_dir=args.workspace_dir,
                cache_dir=args.cache_dir,
                cache_older_than_hours=args.cache_older_than_hours,
                cache_max_size_mb=args.cache_max_size_mb,
                workflow_id=args.workflow_id,
            )
        else:
            raise ValueError(f"Unsupported command: {args.command}")
    except Exception as exc:
        correlation_id = _command_correlation_id(command, args, None)
        elapsed = max(0.0, time.perf_counter() - started_at)
        _emit_worker_command_log(
            event="worker_command_failed",
            severity="error",
            message=f"worker command failed: command={command} elapsed_seconds={elapsed:.3f} error={exc}",
            run_id=correlation_id,
            request_id=request_id,
            trace_id=correlation_id,
        )
        raise

    correlation_id = _command_correlation_id(command, args, output)
    elapsed = max(0.0, time.perf_counter() - started_at)
    _emit_worker_command_log(
        event="worker_command_completed",
        severity="info",
        message=f"worker command completed: command={command} elapsed_seconds={elapsed:.3f}",
        run_id=correlation_id,
        request_id=request_id,
        trace_id=correlation_id,
    )

    print(json.dumps(output, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Worker entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-worker", help="Run Temporal worker loop")

    start_poll = sub.add_parser(
        "start-poll-workflow",
        help="Start PollFeedsWorkflow via Temporal",
    )
    start_poll.add_argument("--subscription-id", default=None)
    start_poll.add_argument("--platform", default=None, choices=["bilibili", "youtube"])
    start_poll.add_argument("--max-new-videos", type=int, default=50)
    start_poll.add_argument(
        "--continuous",
        action="store_true",
        help="Keep polling on the given interval instead of running once and waiting for result",
    )
    start_poll.add_argument("--interval-minutes", type=int, default=15)
    start_poll.add_argument("--workflow-id", default="poll-feeds-workflow")

    start_process = sub.add_parser(
        "start-process-workflow",
        help="Start ProcessJobWorkflow via Temporal",
    )
    start_process.add_argument("--job-id", required=True, help="Job UUID to process")

    start_daily = sub.add_parser(
        "start-daily-workflow",
        help="Start DailyDigestWorkflow via Temporal",
    )
    start_daily.add_argument(
        "--run-once",
        action="store_true",
        help="Run once immediately and wait for result",
    )
    start_daily.add_argument(
        "--local-hour",
        type=int,
        default=None,
        help="Daily local trigger hour for scheduler mode (default: DIGEST_DAILY_LOCAL_HOUR)",
    )
    start_daily.add_argument(
        "--timezone-name",
        default=None,
        help="IANA timezone name (default: DIGEST_LOCAL_TIMEZONE)",
    )
    start_daily.add_argument(
        "--timezone-offset-minutes",
        type=int,
        default=None,
        help="UTC offset minutes for local time; defaults to host local offset",
    )
    start_daily.add_argument(
        "--workflow-id",
        default="daily-digest-workflow",
        help="Temporal workflow id used for scheduler mode",
    )

    start_retry = sub.add_parser(
        "start-notification-retry-workflow",
        help="Start NotificationRetryWorkflow via Temporal",
    )
    start_retry.add_argument("--run-once", action="store_true")
    start_retry.add_argument("--interval-minutes", type=int, default=10)
    start_retry.add_argument("--retry-batch-limit", type=int, default=50)
    start_retry.add_argument("--workflow-id", default="notification-retry-workflow")

    start_canary = sub.add_parser(
        "start-provider-canary-workflow",
        help="Start ProviderCanaryWorkflow via Temporal",
    )
    start_canary.add_argument("--run-once", action="store_true")
    start_canary.add_argument("--interval-hours", type=int, default=1)
    start_canary.add_argument("--timeout-seconds", type=int, default=8)
    start_canary.add_argument("--workflow-id", default="provider-canary-workflow")

    start_cleanup = sub.add_parser(
        "start-cleanup-workflow",
        help="Start CleanupWorkspaceWorkflow via Temporal",
    )
    start_cleanup.add_argument(
        "--run-once",
        action="store_true",
        help="Run once immediately and wait for result",
    )
    start_cleanup.add_argument(
        "--interval-hours",
        type=int,
        default=6,
        help="Interval for periodic cleanup mode when --run-once is not set",
    )
    start_cleanup.add_argument(
        "--older-than-hours",
        type=int,
        default=24,
        help="Delete workspace media/frame files older than this many hours",
    )
    start_cleanup.add_argument(
        "--workspace-dir",
        default=None,
        help="Optional workspace root override",
    )
    start_cleanup.add_argument(
        "--cache-dir",
        default=None,
        help="Optional cache directory override (default: sibling 'cache' directory of workspace)",
    )
    start_cleanup.add_argument(
        "--cache-older-than-hours",
        type=int,
        default=None,
        help="Delete cache files older than this many hours",
    )
    start_cleanup.add_argument(
        "--cache-max-size-mb",
        type=int,
        default=None,
        help="After age cleanup, delete oldest cache files until this size threshold is met",
    )
    start_cleanup.add_argument(
        "--workflow-id",
        default="cleanup-workspace-workflow",
        help="Temporal workflow id used for periodic cleanup mode",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
