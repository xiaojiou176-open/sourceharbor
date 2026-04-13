from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_governance_module(module_name: str, relative_path: str):
    root = _repo_root()
    scripts_dir = root / "scripts" / "governance"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location(module_name, root / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_meta(
    path: Path,
    *,
    source_commit: str,
    verification_scope: str,
    source_run_id: str = "test-fixture",
    extra: dict | None = None,
) -> None:
    meta = {
        "version": 1,
        "artifact_path": path.as_posix(),
        "created_at": "2026-03-16T12:00:00Z",
        "source_entrypoint": "test-fixture",
        "source_run_id": source_run_id,
        "source_commit": source_commit,
        "verification_scope": verification_scope,
        "freshness_window_hours": 24,
    }
    if extra:
        meta.update(extra)
    path.with_name(f"{path.name}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_probe_external_lane_workflows_prefers_current_head_run() -> None:
    module = _load_governance_module(
        "probe_external_lane_workflows_test",
        "scripts/governance/probe_external_lane_workflows.py",
    )
    current_head = "1111111111111111111111111111111111111111"
    stale_head = "2222222222222222222222222222222222222222"
    runs = [
        {
            "databaseId": 100,
            "headSha": stale_head,
            "status": "completed",
            "conclusion": "success",
        },
        {
            "databaseId": 101,
            "headSha": current_head,
            "status": "completed",
            "conclusion": "failure",
        },
    ]

    selected = module._select_representative_run(runs, current_head)

    assert selected is not None
    assert selected["databaseId"] == 101
    assert selected["headSha"] == current_head


def test_probe_external_lane_workflows_filters_current_commit_runs_by_workflow_name() -> None:
    module = _load_governance_module(
        "probe_external_lane_workflows_filter_test",
        "scripts/governance/probe_external_lane_workflows.py",
    )
    runs = [
        {
            "databaseId": 301,
            "workflowName": "ci",
            "displayTitle": "ci",
            "headSha": "1111111111111111111111111111111111111111",
        },
        {
            "databaseId": 302,
            "workflowName": "build-ci-standard-image",
            "displayTitle": "build-ci-standard-image",
            "headSha": "1111111111111111111111111111111111111111",
        },
        {
            "databaseId": 303,
            "workflowName": "release-evidence-attest",
            "displayTitle": "release-evidence-attest",
            "headSha": "1111111111111111111111111111111111111111",
        },
    ]

    ghcr = module._filter_workflow_runs(
        runs,
        workflow_name="build-ci-standard-image",
        workflow_file="build-ci-standard-image.yml",
    )
    release = module._filter_workflow_runs(
        runs,
        workflow_name="release-evidence-attest",
        workflow_file="release-evidence-attest.yml",
    )

    assert [row["databaseId"] for row in ghcr] == [302]
    assert [row["databaseId"] for row in release] == [303]


def test_probe_external_lane_workflows_blocks_when_current_head_has_no_remote_run(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "probe_external_lane_workflows_missing_current_test",
        "scripts/governance/probe_external_lane_workflows.py",
    )
    head = "1111111111111111111111111111111111111111"

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_repo_slug", lambda: "xiaojiou176-open/sourceharbor")
    monkeypatch.setattr(module, "current_git_commit", lambda: head)
    monkeypatch.setattr(module, "_json_or_none", lambda _command: ({"login": "tester"}, None))
    monkeypatch.setattr(module, "_list_commit_runs", lambda _repo, _head: ([], None))
    monkeypatch.setattr(sys, "argv", ["probe_external_lane_workflows.py"])

    captured_artifact: dict[str, object] = {}

    def _capture_artifact(path: Path, payload: dict[str, object], **kwargs) -> None:
        captured_artifact["path"] = path
        captured_artifact["payload"] = payload

    monkeypatch.setattr(module, "write_json_artifact", _capture_artifact)

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = module.main()

    output = stdout.getvalue()
    assert exit_code == 0, output
    assert "[external-lane-workflows] BLOCKED" in output
    assert "public-api-image: missing" in output

    payload = captured_artifact["payload"]
    assert isinstance(payload, dict)
    assert payload["status"] == "blocked"
    lanes = payload["lanes"]
    assert isinstance(lanes, list)
    assert all(isinstance(lane, dict) and lane["state"] == "missing" for lane in lanes)


def test_required_checks_parsers_ignore_workflow_event_rows(tmp_path: Path, monkeypatch) -> None:
    probe_module = _load_governance_module(
        "probe_remote_platform_truth_test",
        "scripts/governance/probe_remote_platform_truth.py",
    )
    check_module = _load_governance_module(
        "check_remote_required_checks_test",
        "scripts/governance/check_remote_required_checks.py",
    )

    required_checks_path = tmp_path / "docs" / "generated" / "required-checks.md"
    required_checks_path.parent.mkdir(parents=True, exist_ok=True)
    required_checks_path.write_text(
        (
            "# Required Checks\n"
            "\n"
            "| Check | Workflow | Why it exists |\n"
            "| --- | --- | --- |\n"
            "| `python-tests` | `ci.yml` | python coverage |\n"
            "| `web-lint` | `ci.yml` | web lint |\n"
            "| `pre-commit` | `pre-commit.yml` | hygiene gate |\n"
            "| `pull_request` | `n/a` | event row should be ignored |\n"
            "| `push` | `n/a` | event row should be ignored |\n"
            "| `workflow_dispatch` | `n/a` | event row should be ignored |\n"
            "| `schedule` | `n/a` | event row should be ignored |\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(probe_module, "ROOT", tmp_path)

    assert probe_module._load_required_checks() == ["pre-commit", "python-tests", "web-lint"]
    assert check_module._load_required_checks(required_checks_path) == [
        "pre-commit",
        "python-tests",
        "web-lint",
    ]


def test_current_proof_gate_rejects_stale_nested_external_verified(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "check_current_proof_commit_alignment_test",
        "scripts/governance/check_current_proof_commit_alignment.py",
    )
    head = "1111111111111111111111111111111111111111"
    stale_head = "2222222222222222222222222222222222222222"

    workflow_artifact = tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json"
    _write_json(
        workflow_artifact,
        {
            "version": 1,
            "status": "pass",
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "historical",
                    "note": f"latest successful remote workflow targets old head `{stale_head}`; current HEAD `{head}` still not externally verified",
                    "latest_run_matches_current_head": False,
                    "latest_run": {
                        "databaseId": 42,
                        "status": "completed",
                        "conclusion": "success",
                        "headSha": stale_head,
                    },
                }
            ],
        },
    )
    _write_meta(
        workflow_artifact,
        source_commit=head,
        verification_scope="external-lane-workflows",
    )

    ghcr_artifact = (
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json"
    )
    _write_json(
        ghcr_artifact,
        {
            "version": 1,
            "status": "verified",
            "blocked_type": "ok",
            "source_commit": head,
        },
    )
    _write_meta(
        ghcr_artifact,
        source_commit=head,
        verification_scope="standard-image-publish-readiness",
    )

    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", lambda _root: [])
    monkeypatch.setattr(module, "write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "load_governance_json",
        lambda _name: {
            "artifacts": [
                {
                    "name": "external-lane-workflows",
                    "artifact": ".runtime-cache/reports/governance/external-lane-workflows.json",
                    "required": True,
                    "reason": "workflow truth",
                },
                {
                    "name": "ghcr-standard-image-readiness",
                    "artifact": ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
                    "required": True,
                    "reason": "current external proof",
                    "external_lane": "ghcr-standard-image",
                    "workflow_artifact": ".runtime-cache/reports/governance/external-lane-workflows.json",
                    "require_current_head_for_statuses": [
                        "verified",
                        "queued",
                        "in_progress",
                        "blocked",
                    ],
                },
            ]
        },
    )

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = module.main()

    output = stdout.getvalue()
    assert exit_code == 1, output
    assert "ghcr-standard-image-readiness" in output
    assert "historical" in output
    assert "must not report `verified`" in output


def test_render_external_lane_snapshot_demotes_stale_verified_to_historical(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_docs_governance_test",
        "scripts/governance/render_docs_governance.py",
    )
    head = "1111111111111111111111111111111111111111"
    stale_head = "2222222222222222222222222222222222222222"

    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "generated").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / "config/governance/external-lane-contract.json",
        {
            "version": 1,
            "lanes": [
                {
                    "name": "remote-platform-integrity",
                    "canonical_artifact": ".runtime-cache/reports/governance/remote-platform-truth.json",
                    "verification_scope": "remote-platform-truth",
                    "allowed_statuses": ["pass", "blocked"],
                    "blocked_types": ["repo-readability"],
                },
                {
                    "name": "ghcr-standard-image",
                    "canonical_artifact": ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
                    "remote_workflow_artifact": ".runtime-cache/reports/governance/external-lane-workflows.json",
                    "verified_requires_current_head": True,
                    "verification_scope": "standard-image-publish-readiness",
                    "allowed_statuses": [
                        "ready",
                        "queued",
                        "in_progress",
                        "verified",
                        "blocked",
                        "historical",
                    ],
                    "blocked_types": ["registry-auth-failure"],
                },
                {
                    "name": "release-evidence-attestation",
                    "canonical_artifact": ".runtime-cache/reports/release/release-evidence-attest-readiness.json",
                    "remote_workflow_artifact": ".runtime-cache/reports/governance/external-lane-workflows.json",
                    "verified_requires_current_head": True,
                    "verification_scope": "release-evidence-attest-readiness",
                    "allowed_statuses": [
                        "ready",
                        "queued",
                        "in_progress",
                        "verified",
                        "blocked",
                        "historical",
                    ],
                    "blocked_types": ["attestation-failure"],
                },
            ],
        },
    )
    _write_json(
        tmp_path / "config/governance/upstream-compat-matrix.json",
        {
            "matrix": [
                {
                    "name": "rsshub-youtube-ingest-chain",
                    "verification_status": "verified",
                    "verification_lane": "provider",
                    "evidence_artifact": "rsshub.json",
                },
                {
                    "name": "resend-digest-delivery-chain",
                    "verification_status": "verified",
                    "verification_lane": "provider",
                    "evidence_artifact": "resend.json",
                },
                {
                    "name": "strict-ci-compose-image-set",
                    "verification_status": "pending",
                    "verification_lane": "external",
                    "evidence_artifact": "compose.json",
                },
            ]
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "verified",
            "blocked_type": "ok",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "historical",
                    "note": f"latest successful remote workflow targets old head `{stale_head}`; current HEAD `{head}` still not externally verified",
                    "latest_run_matches_current_head": False,
                    "latest_run": {
                        "databaseId": 42,
                        "status": "completed",
                        "conclusion": "success",
                        "headSha": stale_head,
                    },
                }
            ],
        },
    )

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    rendered = module._render_external_lane_snapshot()

    assert "# External Lane Truth Entry" in rendered
    assert "tracked page is a machine-rendered pointer only" in rendered
    assert ".runtime-cache/reports/governance/standard-image-publish-readiness.json" in rendered
    assert "must not carry current verdict payload" in rendered
    assert "| `ghcr-standard-image` | `verified` |" not in rendered


