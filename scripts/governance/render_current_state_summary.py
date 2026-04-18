#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "governance"))

from common import write_text_artifact

GENERATED_HEADER = "<!-- runtime-generated: current-state-summary; do not edit directly -->\n"
CURRENT_WORKFLOW_STATUSES = {"verified", "queued", "in_progress"}


def _output_path() -> Path:
    return REPO_ROOT / ".runtime-cache" / "reports" / "governance" / "current-state-summary.md"


def _output_metadata_path() -> Path:
    output_path = _output_path()
    return output_path.with_name(f"{output_path.name}.meta.json")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _maybe_load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return _load_json(path)


def _current_head() -> str:
    head_path = REPO_ROOT / ".git" / "HEAD"
    if not head_path.exists():
        return ""
    ref = head_path.read_text(encoding="utf-8").strip()
    if ref.startswith("ref: "):
        target = REPO_ROOT / ".git" / ref[5:]
        return target.read_text(encoding="utf-8").strip() if target.exists() else ""
    return ref


def _worktree_changes() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.rstrip() for line in result.stdout.splitlines() if line.strip()]


def _workspace_freshness(*, worktree_dirty: bool) -> str:
    return "stale" if worktree_dirty else "current"


def _lane_row(name: str, state: str, note: str, artifact: str) -> str:
    return f"| `{name}` | `{state}` | {note} | `{artifact}` |"


def _workflow_lane_map(workflow_report: dict | None) -> dict[str, dict]:
    if not workflow_report:
        return {}
    return {
        str(lane.get("name") or ""): lane
        for lane in workflow_report.get("lanes", [])
        if isinstance(lane, dict)
    }


def _workflow_head_alignment(lane: dict | None, head_commit: str) -> tuple[str, str]:
    lane = lane or {}
    latest_run = lane.get("latest_run") or {}
    if not isinstance(latest_run, dict):
        latest_run = {}
    latest_head = str(lane.get("latest_run_head_sha") or latest_run.get("headSha") or "").strip()
    matches_current_head = lane.get("latest_run_matches_current_head") is True
    if matches_current_head or (latest_head and latest_head == head_commit):
        return "current", latest_head
    if latest_head:
        return "historical", latest_head
    return "missing", latest_head


