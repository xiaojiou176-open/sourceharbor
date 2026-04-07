from __future__ import annotations

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_check_docs_governance_module():
    root = _repo_root()
    module_path = root / "scripts" / "governance" / "check_docs_governance.py"
    spec = spec_from_file_location("check_docs_governance", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docs_control_plane_files_exist_and_reference_real_paths() -> None:
    root = _repo_root()
    for relative in (
        "config/docs/nav-registry.json",
        "config/docs/render-manifest.json",
        "config/docs/boundary-policy.json",
        "config/docs/change-contract.json",
    ):
        assert (root / relative).is_file(), relative

    nav = json.loads((root / "config/docs/nav-registry.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "config/docs/render-manifest.json").read_text(encoding="utf-8"))
    boundary = json.loads((root / "config/docs/boundary-policy.json").read_text(encoding="utf-8"))

    nav_paths = {item for section in nav["sections"] for item in section["docs"]}
    generated_paths = {entry["path"] for entry in manifest["generated_docs"]}
    fragment_paths = {entry["path"] for entry in manifest["fragments"]}

    for relative in (
        nav_paths | generated_paths | fragment_paths | set(boundary["manual_docs"].keys())
    ):
        assert (root / relative).exists(), relative


def test_boundary_policy_declares_and_docs_match_first_hop_truth_surfaces() -> None:
    root = _repo_root()
    boundary = json.loads((root / "config/docs/boundary-policy.json").read_text(encoding="utf-8"))
    docs_index = (root / "docs/index.md").read_text(encoding="utf-8")
    module = _load_check_docs_governance_module()

    expected = set(boundary["first_hop_truth_surfaces"])

    docs_index_route = module._extract_section_text(docs_index, "First-Hop Route")
    assert docs_index_route is not None
    docs_index_surfaces = module._extract_first_hop_code_refs(docs_index_route)
    assert docs_index_surfaces == expected


def test_render_docs_governance_check_passes_for_repo_snapshot() -> None:
    root = _repo_root()
    result = subprocess.run(
        [sys.executable, "scripts/governance/render_docs_governance.py", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_governance_blocking_check_passes_for_repo_snapshot() -> None:
    root = _repo_root()
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "governance" / "check_docs_governance.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_docs_reference_current_semantics_and_counts() -> None:
    root = _repo_root()
    ci_topology = (root / "docs/generated/ci-topology.md").read_text(encoding="utf-8")
    dashboard = (root / "docs/generated/governance-dashboard.md").read_text(encoding="utf-8")
    required_checks = (root / "docs/generated/required-checks.md").read_text(encoding="utf-8")
    root_allowlist = json.loads(
        (root / "config/governance/root-allowlist.json").read_text(encoding="utf-8")
    )

    assert (
        f"- root allowlist entries: `{len(root_allowlist['tracked_root_allowlist'])}`"
        in ci_topology
    )
    assert "- GHCR image publish workflow runs on `ubuntu-latest`" in ci_topology
    assert (
        "Pre-commit workflow jobs in `.github/workflows/pre-commit.yml`: `pre-commit`"
        in ci_topology
    )
    assert "| `pre-commit` |" in ci_topology
    assert "| `pre-push` |" in ci_topology
    assert "| `hosted` |" in ci_topology
    assert "| `nightly` |" in ci_topology
    assert "| `manual` |" in ci_topology
    assert "do not create a separate weekly governance bucket" in ci_topology
    assert "`pre-commit.yml`" in required_checks
    assert "`pre-commit`" in required_checks
    assert "`python-tests`" in required_checks
    assert "`web-lint`" in required_checks
    assert "`pull_request`" not in required_checks
    assert "`push`" not in required_checks
    assert "`README.md`" in dashboard
    assert "`docs/generated/ci-topology.md`" in dashboard


def test_doc_drift_script_uses_control_plane_contract() -> None:
    script = (_repo_root() / "scripts/governance/ci_or_local_gate_doc_drift.sh").read_text(
        encoding="utf-8"
    )

    assert "config/docs/change-contract.json" in script
    assert "PIPELINE_STEPS_CHANGED" in script
    assert "[doc-drift] missing required doc update for" in script


def test_generated_governance_dashboard_and_required_checks_exist() -> None:
    root = _repo_root()
    for relative in (
        "docs/generated/governance-dashboard.md",
        "docs/generated/required-checks.md",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "generated: docs governance control plane" in text


def test_third_party_notice_scope_matches_inventory_contract() -> None:
    root = _repo_root()
    inventory = json.loads(
        (root / "artifacts" / "licenses" / "third-party-license-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    notice = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    shared_phrase = (
        "throwaway temp uv environment instead of root `.venv` or repo-owned runtime roots"
    )

    assert shared_phrase in inventory["scope"]["python"]
    assert ".runtime-cache/tmp/" not in inventory["scope"]["python"]
    assert shared_phrase in notice


def test_render_docs_governance_uses_runtime_release_readiness_inputs() -> None:
    script = Path("scripts/governance/render_docs_governance.py").read_text(encoding="utf-8")

    assert 'REPO_ROOT / ".github" / "workflows" / "ci.yml"' in script
    assert 'REPO_ROOT / ".github" / "workflows" / "build-ci-standard-image.yml"' in script
    assert 'REPO_ROOT / "config" / "docs" / "nav-registry.json"' in script


def test_reference_docs_fail_close_remote_required_checks_semantics() -> None:
    root = _repo_root()
    public_readiness = (root / "docs" / "reference" / "public-repo-readiness.md").read_text(
        encoding="utf-8"
    )
    required_checks = (root / "docs" / "generated" / "required-checks.md").read_text(
        encoding="utf-8"
    )
    ci_topology = (root / "docs" / "generated" / "ci-topology.md").read_text(encoding="utf-8")

    assert "`python-tests`" in required_checks
    assert "`web-lint`" in required_checks
    assert "`pre-commit`" in required_checks
    assert "release evidence attestation" in ci_topology.lower()
    assert "publicly readable and locally runnable" in public_readiness
    assert (
        "does **not** automatically mean every remote or release claim is proven"
        in public_readiness
    )


def test_ci_topology_ghcr_workflow_line_tracks_workflow_runner_semantics() -> None:
    root = _repo_root()
    module = _load_check_docs_governance_module()
    ci_topology = (root / "docs/generated/ci-topology.md").read_text(encoding="utf-8")

    expected_line = module._expected_ci_topology_standard_image_line()

    assert expected_line == (
        "- GHCR image publish workflow runs on `ubuntu-latest` and sets up Docker Buildx "
        "before calling `scripts/ci/build_standard_image.sh`"
    )
    assert expected_line in ci_topology
