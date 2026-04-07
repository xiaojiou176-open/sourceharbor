#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config" / "docs"
GENERATED_HEADER = "<!-- generated: docs governance control plane -->"


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _check_paths_exist(paths: list[str]) -> list[str]:
    failures: list[str] = []
    for raw in paths:
        if not (REPO_ROOT / raw).exists():
            failures.append(f"missing path: {raw}")
    return failures


def _extract_section_text(text: str, heading: str) -> str | None:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)")
    match = pattern.search(text)
    return match.group("body") if match else None


def _extract_first_hop_code_refs(text: str) -> set[str]:
    return {match for match in re.findall(r"`([^`]+)`", text) if match.endswith(".md")}


def _front_door_docs() -> list[str]:
    front_door_docs = ["README.md", "docs/start-here.md", "docs/index.md", "docs/proof.md"]
    md_pattern = re.compile(r"\((\./[^)]+\.md|\.\./[^)]+\.md|[^)]+\.md)\)")
    routed: set[str] = set()
    for rel in front_door_docs:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for raw in md_pattern.findall(text):
            normalized = raw.removeprefix("./")
            if normalized.startswith("../"):
                normalized = normalized[3:]
            if normalized.startswith("docs/") or normalized in {
                "README.md",
                "CONTRIBUTING.md",
                "SUPPORT.md",
                "SECURITY.md",
                "CHANGELOG.md",
                "NOTICE.md",
                "CODE_OF_CONDUCT.md",
            }:
                routed.add(normalized)
    return sorted(routed)


def _check_control_plane() -> list[str]:
    failures: list[str] = []
    nav = _load_json(CONFIG_DIR / "nav-registry.json")
    manifest = _load_json(CONFIG_DIR / "render-manifest.json")
    boundary = _load_json(CONFIG_DIR / "boundary-policy.json")
    change_contract = _load_json(CONFIG_DIR / "change-contract.json")

    nav_docs: list[str] = []
    for section in nav.get("sections", []):
        nav_docs.extend(section.get("docs", []))
    failures.extend(_check_paths_exist(nav_docs))

    for path in _front_door_docs():
        if path not in nav_docs:
            failures.append(f"front-door route missing from nav-registry.json: {path}")

    render_paths = [entry["path"] for entry in manifest.get("generated_docs", [])]
    failures.extend(_check_paths_exist(render_paths))
    failures.extend(_check_paths_exist([entry["path"] for entry in manifest.get("fragments", [])]))

    manual_docs = boundary.get("manual_docs", {})
    for path in manual_docs:
        if not (REPO_ROOT / path).exists():
            failures.append(f"manual boundary doc missing: {path}")

    for rule in change_contract.get("rules", []):
        failures.extend(_check_paths_exist(rule.get("required_paths", [])))

    first_hop = boundary.get("first_hop_truth_surfaces", [])
    if not isinstance(first_hop, list) or not first_hop:
        failures.append("boundary policy missing first_hop_truth_surfaces")
    else:
        docs_index_text = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        first_hop_section = _extract_section_text(docs_index_text, "First-Hop Route")
        if first_hop_section is None:
            failures.append("docs/index.md: missing `## First-Hop Route` section")
        else:
            observed = _extract_first_hop_code_refs(first_hop_section)
            expected = set(first_hop)
            missing = sorted(expected - observed)
            unexpected = sorted(observed - expected)
            if missing:
                failures.append(
                    "docs/index.md: first-hop route missing configured truth surfaces: "
                    + ", ".join(missing)
                )
            if unexpected:
                failures.append(
                    "docs/index.md: first-hop route contains unexpected truth surfaces: "
                    + ", ".join(unexpected)
                )

    return failures


def _check_render_freshness() -> list[str]:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/render_docs_governance.py",
            "--check",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    lines = [line for line in (result.stdout + "\n" + result.stderr).splitlines() if line.strip()]
    return lines or ["docs governance render freshness failed"]


def _extract_workflow_job_runs_on(workflow_text: str, job_name: str) -> str | None:
    match = re.search(
        rf"^\s{{2}}{re.escape(job_name)}:\n(?P<body>(?:^\s{{4}}.*\n?)*)",
        workflow_text,
        flags=re.MULTILINE,
    )
    if not match:
        return None
    body = match.group("body")
    runner_match = re.search(r"^\s{4}runs-on:\s*(.+)$", body, flags=re.MULTILINE)
    return runner_match.group(1).strip() if runner_match else None