def _workspace_blockers(report: dict | None) -> list[str]:
    verdict = (report or {}).get("current_workspace_verdict") or {}
    raw = verdict.get("blocking_conditions")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def render() -> str:
    output_metadata_path = _output_metadata_path()
    newcomer_report = _maybe_load_json(
        REPO_ROOT / ".runtime-cache" / "reports" / "governance" / "newcomer-result-proof.json"
    )
    remote_report = _maybe_load_json(
        REPO_ROOT / ".runtime-cache" / "reports" / "governance" / "remote-platform-truth.json"
    )
    required_checks = _maybe_load_json(
        REPO_ROOT / ".runtime-cache" / "reports" / "governance" / "remote-required-checks.json"
    )
    ghcr_report = _maybe_load_json(
        REPO_ROOT
        / ".runtime-cache"
        / "reports"
        / "governance"
        / "standard-image-publish-readiness.json"
    )
    release_report = _maybe_load_json(
        REPO_ROOT
        / ".runtime-cache"
        / "reports"
        / "release"
        / "release-evidence-attest-readiness.json"
    )
    workflow_report = _maybe_load_json(
        REPO_ROOT / ".runtime-cache" / "reports" / "governance" / "external-lane-workflows.json"
    )
    alignment_report = _maybe_load_json(
        REPO_ROOT
        / ".runtime-cache"
        / "reports"
        / "governance"
        / "current-proof-commit-alignment.json"
    )
    compat = (
        _maybe_load_json(REPO_ROOT / "config" / "governance" / "upstream-compat-matrix.json") or {}
    )
    workflow_lanes = _workflow_lane_map(workflow_report)

    head_commit = _current_head()
    worktree_changes = _worktree_changes()
    worktree_dirty = bool(worktree_changes)
    workspace_freshness = _workspace_freshness(worktree_dirty=worktree_dirty)
    workspace_verdict = str(
        ((newcomer_report or {}).get("current_workspace_verdict") or {}).get("status")
        or (newcomer_report or {}).get("status")
        or ("partial" if worktree_dirty else "unknown")
    )
    workspace_blockers = _workspace_blockers(newcomer_report)
    if worktree_dirty and workspace_verdict == "pass":
        workspace_verdict = "partial"
        if "dirty_worktree" not in workspace_blockers:
            workspace_blockers.append("dirty_worktree")
    lines = [
        GENERATED_HEADER.rstrip(),
        "# Current State Summary",
        "",
        "This runtime-owned page is the current-state verdict surface. It is intentionally not a tracked doc, so commit-sensitive truth cannot get stuck in checked-in prose again.",
        "",
        f"- current HEAD: `{head_commit or 'unknown'}`",
    ]
    if alignment_report:
        lines.append(f"- current-proof alignment: `{alignment_report.get('status', 'unknown')}`")
    lines.append(f"- worktree dirty: `{str(worktree_dirty).lower()}`")
    lines.append(f"- current workspace freshness: `{workspace_freshness}`")
    lines.append(f"- current workspace verdict: `{workspace_verdict}`")
    if workspace_blockers:
        lines.append(
            "- fail-close blockers: " + ", ".join(f"`{item}`" for item in workspace_blockers)
        )
    if worktree_dirty:
        lines.append(
            "- dirty-worktree note: current workspace freshness is stale, so this page fail-closes to the committed snapshot only; do not read green sub-receipts as proof for the current uncommitted workspace"
        )
    if workspace_verdict != "pass":
        lines.append(
            "- repo-side reading rule: `repo-side-strict receipt=pass` can still be commit-aligned-only evidence; the current workspace verdict above is the fail-close interpretation you must trust"
        )
        lines.extend(
            [
                "- reading rule: `docs/generated/external-lane-snapshot.md` is only a pointer and reading guide; current state must come from this file plus the underlying runtime reports",
                f"- summary metadata path: `{output_metadata_path.relative_to(REPO_ROOT).as_posix()}`",
                "- stale-summary rule: only treat green-like lines here as current when `.runtime-cache/reports/governance/current-state-summary.md.meta.json` points at the current HEAD; otherwise the whole page is historical",
                "",
                "## Repo-side Signals",
                "",
            ]
        )
    if newcomer_report:
        lines.append(
            f"- newcomer-result-proof artifact: `{newcomer_report.get('status', 'unknown')}`"
        )
        strict_receipt = newcomer_report.get("repo_side_strict_receipt") or {}
        if isinstance(strict_receipt, dict):
            strict_status = str(strict_receipt.get("status") or "unknown")
            lines.append(
                f"- repo-side-strict receipt: `{strict_status}` "
                f"(path=`.runtime-cache/reports/governance/newcomer-result-proof.json`)"
            )
    if remote_report:
        lines.append(
            f"- remote-platform-integrity artifact: `{remote_report.get('status', 'unknown')}`"
        )
    if required_checks:
        lines.append(
            f"- remote-required-checks artifact: `{required_checks.get('status', 'unknown')}` "
            f"(expected={len(required_checks.get('expected_required_checks', []))}, actual={len(required_checks.get('actual_required_checks', []))})"
        )
    open_source_audit_freshness = _maybe_load_json(
        REPO_ROOT / ".runtime-cache" / "reports" / "governance" / "open-source-audit-freshness.json"
    )
    if open_source_audit_freshness:
        lines.append(
            f"- open-source-audit-freshness artifact: `{open_source_audit_freshness.get('status', 'unknown')}`"
        )
    lines.extend(
        [
            "",
            "## External Lane Summary",
            "",
            "| Lane | Current State | Evidence / Note | Canonical Artifact |",
            "| --- | --- | --- | --- |",
        ]
    )
    remote_state = str((remote_report or {}).get("status") or "missing")
    remote_blocker = str((remote_report or {}).get("blocker_type") or "ok")
    remote_actor = str((remote_report or {}).get("actor") or "").strip()
    remote_note = remote_blocker
    if remote_actor:
        remote_note = f"{remote_blocker}; actor={remote_actor}"
    lines.append(
        _lane_row(
            "remote-platform-integrity",
            remote_state,
            remote_note,
            ".runtime-cache/reports/governance/remote-platform-truth.json",
        )
    )
    lines.append(
        _lane_row(
            "remote-required-checks",
            str((required_checks or {}).get("status") or "missing"),
            f"expected={len((required_checks or {}).get('expected_required_checks', []))}, actual={len((required_checks or {}).get('actual_required_checks', []))}",
            ".runtime-cache/reports/governance/remote-required-checks.json",
        )
    )
    ghcr_artifact_state = str((ghcr_report or {}).get("status") or "missing")
    ghcr_state = ghcr_artifact_state
    ghcr_note = str((ghcr_report or {}).get("blocker_type") or "ok")
    ghcr_manifest_probe = (ghcr_report or {}).get("manifest_probe") or {}
    if not isinstance(ghcr_manifest_probe, dict):
        ghcr_manifest_probe = {}
    ghcr_manifest_unknown = (
        "manifest unknown" in str(ghcr_manifest_probe.get("stderr") or "").lower()
    )
    ghcr_workflow = workflow_lanes.get("ghcr-standard-image") or {}
    ghcr_workflow_state = str(ghcr_workflow.get("state") or "")
    ghcr_workflow_note = str(ghcr_workflow.get("note") or "")
    ghcr_head_alignment, _ = _workflow_head_alignment(ghcr_workflow, head_commit)
    ghcr_failure_details = ghcr_workflow.get("failure_details") or {}
    if not isinstance(ghcr_failure_details, dict):
        ghcr_failure_details = {}
    if ghcr_workflow_state in CURRENT_WORKFLOW_STATUSES and ghcr_head_alignment == "current":
        ghcr_state = ghcr_workflow_state
        ghcr_note = (
            f"{ghcr_workflow_note}; local readiness artifact="
            f"{ghcr_artifact_state}:{str((ghcr_report or {}).get('blocker_type') or 'ok')}; "
            "current external verification remains open until both layers close"
        )
    elif (
        ghcr_workflow_state == "blocked"
        and ghcr_head_alignment == "current"
        and ghcr_failure_details
    ):
        ghcr_state = "blocked"
        failed_step = str(ghcr_failure_details.get("failed_step_name") or "")
        failure_signature = str(ghcr_failure_details.get("failure_signature") or "")
        if failed_step and failure_signature == "ghcr-blob-upload-401-unauthorized":
            local_readiness = (
                f"local readiness artifact={ghcr_artifact_state}:"
                f"{str((ghcr_report or {}).get('blocker_type') or 'ok')}"
            )
            ghcr_note = (
                f"{local_readiness}; latest remote current-head workflow failed at "
                f"`{failed_step}`; GHCR blob upload probe rejected the selected token with HTTP 401"
            )
            if ghcr_manifest_unknown:
                ghcr_note += "; digest-pinned manifest probe also returned `manifest unknown`, so package-path / ownership / visibility remains unresolved"
        elif failed_step and failure_signature == "blob-head-403-forbidden":
            local_readiness = (
                f"local readiness artifact={ghcr_artifact_state}:"
                f"{str((ghcr_report or {}).get('blocker_type') or 'ok')}"
            )
            ghcr_note = (
                f"{local_readiness}; latest remote current-head workflow preflight passed; "
                "blocked at `Build and push strict CI standard image`; GHCR blob HEAD returned 403 Forbidden"
            )
        elif failed_step == "Standard image publish preflight":
            local_readiness = (
                f"local readiness artifact={ghcr_artifact_state}:"
                f"{str((ghcr_report or {}).get('blocker_type') or 'ok')}"
            )
            ghcr_note = (
                f"{local_readiness}; latest remote current-head workflow failed at "
                f"`{failed_step}` before build/push; treat this as a registry/token preflight boundary failure, not as current external verification progress"
            )
            if ghcr_manifest_unknown:
                ghcr_note += "; digest-pinned manifest probe also returned `manifest unknown`, so package-path / ownership / visibility remains unresolved"
        elif failed_step and not ghcr_note.startswith("local readiness artifact="):
            ghcr_note = f"{ghcr_workflow_note}; failed_step={failed_step}"
    elif ghcr_head_alignment == "historical":
        if ghcr_state in CURRENT_WORKFLOW_STATUSES:
            ghcr_state = "historical"
        local_readiness = (
            f"local readiness artifact={ghcr_artifact_state}:"
            f"{str((ghcr_report or {}).get('blocker_type') or 'ok')}"
        )
        ghcr_note = f"{local_readiness}; remote workflow is historical for current HEAD and cannot upgrade this lane to current external verification"
        if ghcr_workflow_note:
            ghcr_note = f"{ghcr_workflow_note}; {ghcr_note}"
    lines.append(
        _lane_row(
            "ghcr-standard-image",
            ghcr_state,
            ghcr_note,
            ".runtime-cache/reports/governance/standard-image-publish-readiness.json + .runtime-cache/reports/governance/external-lane-workflows.json",
        )
    )

    public_api_workflow = workflow_lanes.get("public-api-image") or {}
    public_api_state = str(public_api_workflow.get("state") or "missing")
    public_api_note = str(public_api_workflow.get("note") or "missing")
    lines.append(
        _lane_row(
            "public-api-image",
            public_api_state,
            public_api_note,
            ".runtime-cache/reports/build-public-api-image/metadata.json + .runtime-cache/reports/governance/external-lane-workflows.json",
        )
    )

    release_artifact_state = str((release_report or {}).get("status") or "missing")
    release_state = release_artifact_state
    release_note = str((release_report or {}).get("blocker_type") or "ok")
    release_workflow = workflow_lanes.get("release-evidence-attestation") or {}
    release_workflow_state = str(release_workflow.get("state") or "")
    release_workflow_note = str(release_workflow.get("note") or "")
    release_head_alignment, _ = _workflow_head_alignment(release_workflow, head_commit)
    if (
        release_workflow_state == "verified"
        and release_head_alignment == "current"
        and release_artifact_state == "ready"
    ):
        release_state = "verified"
        release_note = f"{release_workflow_note}; readiness artifact=ready"
    elif (
        release_workflow_state in {"in_progress", "queued"} and release_head_alignment == "current"
    ):
        release_state = release_workflow_state
        release_note = (
            f"{release_workflow_note}; readiness artifact={release_artifact_state}; "
            "current external verification remains open until the current-head remote run closes"
        )
    elif release_head_alignment == "historical":
        if release_state in CURRENT_WORKFLOW_STATUSES:
            release_state = "historical"
        release_note = f"readiness artifact={release_artifact_state}; remote workflow is historical for current HEAD and does not count as current external verification"
        if release_workflow_note:
            release_note = f"{release_workflow_note}; {release_note}"
    lines.append(
        _lane_row(
            "release-evidence-attestation",
            release_state,
            release_note,
            ".runtime-cache/reports/release/release-evidence-attest-readiness.json + .runtime-cache/reports/governance/external-lane-workflows.json",
        )
    )

    publish_pypi_workflow = workflow_lanes.get("publish-pypi") or {}
    lines.append(
        _lane_row(
            "publish-pypi",
            str(publish_pypi_workflow.get("state") or "missing"),
            str(publish_pypi_workflow.get("note") or "missing"),
            ".runtime-cache/reports/publish-pypi/metadata.json + .runtime-cache/reports/governance/external-lane-workflows.json",
        )
    )

    publish_registry_workflow = workflow_lanes.get("publish-mcp-registry") or {}
    lines.append(
        _lane_row(
            "publish-mcp-registry",
            str(publish_registry_workflow.get("state") or "missing"),
            str(publish_registry_workflow.get("note") or "missing"),
            ".runtime-cache/reports/publish-mcp-registry/metadata.json + .runtime-cache/reports/governance/external-lane-workflows.json",
        )
    )
    if workflow_report:
        for lane in workflow_report.get("lanes", []):
            if not isinstance(lane, dict):
                continue
            lines.append(
                _lane_row(
                    f"workflow:{lane.get('name', 'unknown')}",
                    str(lane.get("state") or "unknown"),
                    str(lane.get("note") or "missing"),
                    ".runtime-cache/reports/governance/external-lane-workflows.json",
                )
            )
    compat_rows = {
        str(row.get("name") or ""): row for row in compat.get("matrix", []) if isinstance(row, dict)
    }
    for lane_name in (
        "rsshub-youtube-ingest-chain",
        "resend-digest-delivery-chain",
        "strict-ci-compose-image-set",
    ):
        row = compat_rows.get(lane_name, {})
        lane_note = str(row.get("verification_lane") or "unknown")
        if (
            lane_name == "strict-ci-compose-image-set"
            and str(row.get("verification_status") or "") == "pending"
            and ghcr_state == "blocked"
        ):
            lane_note = (
                "external; blocked on `ghcr-standard-image` "
                f"(local readiness={ghcr_artifact_state}, remote state={ghcr_state})"
            )
        lines.append(
            _lane_row(
                lane_name,
                str(row.get("verification_status") or "missing"),
                lane_note,
                str(row.get("evidence_artifact") or "n/a"),
            )
        )
    lines.extend(
        [
            "",
            "## Public Capability Reminder",
            "",
            "- `ready` does not mean `verified`.",
            "- When a remote workflow points at an old head, it is only historical evidence and does not count as current closure.",
            "- If the GHCR lane shows `preflight passed` and later stays `blocked`, the failure has already crossed into build/push or registry-write territory instead of stopping in readiness preflight.",
            "- Platform capability claims must be backed by a live probe or a current runtime artifact; tracked docs alone are not enough.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    output_path = _output_path()
    content = render()
    write_text_artifact(
        output_path,
        content,
        source_entrypoint="scripts/governance/render_current_state_summary.py",
        verification_scope="current-state-summary",
        source_run_id="current-state-summary",
        source_commit=_current_head(),
        freshness_window_hours=24,
        extra={"report_kind": "current-state-summary"},
    )
    print(output_path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
