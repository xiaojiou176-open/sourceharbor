#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from common import current_git_commit, read_runtime_metadata, repo_root, write_json_artifact

ROOT = repo_root()


def _worktree_changes() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _workspace_freshness(*, worktree_dirty: bool) -> str:
    return "stale" if worktree_dirty else "current"


def _latest_manifest(entrypoint: str, commit: str) -> dict[str, Any] | None:
    manifests = sorted(
        (ROOT / ".runtime-cache" / "run" / "manifests").glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in manifests:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if payload.get("entrypoint") == entrypoint and payload.get("repo_commit") == commit:
            payload["_path"] = path.relative_to(ROOT).as_posix()
            return payload
    return None


def _latest_completed_manifest(
    entrypoint: str,
    commit: str,
    extra_log_paths: list[Path] | None = None,
) -> dict[str, Any] | None:
    manifests = sorted(
        (ROOT / ".runtime-cache" / "run" / "manifests").glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in manifests:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if payload.get("entrypoint") != entrypoint or payload.get("repo_commit") != commit:
            continue
        log_paths = [ROOT / str(payload.get("log_path") or "")]
        if extra_log_paths:
            log_paths.extend(extra_log_paths)
        run_id = str(payload.get("run_id") or "")
        if run_id and _log_has_complete(log_paths, run_id):
            payload["_path"] = path.relative_to(ROOT).as_posix()
            return payload
    return None


def _log_has_complete(log_paths: list[Path], run_id: str) -> bool:
    for log_path in log_paths:
        if not log_path.is_file():
            continue
        try:
            for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(payload.get("run_id") or "") != run_id:
                    continue
                if payload.get("event") == "complete" and payload.get("message") == "PASS":
                    return True
        except OSError:
            continue
    return False


def _latest_eval(commit: str) -> dict[str, Any] | None:
    candidates = sorted(
        (ROOT / ".runtime-cache" / "reports" / "evals").glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        if path.name.endswith(".meta.json"):
            continue
        metadata = read_runtime_metadata(path)
        if metadata is None:
            continue
        if str(metadata.get("source_commit") or "") != commit:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        return {
            "path": path.relative_to(ROOT).as_posix(),
            "status": payload.get("status"),
            "pass_rate": payload.get("pass_rate"),
            "metadata": metadata,
        }
    for path in candidates:
        if path.name.endswith(".meta.json"):
            continue
        metadata = read_runtime_metadata(path)
        if metadata is None:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        return {
            "path": path.relative_to(ROOT).as_posix(),
            "status": payload.get("status"),
            "pass_rate": payload.get("pass_rate"),
            "metadata": metadata,
            "current_commit_aligned": False,
        }
    return None


def _artifact_summary(rel: str, commit: str) -> dict[str, Any]:
    path = ROOT / rel
    metadata = read_runtime_metadata(path) if path.is_file() else None
    return {
        "path": rel,
        "exists": path.is_file(),
        "current_commit_aligned": bool(
            metadata and str(metadata.get("source_commit") or "") == commit
        ),
        "metadata": metadata,
    }


def _workspace_verdict(
    *,
    newcomer_preflight_status: str,
    governance_status: str,
    repo_side_strict_status: str,
    current_proof: dict[str, Any],
    worktree_dirty: bool,
) -> tuple[str, list[str], str]:
    blockers: list[str] = []

    if newcomer_preflight_status != "pass":
        blockers.append("newcomer_preflight_missing")
    if governance_status != "pass":
        blockers.append("governance_audit_not_pass")
    if repo_side_strict_status != "pass":
        blockers.append("repo_side_strict_missing_current_receipt")

    current_proof_exists = bool(current_proof.get("exists"))
    current_proof_aligned = bool(current_proof.get("current_commit_aligned"))
    if not current_proof_exists:
        blockers.append("current_proof_alignment_missing")
    elif not current_proof_aligned:
        blockers.append("current_proof_alignment_stale")

    if worktree_dirty:
        blockers.append("dirty_worktree")

    if newcomer_preflight_status != "pass":
        return (
            "missing",
            blockers,
            "required newcomer preflight proof is missing, so this report cannot be read as current workspace proof",
        )

    if governance_status not in {"pass", "in_progress"}:
        return (
            "missing",
            blockers,
            "required governance proof is missing, so this report cannot be read as current workspace proof",
        )

    if governance_status == "in_progress":
        return (
            "partial",
            blockers,
            "governance evidence is still in progress, so this report may describe progress but must not be read as current repo-side closure",
        )

    if repo_side_strict_status != "pass" or not current_proof_exists or not current_proof_aligned:
        return (
            "partial",
            blockers,
            "repo-side receipts are only partially current, so this report may explain progress but must not be read as repo-side done for the current workspace",
        )

    if worktree_dirty:
        return (
            "partial",
            blockers,
            "dirty worktree forces fail-close to partial: green commit-aligned receipts only prove the last committed snapshot, not the current uncommitted workspace",
        )

    return (
        "pass",
        [],
        "all required repo-side receipts are current and the worktree is clean, so this report can be read as current workspace proof",
    )


def main() -> int:
    commit = current_git_commit()
    validate_manifest = _latest_manifest("validate-profile", commit)
    strict_completed_manifest = _latest_completed_manifest(
        "strict-ci",
        commit,
        [ROOT / ".runtime-cache" / "logs" / "governance" / "strict-ci-entry.jsonl"],
    )
    strict_latest_manifest = _latest_manifest("strict-ci", commit)
    strict_manifest = strict_completed_manifest or strict_latest_manifest
    governance_manifest = _latest_completed_manifest(
        "governance-audit",
        commit,
        [ROOT / ".runtime-cache" / "logs" / "governance" / "governance-gate.jsonl"],
    ) or _latest_manifest("governance-audit", commit)

    validate_log = ROOT / str((validate_manifest or {}).get("log_path") or "")
    strict_log = ROOT / str((strict_manifest or {}).get("log_path") or "")
    strict_log_candidates = [
        strict_log,
        ROOT / ".runtime-cache" / "logs" / "governance" / "strict-ci-entry.jsonl",
    ]
    governance_log = ROOT / str((governance_manifest or {}).get("log_path") or "")
    governance_log_candidates = [
        governance_log,
        ROOT / ".runtime-cache" / "logs" / "governance" / "governance-gate.jsonl",
    ]

    validate_resolved = ROOT / ".runtime-cache" / "tmp" / ".env.local.resolved"
    eval_summary = _latest_eval(commit)
    current_proof = _artifact_summary(
        ".runtime-cache/reports/governance/current-proof-commit-alignment.json", commit
    )
    external_snapshot = _artifact_summary(
        ".runtime-cache/reports/governance/standard-image-publish-readiness.json", commit
    )
    worktree_changes = _worktree_changes()
    worktree_dirty = bool(worktree_changes)
    workspace_freshness = _workspace_freshness(worktree_dirty=worktree_dirty)

    newcomer_preflight_status = (
        "pass"
        if validate_resolved.is_file() and (validate_manifest is None or validate_log.is_file())
        else "missing"
    )
    repo_side_strict_status = (
        "pass"
        if strict_completed_manifest
        and _log_has_complete(
            strict_log_candidates, str(strict_completed_manifest.get("run_id") or "")
        )
        else "missing_current_receipt"
    )
    governance_status = "missing"
    if governance_manifest:
        governance_status = (
            "pass"
            if _log_has_complete(
                governance_log_candidates, str(governance_manifest.get("run_id") or "")
            )
            else "in_progress"
        )
    elif any(path.is_file() for path in governance_log_candidates):
        governance_status = "in_progress"

    overall_status, workspace_blockers, workspace_note = _workspace_verdict(
        newcomer_preflight_status=newcomer_preflight_status,
        governance_status=governance_status,
        repo_side_strict_status=repo_side_strict_status,
        current_proof=current_proof,
        worktree_dirty=worktree_dirty,
    )

    payload = {
        "version": 1,
        "status": overall_status,
        "source_commit": commit,
        "current_workspace_verdict": {
            "status": overall_status,
            "blocking_conditions": workspace_blockers,
            "freshness": workspace_freshness,
            "note": workspace_note,
        },
        "newcomer_preflight": {
            "status": newcomer_preflight_status,
            "manifest": validate_manifest,
            "log_exists": validate_log.is_file(),
            "resolved_env_path": ".runtime-cache/tmp/.env.local.resolved",
            "resolved_env_exists": validate_resolved.is_file(),
        },
        "repo_side_strict_receipt": {
            "status": repo_side_strict_status,
            "manifest": strict_manifest,
            "log_exists": strict_log.is_file(),
            "pass_receipt_detected": (
                _log_has_complete(
                    strict_log_candidates, str(strict_completed_manifest.get("run_id") or "")
                )
                if strict_completed_manifest
                else False
            ),
            "latest_seen_manifest": strict_latest_manifest,
            "pass_receipt_manifest": strict_completed_manifest,
            "note": "missing_current_receipt means the current commit has a strict entry manifest but no captured PASS completion receipt yet",
        },
        "governance_audit_receipt": {
            "status": governance_status,
            "manifest": governance_manifest,
            "log_exists": any(path.is_file() for path in governance_log_candidates),
            "pass_receipt_detected": (
                _log_has_complete(
                    governance_log_candidates, str(governance_manifest.get("run_id") or "")
                )
                if governance_manifest
                else False
            ),
        },
        "worktree_state": {
            "dirty": worktree_dirty,
            "workspace_freshness": workspace_freshness,
            "changed_paths_sample": worktree_changes[:20],
            "note": (
                "dirty worktree means this report intentionally fail-closes to partial even when commit-aligned receipts are green"
            ),
        },
        "representative_result_proof_pack": {
            "path": "docs/proofs/task-result-proof-pack.md",
            "exists": (ROOT / "docs" / "proofs" / "task-result-proof-pack.md").is_file(),
            "note": "public-safe representative result cases for human review; not a current external verdict surface",
        },
        "representative_result_cases": [
            {
                "id": "rep-case-01-ingest-queue",
                "proof_pack_path": "docs/proofs/task-result-proof-pack.md",
                "note": "持续发现新内容并稳定入队",
            },
            {
                "id": "rep-case-02-structured-digest",
                "proof_pack_path": "docs/proofs/task-result-proof-pack.md",
                "note": "单条内容被处理成结构化 digest",
            },
            {
                "id": "rep-case-03-failure-replayability",
                "proof_pack_path": "docs/proofs/task-result-proof-pack.md",
                "note": "失败路径可复盘而不是只剩红灯",
            },
        ],
        "eval_regression": eval_summary,
        "current_proof_alignment": current_proof,
        "external_standard_image": external_snapshot,
    }

    write_json_artifact(
        ROOT / ".runtime-cache" / "reports" / "governance" / "newcomer-result-proof.json",
        payload,
        source_entrypoint="scripts/governance/render_newcomer_result_proof.py",
        verification_scope="newcomer-result-proof",
        source_run_id="newcomer-result-proof",
        freshness_window_hours=24,
        extra={"report_kind": "newcomer-result-proof"},
    )

    print("[newcomer-result-proof] RENDERED")
    print(f"  - newcomer_preflight={newcomer_preflight_status}")
    print(f"  - repo_side_strict_receipt={repo_side_strict_status}")
    print(f"  - governance_audit_receipt={governance_status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
