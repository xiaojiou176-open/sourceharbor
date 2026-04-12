#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import current_git_commit, write_json_artifact

WORKFLOW_MAP = {
    "ghcr-standard-image": {
        "workflow_file": "build-ci-standard-image.yml",
        "workflow_name": "build-ci-standard-image",
    },
    "public-api-image": {
        "workflow_file": "build-public-api-image.yml",
        "workflow_name": "build-public-api-image",
    },
    "release-evidence-attestation": {
        "workflow_file": "release-evidence-attest.yml",
        "workflow_name": "release-evidence-attest",
    },
}


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), cwd=ROOT, check=check, capture_output=True, text=True)


def _repo_slug() -> str:
    remote = _run("git", "config", "--get", "remote.origin.url").stdout.strip()
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$", remote)
    if not match:
        raise SystemExit(
            f"unable to derive GitHub repository slug from remote.origin.url: {remote}"
        )
    return f"{match.group('owner')}/{match.group('repo')}"


def _json_or_none(command: list[str]) -> tuple[Any | None, dict[str, Any] | None]:
    result = _run(*command, check=False)
    if result.returncode == 0:
        return json.loads(result.stdout), None
    return None, {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _list_commit_runs(
    repo: str, current_head: str
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    payload, error = _json_or_none(
        [
            "gh",
            "run",
            "list",
            "--commit",
            current_head,
            "--limit",
            "100",
            "--json",
            "databaseId,workflowName,status,conclusion,displayTitle,headSha,updatedAt,url",
        ]
    )
    if error is not None or not isinstance(payload, list):
        return [], error
    rows = [row for row in payload if isinstance(row, dict)]
    return rows, None


def _filter_workflow_runs(
    runs: list[dict[str, Any]], workflow_name: str, workflow_file: str
) -> list[dict[str, Any]]:
    workflow_stem = Path(workflow_file).stem
    matches: list[dict[str, Any]] = []
    for run in runs:
        run_workflow_name = str(run.get("workflowName") or "").strip()
        display_title = str(run.get("displayTitle") or "").strip()
        if run_workflow_name in {workflow_name, workflow_file, workflow_stem}:
            matches.append(run)
            continue
        if display_title in {workflow_name, workflow_stem}:
            matches.append(run)
    return matches


def _failed_job_summary(
    repo: str, run_id: int | str | None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not run_id:
        return {}, None
    payload, error = _json_or_none(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            repo,
            "--json",
            "jobs",
        ]
    )
    if error is not None or not isinstance(payload, dict):
        return {}, error
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return {}, None
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if str(job.get("conclusion") or "") != "failure":
            continue
        steps = job.get("steps")
        failed_step_name = ""
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict) and str(step.get("conclusion") or "") == "failure":
                    failed_step_name = str(step.get("name") or "")
                    break
        return {
            "job_name": str(job.get("name") or ""),
            "job_id": job.get("databaseId"),
            "failed_step_name": failed_step_name,
            "job_url": str(job.get("url") or ""),
        }, None
    return {}, None


def _failure_signature(repo: str, run_id: int | str | None) -> tuple[str, dict[str, Any] | None]:
    if not run_id:
        return "", None
    result = _run(
        "gh",
        "run",
        "view",
        str(run_id),
        "--repo",
        repo,
        "--log-failed",
        check=False,
    )
    if result.returncode != 0:
        return "", {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if (
            "GHCR blob upload probe rejected the selected token via ghcr blob upload endpoint (HTTP 401)"
            in line
        ):
            return "ghcr-blob-upload-401-unauthorized", None
        if "403 Forbidden" in line and "blobs/sha256" in line:
            return "blob-head-403-forbidden", None
        if "failed to push" in line:
            return "failed-to-push-registry", None
    return "", None


def _select_representative_run(
    runs: list[dict[str, Any]] | None, current_head: str
) -> dict[str, Any] | None:
    if not isinstance(runs, list) or not runs:
        return None
    for run in runs:
        if isinstance(run, dict) and str(run.get("headSha") or "") == current_head:
            return run
    for run in runs:
        if isinstance(run, dict):
            return run
    return None


def _lane_state(current_head: str, run: dict[str, Any] | None) -> tuple[str, str, bool, str, str]:
    if not run:
        return "missing", "no remote workflow run found", False, "", "missing"
    status = str(run.get("status") or "")
    conclusion = str(run.get("conclusion") or "")
    run_head = str(run.get("headSha") or "")
    if not run_head and conclusion == "success":
        return (
            "blocked",
            "remote workflow completed without headSha; current HEAD cannot be verified",
            False,
            run_head,
            "missing",
        )
    if run_head and run_head != current_head:
        if status in {"queued", "pending"}:
            return (
                "historical",
                f"latest queued remote workflow targets old head `{run_head}`; current HEAD `{current_head}` has no queued remote run",
                False,
                run_head,
                "historical",
            )
        if status == "in_progress":
            return (
                "historical",
                f"latest in-progress remote workflow targets old head `{run_head}`; current HEAD `{current_head}` has no active remote run",
                False,
                run_head,
                "historical",
            )
        if conclusion == "success":
            return (
                "historical",
                f"latest successful remote workflow targets old head `{run_head}`; current HEAD `{current_head}` still not externally verified",
                False,
                run_head,
                "historical",
            )
        if conclusion:
            return (
                "historical",
                f"latest completed remote workflow targets old head `{run_head}` with conclusion `{conclusion}`; current HEAD `{current_head}` still unresolved",
                False,
                run_head,
                "historical",
            )
        return (
            "historical",
            f"latest remote workflow targets old head `{run_head}`; current HEAD `{current_head}` still unresolved",
            False,
            run_head,
            "historical",
        )
    if status in {"queued", "pending"}:
        return "queued", "remote workflow queued for current HEAD", True, run_head, "current"
    if status == "in_progress":
        return (
            "in_progress",
            "remote workflow in progress for current HEAD",
            True,
            run_head,
            "current",
        )
    if conclusion == "success":
        return (
            "verified",
            "remote workflow completed successfully for current HEAD",
            True,
            run_head,
            "current",
        )
    if conclusion:
        return (
            "blocked",
            f"remote workflow for current HEAD concluded `{conclusion}`",
            True,
            run_head,
            "current",
        )
    return (
        "blocked",
        f"unexpected workflow state status={status} conclusion={conclusion}",
        bool(run_head == current_head),
        run_head,
        "current" if run_head == current_head and run_head else "missing",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture latest remote workflow states for external lanes."
    )
    parser.add_argument(
        "--repo", default="", help="Explicit owner/repo slug. Defaults to origin remote."
    )
    parser.add_argument(
        "--output",
        default=".runtime-cache/reports/governance/external-lane-workflows.json",
        help="Output report path.",
    )
    args = parser.parse_args()

    repo = args.repo.strip() or _repo_slug()
    current_head = current_git_commit()
    actor_payload, actor_error = _json_or_none(["gh", "api", "user"])
    actor = str((actor_payload or {}).get("login") or "")

    commit_runs, commit_runs_error = _list_commit_runs(repo, current_head)

    lanes: list[dict[str, Any]] = []
    overall_status = "pass"
    for lane_name, workflow_config in WORKFLOW_MAP.items():
        workflow_file = str(workflow_config["workflow_file"])
        workflow_name = str(workflow_config["workflow_name"])
        payload = _filter_workflow_runs(commit_runs, workflow_name, workflow_file)
        error = commit_runs_error
        latest_run = _select_representative_run(payload, current_head)
        lane_state, note, matches_current_head, latest_run_head_sha, head_alignment = _lane_state(
            current_head, latest_run
        )
        failure_details: dict[str, Any] = {}
        failed_job_error: dict[str, Any] | None = None
        failure_signature_error: dict[str, Any] | None = None
        if lane_state == "blocked" and matches_current_head and isinstance(latest_run, dict):
            run_id = latest_run.get("databaseId")
            failure_details, failed_job_error = _failed_job_summary(repo, run_id)
            failure_signature, failure_signature_error = _failure_signature(repo, run_id)
            if failure_signature:
                failure_details["failure_signature"] = failure_signature
            if (
                failure_details.get("failed_step_name")
                and failure_details.get("failure_signature") == "blob-head-403-forbidden"
            ):
                note = (
                    f"{note}; preflight passed; failed at `{failure_details['failed_step_name']}` "
                    "with GHCR blob HEAD 403 Forbidden"
                )
        if lane_state == "blocked":
            overall_status = "blocked"
        lanes.append(
            {
                "name": lane_name,
                "workflow_file": workflow_file,
                "state": lane_state,
                "note": note,
                "latest_run_matches_current_head": matches_current_head,
                "latest_run_head_sha": latest_run_head_sha,
                "head_alignment": head_alignment,
                "latest_run": latest_run,
                "failure_details": failure_details,
                "failed_job_error": failed_job_error,
                "failure_signature_error": failure_signature_error,
                "error": error,
            }
        )

    report = {
        "version": 1,
        "status": overall_status,
        "repo": repo,
        "actor": actor,
        "actor_error": actor_error,
        "source_commit": current_head,
        "lanes": lanes,
    }
    write_json_artifact(
        ROOT / args.output,
        report,
        source_entrypoint="scripts/governance/probe_external_lane_workflows.py",
        verification_scope="external-lane-workflows",
        source_run_id="external-lane-workflows",
        freshness_window_hours=24,
        extra={"report_kind": "external-lane-workflows"},
    )

    print("[external-lane-workflows] PASS")
    for lane in lanes:
        latest_run = lane.get("latest_run") or {}
        run_id = latest_run.get("databaseId", "")
        print(f"  - {lane['name']}: {lane['state']} run_id={run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
