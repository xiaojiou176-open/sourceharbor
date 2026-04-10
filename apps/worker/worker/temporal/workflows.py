from __future__ import annotations

from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from datetime import timedelta

    from worker.temporal.activities_entry import (
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


@workflow.defn(name="PollFeedsWorkflow")
class PollFeedsWorkflow:
    @workflow.run
    async def run(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        config = dict(filters or {})
        run_once = bool(config.pop("run_once", True))
        interval_minutes = max(1, int(config.pop("interval_minutes", 15)))
        latest_result: dict[str, Any] = {"ok": True, "runs": 0}
        run_count = 0

        while True:
            poll_result = await workflow.execute_activity(
                poll_feeds_activity,
                config,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            run_count += 1
            latest_result = {
                **poll_result,
                "track_interval_minutes": interval_minutes,
                "runs": run_count,
                "dispatched_process_workflows": 0,
                "process_results": [],
            }
            if run_once:
                return latest_result
            await workflow.sleep(timedelta(minutes=interval_minutes))


@workflow.defn(name="ConsumeBatchWorkflow")
class ConsumeBatchWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = dict(payload or {})
        batch_id = str(config.get("consumption_batch_id") or "").strip()
        if not batch_id:
            raise ValueError("ConsumeBatchWorkflow requires consumption_batch_id")
        try:
            batch = await workflow.execute_activity(
                load_consumption_batch_activity,
                {"consumption_batch_id": batch_id},
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            items = list(batch.get("items", []))
            process_results: list[dict[str, Any]] = []
            succeeded = 0
            failed = 0
            for item in items:
                job_id = str(item.get("job_id") or "").strip()
                if not job_id:
                    continue
                child_result = await workflow.execute_child_workflow(
                    ProcessJobWorkflow.run,
                    job_id,
                    id=f"consume-batch-{batch_id}-process-job-{job_id}",
                    task_queue=workflow.info().task_queue,
                )
                process_results.append(child_result)
                if bool(child_result.get("ok")):
                    succeeded += 1
                else:
                    failed += 1

            materialization = await workflow.execute_activity(
                materialize_reader_batch_activity,
                {"consumption_batch_id": batch_id},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            process_summary = {
                "consumption_batch_id": batch_id,
                "window_id": batch.get("window_id"),
                "cutoff_at": batch.get("cutoff_at"),
                "source_item_count": int(batch.get("source_item_count") or len(items)),
                "processed_job_ids": [
                    str(item.get("job_id"))
                    for item in items
                    if isinstance(item, dict) and str(item.get("job_id") or "").strip()
                ],
                "cluster_verdict_manifest_id": materialization.get("cluster_verdict_manifest_id"),
                "published_document_ids": [
                    str(item.get("id"))
                    for item in (materialization.get("documents") or [])
                    if isinstance(item, dict) and str(item.get("id") or "").strip()
                ],
                "published_document_count": int(
                    materialization.get("published_document_count") or 0
                ),
                "published_with_gap_count": int(
                    materialization.get("published_with_gap_count") or 0
                ),
                "downstream_status": "published_reader_documents_materialized",
            }
            await workflow.execute_activity(
                mark_consumption_batch_materialized_activity,
                {
                    "consumption_batch_id": batch_id,
                    "processed_job_count": succeeded + failed,
                    "succeeded_job_count": succeeded,
                    "failed_job_count": failed,
                    "process_summary_json": process_summary,
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            await workflow.execute_activity(
                mark_consumption_batch_closed_activity,
                {
                    "consumption_batch_id": batch_id,
                    "process_summary_json": process_summary,
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            return {
                "ok": True,
                "consumption_batch_id": batch_id,
                "window_id": batch.get("window_id"),
                "cutoff_at": batch.get("cutoff_at"),
                "status": "closed",
                "processed_job_count": succeeded + failed,
                "succeeded_job_count": succeeded,
                "failed_job_count": failed,
                "downstream_status": "published_reader_documents_materialized",
                "published_document_count": int(
                    materialization.get("published_document_count") or 0
                ),
                "published_with_gap_count": int(
                    materialization.get("published_with_gap_count") or 0
                ),
                "process_results": process_results,
                "materialization": materialization,
            }
        except Exception as exc:
            await workflow.execute_activity(
                mark_consumption_batch_failed_activity,
                {
                    "consumption_batch_id": batch_id,
                    "error": str(exc),
                    "reset_items_to_pending": True,
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            raise


@workflow.defn(name="ConsumePendingWorkflow")
class ConsumePendingWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = dict(payload or {})
        run_once = bool(config.pop("run_once", False))
        interval_minutes = max(60, int(config.pop("interval_minutes", 60)))

        latest_result: dict[str, Any] = {"ok": True, "runs": 0, "status": "idle"}
        run_count = 0
        while True:
            prepared = await workflow.execute_activity(
                prepare_consumption_batch_activity,
                config,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            run_count += 1
            if prepared.get("status") == "no_pending_items":
                latest_result = {**prepared, "runs": run_count}
            else:
                child_result = await workflow.execute_child_workflow(
                    ConsumeBatchWorkflow.run,
                    {"consumption_batch_id": prepared["consumption_batch_id"]},
                    id=f"consume-pending-{prepared['consumption_batch_id']}-{workflow.info().run_id}",
                    task_queue=workflow.info().task_queue,
                )
                latest_result = {
                    **prepared,
                    **child_result,
                    "runs": run_count,
                    "auto_cooldown_minutes": interval_minutes,
                }
            if run_once:
                return latest_result
            await workflow.sleep(timedelta(minutes=interval_minutes))


@workflow.defn(name="ProcessJobWorkflow")
class ProcessJobWorkflow:
    @workflow.run
    async def run(self, job: str | dict[str, Any]) -> dict[str, Any]:
        requested_mode: str | None = None
        requested_overrides: dict[str, Any] | None = None
        if isinstance(job, dict):
            job_id = str(job.get("job_id") or "").strip()
            if not job_id:
                raise ValueError("ProcessJobWorkflow requires job_id")
            mode_raw = job.get("mode")
            if isinstance(mode_raw, str):
                requested_mode = mode_raw.strip() or None
            overrides_raw = job.get("overrides")
            if isinstance(overrides_raw, dict):
                requested_overrides = dict(overrides_raw)
        else:
            job_id = str(job).strip()
            if not job_id:
                raise ValueError("ProcessJobWorkflow requires job_id")

        running = await workflow.execute_activity(
            mark_running_activity,
            job_id,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        payload = {"job_id": job_id, "attempt": int(running["attempt"])}
        if requested_mode is not None:
            payload["mode"] = requested_mode
        if requested_overrides is not None:
            payload["overrides"] = requested_overrides

        try:
            pipeline_result = await workflow.execute_activity(
                run_pipeline_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            final_status = str(pipeline_result.get("final_status", "failed"))
            if final_status == "failed":
                failed = await workflow.execute_activity(
                    mark_failed_activity,
                    {
                        **payload,
                        "error": str(pipeline_result.get("fatal_error") or "pipeline_failed"),
                        "pipeline_final_status": final_status,
                        "degradations": pipeline_result.get("degradations", []),
                        "llm_required": pipeline_result.get("llm_required"),
                        "llm_gate_passed": pipeline_result.get("llm_gate_passed"),
                        "hard_fail_reason": pipeline_result.get("hard_fail_reason"),
                    },
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
                return {
                    "ok": False,
                    "job_id": job_id,
                    "attempt": payload["attempt"],
                    "status": failed["status"],
                    "pipeline": pipeline_result,
                    "error": str(pipeline_result.get("fatal_error") or "pipeline_failed"),
                }

            succeeded = await workflow.execute_activity(
                mark_succeeded_activity,
                {
                    **payload,
                    "final_status": final_status,
                    "pipeline_final_status": final_status,
                    "degradations": pipeline_result.get("degradations", []),
                    "llm_required": pipeline_result.get("llm_required"),
                    "llm_gate_passed": pipeline_result.get("llm_gate_passed"),
                    "hard_fail_reason": pipeline_result.get("hard_fail_reason"),
                    "artifacts": pipeline_result.get("artifacts", {}),
                    "artifact_dir": pipeline_result.get("artifact_dir"),
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            try:
                notification_result = await workflow.execute_activity(
                    send_video_digest_activity,
                    {
                        "job_id": job_id,
                        "final_status": final_status,
                    },
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except Exception as notification_exc:
                notification_result = {
                    "ok": False,
                    "job_id": job_id,
                    "error": str(notification_exc),
                    "status": "failed",
                }
            return {
                "ok": final_status != "failed",
                "job_id": job_id,
                "attempt": payload["attempt"],
                "pipeline": pipeline_result,
                "status": succeeded["status"],
                "db_status": succeeded.get("db_status"),
                "video_digest": notification_result,
            }
        except Exception as exc:
            failed = await workflow.execute_activity(
                mark_failed_activity,
                {
                    **payload,
                    "error": str(exc),
                    "pipeline_final_status": "failed",
                    "llm_required": True,
                    "llm_gate_passed": False,
                    "hard_fail_reason": "workflow_exception",
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            return {
                "ok": False,
                "job_id": job_id,
                "attempt": payload["attempt"],
                "status": failed["status"],
                "error": str(exc),
            }


@workflow.defn(name="DailyDigestWorkflow")
class DailyDigestWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = payload or {}
        run_once = bool(config.get("run_once", False))
        timezone_name = str(config.get("timezone_name") or "").strip() or None
        offset_minutes = int(config.get("timezone_offset_minutes", 0))
        target_hour = max(0, min(23, int(config.get("local_hour", 9))))

        latest_result: dict[str, Any] = {
            "ok": True,
            "runs": 0,
        }
        run_count = 0

        while True:
            timing = await workflow.execute_activity(
                resolve_daily_digest_timing_activity,
                {
                    "run_once": run_once,
                    "timezone_name": timezone_name,
                    "timezone_offset_minutes": offset_minutes,
                    "local_hour": target_hour,
                },
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            wait_before = int(timing.get("wait_before_run_seconds", 0))
            if wait_before > 0 and not run_once:
                await workflow.sleep(timedelta(seconds=wait_before))

            digest_date = str(timing.get("digest_date") or "")
            resolved_timezone_name = str(timing.get("timezone_name") or timezone_name or "")
            resolved_offset = int(timing.get("timezone_offset_minutes", offset_minutes))
            activity_result = await workflow.execute_activity(
                send_daily_digest_activity,
                {
                    "digest_date": digest_date,
                    "timezone_name": resolved_timezone_name or None,
                    "timezone_offset_minutes": resolved_offset,
                },
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            run_count += 1
            latest_result = {
                **activity_result,
                "runs": run_count,
            }

            if run_once:
                return latest_result

            wait_after = int(timing.get("wait_after_run_seconds", 60))
            if wait_after < 1:
                wait_after = 60
            await workflow.sleep(timedelta(seconds=wait_after))


@workflow.defn(name="NotificationRetryWorkflow")
class NotificationRetryWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = payload or {}
        run_once = bool(config.get("run_once", False))
        interval_minutes = max(1, int(config.get("interval_minutes", 10)))
        retry_limit = max(1, int(config.get("retry_batch_limit", 50)))
        queued_timeout_minutes = max(1, int(config.get("queued_timeout_minutes", 15)))
        queued_reclaim_limit = max(1, int(config.get("queued_reclaim_limit", 200)))

        latest_result: dict[str, Any] = {"ok": True, "runs": 0}
        run_count = 0
        while True:
            stale_jobs_result = await workflow.execute_activity(
                reconcile_stale_queued_jobs_activity,
                {
                    "timeout_minutes": queued_timeout_minutes,
                    "limit": queued_reclaim_limit,
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            activity_result = await workflow.execute_activity(
                retry_failed_deliveries_activity,
                {"limit": retry_limit},
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            run_count += 1
            latest_result = {
                **activity_result,
                "stale_queued_recovery": stale_jobs_result,
                "runs": run_count,
            }
            if run_once:
                return latest_result
            await workflow.sleep(timedelta(minutes=interval_minutes))


@workflow.defn(name="ProviderCanaryWorkflow")
class ProviderCanaryWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = payload or {}
        run_once = bool(config.get("run_once", False))
        interval_hours = max(1, int(config.get("interval_hours", 1)))
        timeout_seconds = max(3, int(config.get("timeout_seconds", 8)))

        latest_result: dict[str, Any] = {"ok": True, "runs": 0}
        run_count = 0
        while True:
            activity_result = await workflow.execute_activity(
                provider_canary_activity,
                {"timeout_seconds": timeout_seconds},
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            run_count += 1
            latest_result = {
                **activity_result,
                "runs": run_count,
            }
            if run_once:
                return latest_result
            await workflow.sleep(timedelta(hours=interval_hours))


@workflow.defn(name="CleanupWorkspaceWorkflow")
class CleanupWorkspaceWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        config = payload or {}
        run_once = bool(config.get("run_once", False))
        interval_hours = max(1, int(config.get("interval_hours", 6)))

        activity_payload: dict[str, Any] = {}
        for key in (
            "workspace_dir",
            "older_than_hours",
            "cache_dir",
            "cache_older_than_hours",
            "cache_max_size_mb",
        ):
            if key in config:
                activity_payload[key] = config[key]

        latest_result: dict[str, Any] = {"ok": True, "runs": 0}
        run_count = 0
        while True:
            activity_result = await workflow.execute_activity(
                cleanup_workspace_activity,
                activity_payload,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            run_count += 1
            latest_result = {
                **activity_result,
                "runs": run_count,
            }
            if run_once:
                return latest_result
            await workflow.sleep(timedelta(hours=interval_hours))