def test_render_current_state_summary_distinguishes_local_readiness_from_remote_push_failure(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "1111111111111111111111111111111111111111"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "blocked",
            "blocker_type": "registry-auth-failure",
            "token_mode": "gh-cli",
            "token_scope_ok": False,
            "blob_upload_scope_ok": False,
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "blocked",
                    "note": "remote workflow for current HEAD concluded `failure`; preflight passed",
                    "latest_run_matches_current_head": True,
                    "latest_run": {
                        "databaseId": 42,
                        "status": "completed",
                        "conclusion": "failure",
                        "headSha": head,
                    },
                    "failure_details": {
                        "failed_step_name": "Build and push strict CI standard image",
                        "failure_signature": "blob-head-403-forbidden",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {"version": 1, "status": "pass", "blocker_type": ""},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "partial",
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(tmp_path / "config/governance/upstream-compat-matrix.json", {"matrix": []})

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(
        module, "_worktree_changes", lambda: [" M apps/worker/worker/comments/youtube.py"]
    )

    rendered = module.render()

    assert "local readiness artifact=blocked:registry-auth-failure" in rendered
    assert "latest remote current-head workflow preflight passed" in rendered
    assert "GHCR blob HEAD returned 403 Forbidden" in rendered


def test_render_current_state_summary_keeps_release_lane_as_readiness_when_remote_workflow_is_historical(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_release_historical_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "1111111111111111111111111111111111111111"
    stale_head = "2222222222222222222222222222222222222222"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/release/release-evidence-attest-readiness.json",
        {
            "version": 1,
            "status": "ready",
            "blocker_type": "",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "release-evidence-attestation",
                    "state": "historical",
                    "note": f"latest successful remote workflow targets old head `{stale_head}`; current HEAD `{head}` still not externally verified",
                    "latest_run_matches_current_head": False,
                    "latest_run": {
                        "databaseId": 41,
                        "status": "completed",
                        "conclusion": "success",
                        "headSha": stale_head,
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {"version": 1, "status": "pass", "blocker_type": ""},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "pass",
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(tmp_path / "config/governance/upstream-compat-matrix.json", {"matrix": []})

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", list)

    rendered = module.render()

    assert "| `release-evidence-attestation` | `verified` |" not in rendered
    assert "| `release-evidence-attestation` | `ready` |" in rendered
    assert (
        "remote workflow is historical for current HEAD and does not count as current external verification"
        in rendered
    )


def test_current_state_summary_check_rejects_stale_summary_and_historical_greenwash(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "check_current_state_summary_test",
        "scripts/governance/check_current_state_summary.py",
    )
    head = "1111111111111111111111111111111111111111"
    stale_head = "2222222222222222222222222222222222222222"

    summary_path = tmp_path / ".runtime-cache/reports/governance/current-state-summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        "\n".join(
            [
                "# Current State Summary",
                "",
                f"- current HEAD: `{stale_head}`",
                "",
                "| Lane | Current State | Evidence / Note | Canonical Artifact |",
                "| --- | --- | --- | --- |",
                "| `release-evidence-attestation` | `verified` | stale | `x` |",
                "| `workflow:release-evidence-attestation` | `historical` | stale workflow | `y` |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_meta(
        summary_path,
        source_commit=stale_head,
        verification_scope="current-state-summary",
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "release-evidence-attestation",
                    "state": "historical",
                    "note": "historical run",
                    "latest_run_matches_current_head": False,
                    "latest_run": {
                        "databaseId": 51,
                        "status": "completed",
                        "conclusion": "success",
                        "headSha": stale_head,
                    },
                }
            ],
        },
    )

    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = module.main()

    output = stdout.getvalue()
    assert exit_code == 1, output
    assert "source_commit does not match current HEAD" in output
    assert "must not be rendered as `verified`" in output


def test_current_proof_contract_requires_critical_external_current_artifacts() -> None:
    payload = json.loads(
        (_repo_root() / "config" / "governance" / "current-proof-contract.json").read_text(
            encoding="utf-8"
        )
    )

    artifacts = {
        item["name"]: item
        for item in payload["artifacts"]
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    for name in (
        "remote-platform-truth",
        "remote-required-checks",
        "ghcr-standard-image-readiness",
        "external-lane-workflows",
        "release-evidence-attestation",
    ):
        assert artifacts[name]["required"] is True

    assert artifacts["remote-required-checks"]["reason"].startswith("fail-close:")


def test_probe_remote_platform_truth_uses_dedicated_pvr_endpoint_when_repo_field_missing(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "probe_remote_platform_truth_test",
        "scripts/governance/probe_remote_platform_truth.py",
    )
    head = "1111111111111111111111111111111111111111"

    def _fake_json_or_none(command: list[str]):
        cmd = " ".join(command)
        if cmd == "gh api user":
            return {"login": "tester"}, None
        if cmd.startswith("gh repo view "):
            return {
                "name": "sourceharbor",
                "owner": {"login": "xiaojiou176"},
                "visibility": "PUBLIC",
                "defaultBranchRef": {"name": "main"},
                "isPrivate": False,
            }, None
        if cmd == "gh api repos/xiaojiou176-open/sourceharbor":
            return {
                "private_vulnerability_reporting": None,
                "security_and_analysis": {},
            }, None
        if cmd == "gh api repos/xiaojiou176-open/sourceharbor/private-vulnerability-reporting":
            return {"enabled": True}, None
        if cmd == "gh api repos/xiaojiou176-open/sourceharbor/actions/permissions":
            return {"enabled": True}, None
        if cmd == "gh api repos/xiaojiou176-open/sourceharbor/actions/permissions/workflow":
            return {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            }, None
        if cmd == "gh api repos/xiaojiou176-open/sourceharbor/branches/main/protection":
            return {
                "required_status_checks": {
                    "contexts": [],
                }
            }, None
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_repo_slug", lambda: "xiaojiou176-open/sourceharbor")
    monkeypatch.setattr(module, "_current_actor", lambda: "tester")
    monkeypatch.setattr(
        module,
        "_run",
        lambda *args, check=True: type(
            "R", (), {"returncode": 0, "stdout": '{"login":"tester"}', "stderr": ""}
        )(),
    )
    monkeypatch.setattr(module, "_json_or_none", _fake_json_or_none)
    monkeypatch.setattr(module, "_load_required_checks", list)
    monkeypatch.setattr(module, "_actual_required_checks", lambda payload: [])
    monkeypatch.setattr(module, "current_git_commit", lambda: head)

    captured = {}

    def _capture_artifact(path, report, **kwargs):
        captured["report"] = report

    monkeypatch.setattr(module, "write_json_artifact", _capture_artifact)
    monkeypatch.setattr(
        sys, "argv", ["probe_remote_platform_truth.py", "--repo", "xiaojiou176-open/sourceharbor"]
    )

    exit_code = module.main()

    assert exit_code == 0
    assert captured["report"]["private_vulnerability_reporting"]["status"] == "enabled"
    assert captured["report"]["private_vulnerability_reporting"]["reason"].startswith(
        "dedicated private-vulnerability-reporting endpoint"
    )
    assert captured["report"]["workflow_permissions"]["default_workflow_permissions"] == "read"
    assert captured["report"]["workflow_permissions"]["can_approve_pull_request_reviews"] is False


def test_probe_remote_platform_truth_auto_switches_to_more_capable_actor(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "probe_remote_platform_truth_actor_fallback_test",
        "scripts/governance/probe_remote_platform_truth.py",
    )
    head = "9999999999999999999999999999999999999999"

    current_actor = {"value": "terryyifeng"}
    switched: list[str] = []

    def _fake_switch_actor(login: str) -> None:
        current_actor["value"] = login
        switched.append(login)

    def _fake_probe_repo_platform_truth(_slug: str, expected_required_checks: list[str]):
        if current_actor["value"] == "terryyifeng":
            return {
                "status": "blocked",
                "blocker_type": "branch-protection-platform-boundary",
                "actor": "terryyifeng",
                "actor_error": None,
                "repo_view": {"visibility": "PUBLIC"},
                "repo_view_error": None,
                "raw_repo_api": {},
                "raw_repo_api_error": None,
                "actions_permissions": {},
                "actions_permissions_error": None,
                "workflow_permissions": {},
                "workflow_permissions_error": None,
                "branch_protection": None,
                "branch_protection_error": {
                    "stderr": "gh: Not Found (HTTP 404)",
                    "stdout": "",
                    "returncode": 1,
                },
                "private_vulnerability_reporting": {"status": "enabled"},
                "security_and_analysis": {"status": "observed", "features": {}},
                "required_checks": {
                    "expected": expected_required_checks,
                    "actual": [],
                    "missing": [],
                    "extra": [],
                    "match": True,
                },
            }
        return {
            "status": "pass",
            "blocker_type": "",
            "actor": "xiaojiou176",
            "actor_error": None,
            "repo_view": {"visibility": "PUBLIC"},
            "repo_view_error": None,
            "raw_repo_api": {},
            "raw_repo_api_error": None,
            "actions_permissions": {},
            "actions_permissions_error": None,
            "workflow_permissions": {},
            "workflow_permissions_error": None,
            "branch_protection": {"required_status_checks": {"contexts": []}},
            "branch_protection_error": None,
            "private_vulnerability_reporting": {"status": "enabled"},
            "security_and_analysis": {"status": "observed", "features": {}},
            "required_checks": {
                "expected": expected_required_checks,
                "actual": [],
                "missing": [],
                "extra": [],
                "match": True,
            },
        }

    captured = {}

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "_repo_slug", lambda: "xiaojiou176-open/sourceharbor")
    monkeypatch.setattr(module, "_current_actor", lambda: "terryyifeng")
    monkeypatch.setattr(
        module, "_discover_logged_in_accounts", lambda: ["terryyifeng", "xiaojiou176"]
    )
    monkeypatch.setattr(module, "_switch_actor", _fake_switch_actor)
    monkeypatch.setattr(module, "_load_required_checks", lambda: ["trusted-pr-boundary"])
    monkeypatch.setattr(module, "_probe_repo_platform_truth", _fake_probe_repo_platform_truth)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda _path, report, **_kwargs: captured.setdefault("report", report),
    )
    monkeypatch.setattr(
        sys, "argv", ["probe_remote_platform_truth.py", "--repo", "xiaojiou176-open/sourceharbor"]
    )

    exit_code = module.main()

    assert exit_code == 0
    assert captured["report"]["actor"] == "xiaojiou176"
    assert captured["report"]["status"] == "pass"
    assert captured["report"]["actor_probe_attempts"] == [
        {
            "actor": "terryyifeng",
            "status": "blocked",
            "blocker_type": "branch-protection-platform-boundary",
        },
        {"actor": "xiaojiou176", "status": "pass", "blocker_type": ""},
    ]
    assert switched == ["xiaojiou176", "terryyifeng"]


def test_newcomer_workspace_verdict_dirty_worktree_forces_partial() -> None:
    module = _load_governance_module(
        "render_newcomer_result_proof_dirty_verdict_test",
        "scripts/governance/render_newcomer_result_proof.py",
    )

    status, blockers, note = module._workspace_verdict(
        newcomer_preflight_status="pass",
        governance_status="pass",
        repo_side_strict_status="pass",
        current_proof={"exists": True, "current_commit_aligned": True},
        worktree_dirty=True,
    )

    assert status == "partial"
    assert blockers == ["dirty_worktree"]
    assert "last committed snapshot" in note


def test_render_newcomer_result_proof_records_workspace_freshness(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_newcomer_result_proof_workspace_freshness_test",
        "scripts/governance/render_newcomer_result_proof.py",
    )
    head = "1111111111111111111111111111111111111111"

    manifests_dir = tmp_path / ".runtime-cache" / "run" / "manifests"
    logs_dir = tmp_path / ".runtime-cache" / "logs" / "governance"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "version": 1,
        "run_id": "strict-pass-run",
        "entrypoint": "strict-ci",
        "channel": "governance",
        "argv": ["--mode", "pre-push"],
        "created_at": "2026-03-23T10:00:00Z",
        "repo_commit": head,
        "env_profile": "unknown",
        "log_path": ".runtime-cache/logs/governance/strict-pass-run.jsonl",
        "gate_run_id": "strict-pass-run",
    }
    (manifests_dir / "strict-pass-run.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "strict-pass-run.jsonl").write_text(
        json.dumps(
            {"run_id": "strict-pass-run", "event": "complete", "message": "PASS"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    governance_manifest = dict(manifest)
    governance_manifest["run_id"] = "gov-pass-run"
    governance_manifest["entrypoint"] = "governance-audit"
    governance_manifest["log_path"] = ".runtime-cache/logs/governance/gov-pass-run.jsonl"
    (manifests_dir / "gov-pass-run.json").write_text(
        json.dumps(governance_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "gov-pass-run.jsonl").write_text(
        json.dumps(
            {"run_id": "gov-pass-run", "event": "complete", "message": "PASS"}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    validate_manifest = dict(manifest)
    validate_manifest["run_id"] = "validate-run"
    validate_manifest["entrypoint"] = "validate-profile"
    validate_manifest["log_path"] = ".runtime-cache/logs/governance/validate-run.jsonl"
    (manifests_dir / "validate-run.json").write_text(
        json.dumps(validate_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "validate-run.jsonl").write_text(
        json.dumps(
            {"run_id": "validate-run", "event": "complete", "message": "PASS"}, ensure_ascii=False
        )
        + "\n",
        encoding="utf-8",
    )

    resolved_env = tmp_path / ".runtime-cache" / "tmp" / ".env.local.resolved"
    resolved_env.parent.mkdir(parents=True, exist_ok=True)
    resolved_env.write_text("API_PORT=9000\n", encoding="utf-8")

    _write_json(
        tmp_path / ".runtime-cache/reports/evals/eval-regression.json",
        {
            "version": 1,
            "status": "passed",
            "pass_rate": 0.95,
        },
    )
    _write_meta(
        tmp_path / ".runtime-cache/reports/evals/eval-regression.json",
        source_commit=head,
        verification_scope="eval-regression",
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/current-proof-commit-alignment.json",
        {"version": 1, "status": "pass"},
    )
    _write_meta(
        tmp_path / ".runtime-cache/reports/governance/current-proof-commit-alignment.json",
        source_commit=head,
        verification_scope="current-proof-commit-alignment",
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {"version": 1, "status": "ready"},
    )
    _write_meta(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        source_commit=head,
        verification_scope="standard-image-publish-readiness",
    )

    captured: dict[str, object] = {}
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", lambda: [" M README.md"])
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda _path, report, **_kwargs: captured.setdefault("report", report),
    )

    exit_code = module.main()

    assert exit_code == 0
    report = captured["report"]
    assert isinstance(report, dict)
    verdict = report["current_workspace_verdict"]
    assert isinstance(verdict, dict)
    assert verdict["status"] == "partial"
    assert verdict["freshness"] == "stale"
    worktree_state = report["worktree_state"]
    assert isinstance(worktree_state, dict)
    assert worktree_state["workspace_freshness"] == "stale"


def test_render_newcomer_result_proof_accepts_repo_side_strict_receipt(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_newcomer_result_proof_repo_side_strict_test",
        "scripts/governance/render_newcomer_result_proof.py",
    )
    head = "2222222222222222222222222222222222222222"

    manifests_dir = tmp_path / ".runtime-cache" / "run" / "manifests"
    logs_dir = tmp_path / ".runtime-cache" / "logs" / "governance"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    repo_side_manifest = {
        "version": 1,
        "run_id": "repo-side-pass-run",
        "entrypoint": "repo-side-strict-ci",
        "channel": "governance",
        "argv": ["--mode", "pre-push"],
        "created_at": "2026-03-23T10:00:00Z",
        "repo_commit": head,
        "env_profile": "unknown",
        "log_path": ".runtime-cache/logs/governance/repo-side-pass-run.jsonl",
        "gate_run_id": "repo-side-pass-run",
    }
    (manifests_dir / "repo-side-pass-run.json").write_text(
        json.dumps(repo_side_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "repo-side-pass-run.jsonl").write_text(
        json.dumps(
            {"run_id": "repo-side-pass-run", "event": "entrypoint_bootstrap"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (logs_dir / "governance-gate.jsonl").write_text(
        json.dumps(
            {"run_id": "repo-side-pass-run", "event": "complete", "message": "PASS"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    governance_manifest = dict(repo_side_manifest)
    governance_manifest["run_id"] = "gov-pass-run"
    governance_manifest["entrypoint"] = "governance-audit"
    governance_manifest["log_path"] = ".runtime-cache/logs/governance/gov-pass-run.jsonl"
    (manifests_dir / "gov-pass-run.json").write_text(
        json.dumps(governance_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "gov-pass-run.jsonl").write_text(
        json.dumps(
            {"run_id": "gov-pass-run", "event": "complete", "message": "PASS"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    validate_manifest = dict(repo_side_manifest)
    validate_manifest["run_id"] = "validate-run"
    validate_manifest["entrypoint"] = "validate-profile"
    validate_manifest["log_path"] = ".runtime-cache/logs/governance/validate-run.jsonl"
    (manifests_dir / "validate-run.json").write_text(
        json.dumps(validate_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "validate-run.jsonl").write_text(
        json.dumps(
            {"run_id": "validate-run", "event": "complete", "message": "PASS"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    resolved_env = tmp_path / ".runtime-cache" / "tmp" / ".env.local.resolved"
    resolved_env.parent.mkdir(parents=True, exist_ok=True)
    resolved_env.write_text("API_PORT=9000\n", encoding="utf-8")

    _write_json(
        tmp_path / ".runtime-cache/reports/evals/eval-regression.json",
        {
            "version": 1,
            "status": "passed",
            "pass_rate": 0.95,
        },
    )
    _write_meta(
        tmp_path / ".runtime-cache/reports/evals/eval-regression.json",
        source_commit=head,
        verification_scope="eval-regression",
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/current-proof-commit-alignment.json",
        {"version": 1, "status": "pass"},
    )
    _write_meta(
        tmp_path / ".runtime-cache/reports/governance/current-proof-commit-alignment.json",
        source_commit=head,
        verification_scope="current-proof-commit-alignment",
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {"version": 1, "status": "ready"},
    )
    _write_meta(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        source_commit=head,
        verification_scope="standard-image-publish-readiness",
    )

    captured: dict[str, object] = {}
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda _path, report, **_kwargs: captured.setdefault("report", report),
    )

    exit_code = module.main()

    assert exit_code == 0
    report = captured["report"]
    assert isinstance(report, dict)
    strict_receipt = report["repo_side_strict_receipt"]
    assert isinstance(strict_receipt, dict)
    assert strict_receipt["status"] == "pass"
    manifest = strict_receipt["manifest"]
    assert isinstance(manifest, dict)
    assert manifest["entrypoint"] == "repo-side-strict-ci"
    verdict = report["current_workspace_verdict"]
    assert isinstance(verdict, dict)
    assert verdict["status"] == "pass"


def test_newcomer_workspace_verdict_missing_preflight_stays_missing_even_when_dirty() -> None:
    module = _load_governance_module(
        "render_newcomer_result_proof_missing_preflight_test",
        "scripts/governance/render_newcomer_result_proof.py",
    )

    status, blockers, note = module._workspace_verdict(
        newcomer_preflight_status="missing",
        governance_status="pass",
        repo_side_strict_status="pass",
        current_proof={"exists": True, "current_commit_aligned": True},
        worktree_dirty=True,
    )

    assert status == "missing"
    assert "newcomer_preflight_missing" in blockers
    assert "dirty_worktree" in blockers
    assert "missing" in note


def test_newcomer_result_proof_check_rejects_dirty_partial_without_explicit_blocker(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "check_newcomer_result_proof_dirty_blocker_test",
        "scripts/governance/check_newcomer_result_proof.py",
    )
    head = "1111111111111111111111111111111111111111"

    report_path = tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        report_path,
        {
            "version": 1,
            "status": "partial",
            "source_commit": head,
            "current_workspace_verdict": {
                "status": "partial",
                "blocking_conditions": [],
                "note": "incorrect fixture",
            },
            "newcomer_preflight": {
                "status": "pass",
                "resolved_env_exists": True,
            },
            "governance_audit_receipt": {"status": "pass"},
            "repo_side_strict_receipt": {"status": "pass"},
            "worktree_state": {
                "dirty": True,
            },
            "current_proof_alignment": {
                "exists": True,
                "current_commit_aligned": True,
            },
            "eval_regression": {"status": "passed"},
        },
    )
    _write_meta(
        report_path,
        source_commit=head,
        verification_scope="newcomer-result-proof",
    )

    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)

    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = module.main()

    output = stdout.getvalue()
    assert exit_code == 1, output
    assert "dirty worktree must be listed" in output


def test_render_current_state_summary_explains_pending_strict_ci_compose_row_via_ghcr_blocker(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_pending_compose_row_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "1111111111111111111111111111111111111111"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "blocked",
            "blocker_type": "registry-auth-failure",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "blocked",
                    "note": "remote workflow for current HEAD concluded `failure`",
                    "latest_run_matches_current_head": True,
                    "latest_run": {
                        "databaseId": 42,
                        "status": "completed",
                        "conclusion": "failure",
                        "headSha": head,
                    },
                    "failure_details": {
                        "failed_step_name": "Standard image publish preflight",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {"version": 1, "status": "pass", "blocker_type": ""},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "pass",
            "current_workspace_verdict": {"status": "pass", "blocking_conditions": []},
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(
        tmp_path / "config/governance/upstream-compat-matrix.json",
        {
            "matrix": [
                {
                    "name": "strict-ci-compose-image-set",
                    "verification_status": "pending",
                    "verification_lane": "external",
                    "evidence_artifact": ".runtime-cache/reports/governance/upstream-compat-report.json",
                }
            ]
        },
    )

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", list)

    rendered = module.render()

    assert (
        "| `strict-ci-compose-image-set` | `pending` | external; blocked on `ghcr-standard-image` (local readiness=blocked, remote state=blocked) |"
        in rendered
    )


def test_render_current_state_summary_reports_remote_platform_actor_context(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_remote_platform_actor_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "1111111111111111111111111111111111111111"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {
            "version": 1,
            "status": "blocked",
            "blocker_type": "branch-protection-platform-boundary",
            "actor": "terryyifeng",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "ready",
            "blocker_type": "",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "blocked",
                    "note": "remote workflow failed for current head",
                    "latest_run_matches_current_head": True,
                    "latest_run": {
                        "databaseId": 42,
                        "status": "completed",
                        "conclusion": "failure",
                        "headSha": head,
                    },
                    "failure_details": {
                        "failed_step_name": "Build and push strict CI standard image",
                        "failure_signature": "blob-head-403-forbidden",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "partial",
            "current_workspace_verdict": {
                "status": "partial",
                "blocking_conditions": ["dirty_worktree"],
            },
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/release/release-evidence-attest-readiness.json",
        {"version": 1, "status": "ready", "blocker_type": ""},
    )
    _write_json(
        tmp_path / "config/governance/upstream-compat-matrix.json",
        {"matrix": []},
    )

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", lambda: ["README.md"])

    rendered = module.render()

    assert (
        "| `remote-platform-integrity` | `blocked` | branch-protection-platform-boundary; actor=terryyifeng |"
        in rendered
    )


def test_render_current_state_summary_reports_current_head_preflight_failure_for_ghcr(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_preflight_failure_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "1111111111111111111111111111111111111111"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "blocked",
            "blocker_type": "registry-auth-failure",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "blocked",
                    "note": "remote workflow for current HEAD concluded `failure`",
                    "latest_run_matches_current_head": True,
                    "latest_run": {
                        "databaseId": 42,
                        "status": "completed",
                        "conclusion": "failure",
                        "headSha": head,
                    },
                    "failure_details": {
                        "job_name": "publish",
                        "failed_step_name": "Standard image publish preflight",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {"version": 1, "status": "pass", "blocker_type": ""},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "pass",
            "current_workspace_verdict": {"status": "pass", "blocking_conditions": []},
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(tmp_path / "config/governance/upstream-compat-matrix.json", {"matrix": []})

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", list)

    rendered = module.render()

    assert "| `ghcr-standard-image` | `blocked` |" in rendered
    assert "local readiness artifact=blocked:registry-auth-failure" in rendered
    assert "failed at `Standard image publish preflight` before build/push" in rendered


def test_render_current_state_summary_reports_manifest_unknown_for_ghcr(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_manifest_unknown_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "2222222222222222222222222222222222222222"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "blocked",
            "blocker_type": "registry-auth-failure",
            "manifest_probe": {
                "target": "ghcr.io/xiaojiou176-open/sourceharbor-ci-standard@sha256:test",
                "returncode": 1,
                "stdout": "",
                "stderr": "manifest unknown\n",
            },
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "blocked",
                    "note": "remote workflow for current HEAD concluded `failure`",
                    "latest_run_matches_current_head": True,
                    "latest_run": {
                        "databaseId": 43,
                        "status": "completed",
                        "conclusion": "failure",
                        "headSha": head,
                    },
                    "failure_details": {
                        "job_name": "publish",
                        "failed_step_name": "Standard image publish preflight",
                        "failure_signature": "ghcr-blob-upload-401-unauthorized",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {"version": 1, "status": "pass", "blocker_type": ""},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "pass",
            "current_workspace_verdict": {"status": "pass", "blocking_conditions": []},
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(tmp_path / "config/governance/upstream-compat-matrix.json", {"matrix": []})

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", list)

    rendered = module.render()

    assert "GHCR blob upload probe rejected the selected token with HTTP 401" in rendered
    assert "manifest unknown" in rendered


def test_render_current_state_summary_reports_ready_local_but_blocked_remote_ghcr(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "render_current_state_summary_ready_blocked_ghcr_test",
        "scripts/governance/render_current_state_summary.py",
    )
    head = "3333333333333333333333333333333333333333"

    (tmp_path / ".runtime-cache" / "reports" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "reports" / "release").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)

    _write_json(
        tmp_path / ".runtime-cache/reports/governance/standard-image-publish-readiness.json",
        {
            "version": 1,
            "status": "ready",
            "blocker_type": "",
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/external-lane-workflows.json",
        {
            "version": 1,
            "source_commit": head,
            "lanes": [
                {
                    "name": "ghcr-standard-image",
                    "state": "blocked",
                    "note": "remote workflow for current HEAD concluded `failure`",
                    "latest_run_matches_current_head": True,
                    "latest_run": {
                        "databaseId": 44,
                        "status": "completed",
                        "conclusion": "failure",
                        "headSha": head,
                    },
                    "failure_details": {
                        "job_name": "publish",
                        "failed_step_name": "Build and push strict CI standard image",
                        "failure_signature": "blob-head-403-forbidden",
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json",
        {"version": 1, "status": "pass", "blocker_type": "", "actor": "xiaojiou176"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/remote-required-checks.json",
        {
            "version": 1,
            "status": "pass",
            "expected_required_checks": ["a"],
            "actual_required_checks": ["a"],
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/open-source-audit-freshness.json",
        {"version": 1, "status": "pass"},
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/governance/newcomer-result-proof.json",
        {
            "version": 1,
            "status": "partial",
            "current_workspace_verdict": {
                "status": "partial",
                "blocking_conditions": ["dirty_worktree"],
            },
            "repo_side_strict_receipt": {"status": "pass"},
        },
    )
    _write_json(
        tmp_path / ".runtime-cache/reports/release/release-evidence-attest-readiness.json",
        {"version": 1, "status": "ready", "blocker_type": ""},
    )
    _write_json(tmp_path / "config/governance/upstream-compat-matrix.json", {"matrix": []})

    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "_current_head", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", lambda: ["README.md"])

    rendered = module.render()

    assert "- current workspace freshness: `stale`" in rendered
    assert (
        "| `ghcr-standard-image` | `blocked` | local readiness artifact=ready:ok; latest remote current-head workflow preflight passed; blocked at `Build and push strict CI standard image`; GHCR blob HEAD returned 403 Forbidden |"
        in rendered
    )


def test_current_proof_alignment_report_records_dirty_workspace_context(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "check_current_proof_commit_alignment_workspace_context_test",
        "scripts/governance/check_current_proof_commit_alignment.py",
    )
    head = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    artifact = tmp_path / ".runtime-cache/reports/governance/remote-platform-truth.json"
    _write_json(
        artifact,
        {"version": 1, "status": "pass"},
    )
    _write_meta(
        artifact,
        source_commit=head,
        verification_scope="remote-platform-truth",
    )

    captured: dict[str, object] = {}
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "current_git_commit", lambda: head)
    monkeypatch.setattr(module, "_worktree_changes", lambda _root: [" M README.md"])
    monkeypatch.setattr(
        module,
        "load_governance_json",
        lambda _name: {
            "artifacts": [
                {
                    "name": "remote-platform-truth",
                    "artifact": ".runtime-cache/reports/governance/remote-platform-truth.json",
                    "required": True,
                    "reason": "fixture",
                }
            ]
        },
    )
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda _path, report, **_kwargs: captured.setdefault("report", report),
    )

    exit_code = module.main()

    assert exit_code == 0
    report = captured["report"]
    assert isinstance(report, dict)
    worktree_state = report["worktree_state"]
    assert isinstance(worktree_state, dict)
    assert worktree_state["dirty"] is True
    assert worktree_state["workspace_freshness"] == "stale"


def test_upstream_same_run_cohesion_allows_current_diagnostic_artifacts(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "check_upstream_same_run_cohesion_diagnostic_test",
        "scripts/governance/check_upstream_same_run_cohesion.py",
    )

    head = "1111111111111111111111111111111111111111"
    report_path = tmp_path / ".runtime-cache/reports/governance/upstream-compat-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(report_path, {"version": 1, "status": "pass"})
    _write_meta(
        report_path,
        source_commit=head,
        verification_scope="upstream-compat-report",
        source_run_id="historic-success-run",
    )

    row_log = tmp_path / ".runtime-cache/logs/tests/compat-rsshub-youtube-ingest.log"
    row_log.parent.mkdir(parents=True, exist_ok=True)
    row_log.write_text("diagnostic artifact\n", encoding="utf-8")
    _write_meta(
        row_log,
        source_commit=head,
        verification_scope="upstream:rsshub-youtube-ingest-chain",
        source_run_id="current-diagnostic-run",
        extra={"status": "diagnostic", "report_kind": "provider-compat-log"},
    )

    matrix = {
        "matrix": [
            {
                "name": "rsshub-youtube-ingest-chain",
                "blocking_level": "blocker",
                "verification_status": "verified",
                "verification_lane": "provider",
                "last_verified_run_id": "historic-success-run",
                "verification_artifacts": [
                    ".runtime-cache/reports/governance/upstream-compat-report.json",
                    ".runtime-cache/logs/tests/compat-rsshub-youtube-ingest.log",
                ],
            }
        ]
    }

    captured: dict[str, object] = {}
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "load_governance_json", lambda _name: matrix)
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda _path, report, **_kwargs: captured.setdefault("report", report),
    )

    exit_code = module.main()

    assert exit_code == 0
    report = captured["report"]
    assert report["status"] == "pass"
    row = report["rows"][0]
    assert row["status"] == "pass"
    assert row["diagnostic_mismatched_run_ids"] == [
        ".runtime-cache/logs/tests/compat-rsshub-youtube-ingest.log -> current-diagnostic-run"
    ]


def test_upstream_same_run_cohesion_rejects_non_diagnostic_mismatch(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_governance_module(
        "check_upstream_same_run_cohesion_strict_mismatch_test",
        "scripts/governance/check_upstream_same_run_cohesion.py",
    )

    head = "1111111111111111111111111111111111111111"
    report_path = tmp_path / ".runtime-cache/reports/governance/upstream-compat-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(report_path, {"version": 1, "status": "pass"})
    _write_meta(
        report_path,
        source_commit=head,
        verification_scope="upstream-compat-report",
        source_run_id="historic-success-run",
    )

    row_log = tmp_path / ".runtime-cache/logs/tests/compat-rsshub-youtube-ingest.log"
    row_log.parent.mkdir(parents=True, exist_ok=True)
    row_log.write_text("non-diagnostic artifact\n", encoding="utf-8")
    _write_meta(
        row_log,
        source_commit=head,
        verification_scope="upstream:rsshub-youtube-ingest-chain",
        source_run_id="unexpected-run",
    )

    matrix = {
        "matrix": [
            {
                "name": "rsshub-youtube-ingest-chain",
                "blocking_level": "blocker",
                "verification_status": "verified",
                "verification_lane": "provider",
                "last_verified_run_id": "historic-success-run",
                "verification_artifacts": [
                    ".runtime-cache/reports/governance/upstream-compat-report.json",
                    ".runtime-cache/logs/tests/compat-rsshub-youtube-ingest.log",
                ],
            }
        ]
    }

    captured: dict[str, object] = {}
    monkeypatch.setattr(module, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(module, "load_governance_json", lambda _name: matrix)
    monkeypatch.setattr(
        module,
        "write_json_artifact",
        lambda _path, report, **_kwargs: captured.setdefault("report", report),
    )

    exit_code = module.main()

    assert exit_code == 1
    report = captured["report"]
    assert report["status"] == "fail"
    row = report["rows"][0]
    assert row["status"] == "fail"
    assert row["diagnostic_mismatched_run_ids"] == []
