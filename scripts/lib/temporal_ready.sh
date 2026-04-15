#!/usr/bin/env bash

temporal_namespace_is_ready() {
  local target_host="$1"
  local namespace="$2"

  command -v temporal >/dev/null 2>&1 || return 1

  temporal operator namespace describe \
    --address "$target_host" \
    --namespace "$namespace" \
    >/dev/null 2>&1
}

wait_for_temporal_namespace() {
  local target_host="$1"
  local namespace="$2"
  local timeout="${3:-20}"
  local attempt

  for attempt in $(seq 1 "$timeout"); do
    if temporal_namespace_is_ready "$target_host" "$namespace"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

temporal_task_queue_has_worker_pollers() {
  local target_host="$1"
  local namespace="$2"
  local task_queue="$3"

  command -v uv >/dev/null 2>&1 || return 1

  TEMPORAL_TARGET_HOST="$target_host" \
  TEMPORAL_NAMESPACE="$namespace" \
  TEMPORAL_TASK_QUEUE="$task_queue" \
    uv run python - <<'PY' >/dev/null 2>&1
import asyncio
import os

from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client


async def main() -> int:
    client = await Client.connect(
        os.environ["TEMPORAL_TARGET_HOST"],
        namespace=os.environ["TEMPORAL_NAMESPACE"],
    )
    task_queue = TaskQueue(name=os.environ["TEMPORAL_TASK_QUEUE"])
    for task_queue_type in (
        TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
        TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY,
    ):
        response = await client.workflow_service.describe_task_queue(
            DescribeTaskQueueRequest(
                namespace=os.environ["TEMPORAL_NAMESPACE"],
                task_queue=task_queue,
                task_queue_type=task_queue_type,
            )
        )
        if len(response.pollers) == 0:
            return 1
    return 0


raise SystemExit(asyncio.run(main()))
PY
}

wait_for_temporal_worker_pollers() {
  local target_host="$1"
  local namespace="$2"
  local task_queue="$3"
  local timeout="${4:-45}"
  local attempt

  for attempt in $(seq 1 "$timeout"); do
    if temporal_task_queue_has_worker_pollers "$target_host" "$namespace" "$task_queue"; then
      return 0
    fi
    sleep 1
  done
  return 1
}