def _expected_ci_topology_standard_image_line() -> str:
    workflow_text = (REPO_ROOT / ".github" / "workflows" / "build-ci-standard-image.yml").read_text(
        encoding="utf-8"
    )
    runner = _extract_workflow_job_runs_on(workflow_text, "publish") or "unknown"
    return (
        "- GHCR image publish workflow runs on "
        f"`{runner}` and sets up Docker Buildx before calling `scripts/ci/build_standard_image.sh`"
    )


def _expected_advisory_security_workflows_line() -> str:
    workflows = [
        "codeql.yml",
        "dependency-review.yml",
        "zizmor.yml",
        "trivy.yml",
        "trufflehog.yml",
    ]
    present = [
        f"`{name}`" for name in workflows if (REPO_ROOT / ".github" / "workflows" / name).exists()
    ]
    return "- PR-facing security workflows: " + ", ".join(present)


def _check_generated_doc_semantics() -> list[str]:
    failures: list[str] = []
    runtime_outputs = _load_json(REPO_ROOT / "config" / "governance" / "runtime-outputs.json")
    root_allowlist = _load_json(REPO_ROOT / "config" / "governance" / "root-allowlist.json")

    generated_docs = [
        REPO_ROOT / "docs" / "generated" / "governance-dashboard.md",
        REPO_ROOT / "docs" / "generated" / "ci-topology.md",
        REPO_ROOT / "docs" / "generated" / "required-checks.md",
        REPO_ROOT / "docs" / "generated" / "external-lane-truth-entry.md",
    ]
    for path in generated_docs:
        text = path.read_text(encoding="utf-8")
        if GENERATED_HEADER not in text:
            failures.append(f"{path.relative_to(REPO_ROOT).as_posix()}: missing generated header")

    ci_topology = (REPO_ROOT / "docs" / "generated" / "ci-topology.md").read_text(encoding="utf-8")
    expected_root_line = (
        f"- root allowlist entries: `{len(root_allowlist.get('tracked_root_allowlist', []))}`"
    )
    if expected_root_line not in ci_topology:
        failures.append("docs/generated/ci-topology.md: root allowlist count drifted")
    expected_runtime_root = (
        f"- runtime root: `{runtime_outputs.get('runtime_root', '.runtime-cache')}`"
    )
    if expected_runtime_root not in ci_topology:
        failures.append("docs/generated/ci-topology.md: runtime root drifted")
    if "`bash scripts/ci/python_tests.sh`" not in ci_topology:
        failures.append("docs/generated/ci-topology.md: missing canonical python-tests command")
    if _expected_ci_topology_standard_image_line() not in ci_topology:
        failures.append("docs/generated/ci-topology.md: GHCR workflow summary drifted")
    if (
        "Pre-commit workflow jobs in `.github/workflows/pre-commit.yml`: `pre-commit`"
        not in ci_topology
    ):
        failures.append("docs/generated/ci-topology.md: missing pre-commit workflow summary")
    if _expected_advisory_security_workflows_line() not in ci_topology:
        failures.append(
            "docs/generated/ci-topology.md: PR-facing security workflow summary drifted"
        )
    for layer in ("pre-commit", "pre-push", "hosted", "nightly", "manual"):
        if f"| `{layer}` |" not in ci_topology:
            failures.append(f"docs/generated/ci-topology.md: missing `{layer}` layer row")
    if "do not create a separate weekly governance bucket" not in ci_topology:
        failures.append("docs/generated/ci-topology.md: missing nightly no-weekly guidance")

    required_checks = (REPO_ROOT / "docs" / "generated" / "required-checks.md").read_text(
        encoding="utf-8"
    )
    for job_name in (
        "python-tests",
        "web-lint",
        "pre-commit",
        "CodeQL",
        "dependency-review",
        "trivy-fs",
        "trufflehog",
        "zizmor",
    ):
        if f"`{job_name}`" not in required_checks:
            failures.append(f"docs/generated/required-checks.md: missing `{job_name}`")

    dashboard = (REPO_ROOT / "docs" / "generated" / "governance-dashboard.md").read_text(
        encoding="utf-8"
    )
    if "`README.md`" not in dashboard or "`docs/start-here.md`" not in dashboard:
        failures.append("docs/generated/governance-dashboard.md: missing first-hop surfaces")
    if "`docs/generated/ci-topology.md`" not in dashboard:
        failures.append("docs/generated/governance-dashboard.md: missing generated doc route")
    if "`docs/generated/external-lane-truth-entry.md`" not in dashboard:
        failures.append(
            "docs/generated/governance-dashboard.md: missing external-lane generated doc route"
        )

    return failures


def main() -> int:
    failures = _check_control_plane()
    failures.extend(_check_render_freshness())
    failures.extend(_check_generated_doc_semantics())
    if failures:
        print("docs governance check failed:")
        for item in failures:
            print(f"- {item}")
        return 1
    print("docs governance check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
