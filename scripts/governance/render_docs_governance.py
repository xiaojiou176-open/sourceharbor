#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_HEADER = "<!-- generated: docs governance control plane -->\n\n"


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _maybe_load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return _load_json(path)


def _job_names(workflow_text: str) -> list[str]:
    lines = workflow_text.splitlines()
    inside_jobs = False
    job_names: list[str] = []

    for line in lines:
        if not inside_jobs:
            if line.strip() == "jobs:":
                inside_jobs = True
            continue

        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            job_names.append(match.group(1))

    return job_names


def _workflow_job_names(relative_path: str) -> list[str]:
    workflow_text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    return _job_names(workflow_text)


def _extract_workflow_job_runs_on(workflow_text: str, job_name: str) -> str | None:
    match = re.search(
        rf"^\s{{2}}{re.escape(job_name)}:\n(?P<body>(?:^\s{{4}}.*\n?)*)",
        workflow_text,
        flags=re.MULTILINE,
    )
    if not match:
        return None
    runner_match = re.search(r"^\s{4}runs-on:\s*(.+)$", match.group("body"), flags=re.MULTILINE)
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


def _advisory_security_workflows_line() -> str:
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


def _render_governance_dashboard() -> str:
    nav = _load_json(REPO_ROOT / "config" / "docs" / "nav-registry.json")
    boundary = _load_json(REPO_ROOT / "config" / "docs" / "boundary-policy.json")
    surfaces = [f"`{item}`" for item in boundary["first_hop_truth_surfaces"]]
    section_count = len(nav.get("sections", []))
    doc_count = sum(len(section.get("docs", [])) for section in nav.get("sections", []))
    lines = [
        GENERATED_HEADER.rstrip(),
        "# Governance Dashboard",
        "",
        "This is the thin public-doc control plane for the current SourceHarbor snapshot.",
        "",
        f"- first-hop truth surfaces: {', '.join(surfaces)}",
        f"- nav sections tracked: `{section_count}`",
        f"- tracked doc entries: `{doc_count}`",
        "- generated references: `docs/generated/ci-topology.md`, `docs/generated/required-checks.md`, `docs/generated/external-lane-truth-entry.md`",
        "- public readiness explainer: `docs/reference/public-repo-readiness.md`",
        "- public asset provenance ledger: `docs/reference/public-assets-provenance.md`",
        "- GitHub profile verify entrypoint: `python3 scripts/github/apply_public_profile.py --verify`",
        "",
        "The goal is simple: keep the public surface small, real, and rerunnable.",
        "",
    ]
    return "\n".join(lines)


def _render_external_lane_snapshot() -> str:
    contract = _load_json(REPO_ROOT / "config" / "governance" / "external-lane-contract.json")
    lines = [
        GENERATED_HEADER.rstrip(),
        "",
        "# External Lane Truth Entry",
        "",
        "This tracked page is a machine-rendered pointer only.",
        "",
        "It must not carry current verdict payload. Read the runtime-owned reports directly for commit-sensitive state.",
        "",
        "| Lane | Canonical Artifact | Reading Rule |",
        "| --- | --- | --- |",
    ]
    for lane in contract.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        name = str(lane.get("name") or "").strip()
        artifact = str(lane.get("canonical_artifact") or "").strip()
        lines.append(
            f"| `{name}` | `{artifact}` | tracked pointer only; runtime reports decide current state |"
        )
    lines.extend(
        [
            "",
            "- tracked page is a machine-rendered pointer only",
            "- current external state must come from `.runtime-cache/reports/**`",
            "- stale successful remote workflows should be treated as `historical`, not promoted to current `verified` wording",
            "",
        ]
    )
    return "\n".join(lines)


def _render_ci_topology() -> str:
    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    root_allowlist = _load_json(REPO_ROOT / "config" / "governance" / "root-allowlist.json")
    runtime_outputs = _load_json(REPO_ROOT / "config" / "governance" / "runtime-outputs.json")
    jobs = _job_names(ci_text)
    pre_commit_jobs = _workflow_job_names(".github/workflows/pre-commit.yml")
    lines = [
        GENERATED_HEADER.rstrip(),
        "# CI Topology",
        "",
        "Current deterministic PR-facing CI in this repository is intentionally small and local-proof-first.",
        "",
        f"- root allowlist entries: `{len(root_allowlist.get('tracked_root_allowlist', []))}`",
        f"- runtime root: `{runtime_outputs.get('runtime_root', '.runtime-cache')}`",
        f"- CI jobs in `.github/workflows/ci.yml`: {', '.join(f'`{job}`' for job in jobs)}",
        f"- Pre-commit workflow jobs in `.github/workflows/pre-commit.yml`: {', '.join(f'`{job}`' for job in pre_commit_jobs)}",
        "- canonical python-tests command: `bash scripts/ci/python_tests.sh`",
        "- pre-push is a contributor-side parity hook: it reruns env contract, placebo assertion guard, `bash scripts/ci/python_tests.sh`, and web lint locally after a deterministic `npm ci` refresh when tracked web manifests drift or `apps/web/node_modules/.bin/next` is missing.",
        _advisory_security_workflows_line(),
        _expected_ci_topology_standard_image_line(),
        "- release evidence attestation stays in `.github/workflows/release-evidence-attest.yml`.",
        "",
        "## Five-layer verification map",
        "",
        "| Layer | Primary entrypoints | Reading rule |",
        "| --- | --- | --- |",
        "| `pre-commit` | fast local checks in `docs/testing.md` + `npm run lint` | fastest contributor-side contract before deeper proof |",
        "| `pre-push` | `.githooks/pre-push` | default local parity hook; keep it deterministic instead of turning it into a full closeout audit |",
        "| `hosted` | `ci.yml`, `pre-commit.yml`, `dependency-review.yml`, `codeql.yml` on `pull_request`/`push`, `trivy.yml`, `trufflehog.yml`, `zizmor.yml` | branch-protected GitHub contract for pull requests and `main` |",
        "| `nightly` | `codeql.yml` on `schedule` | background CodeQL refresh; keep it thin and do not create a separate weekly governance bucket |",
        "| `manual` | `./bin/repo-side-strict-ci --mode pre-push`, `./bin/quality-gate --mode pre-push`, `./bin/governance-audit --mode audit`, `./bin/smoke-full-stack --offline-fallback 0`, repo-owned real-profile browser proof, `build-ci-standard-image.yml`, `release-evidence-attest.yml` | provider/browser/release/publication truth plus closeout-grade repo/public audits |",
        "",
    ]
    return "\n".join(lines)


def _render_required_checks() -> str:
    checks = [
        ("python-tests", "ci.yml"),
        ("web-lint", "ci.yml"),
        ("pre-commit", "pre-commit.yml"),
        ("CodeQL", "codeql.yml"),
        ("dependency-review", "dependency-review.yml"),
        ("trivy-fs", "trivy.yml"),
        ("trufflehog", "trufflehog.yml"),
        ("zizmor", "zizmor.yml"),
    ]
    lines = [
        GENERATED_HEADER.rstrip(),
        "# Required Checks",
        "",
        "These are the GitHub Actions checks currently enforced by branch protection on the repository's pull-request path.",
        "",
        "Local Git hooks may rerun overlapping checks, but they are contributor-side guardrails rather than the remote branch-protection contract.",
        "",
        "| Check | Workflow | Why it exists |",
        "| --- | --- | --- |",
    ]
    explanations = {
        "python-tests": "Verifies API, worker, and MCP Python surfaces with the documented in-memory SQLite test path.",
        "web-lint": "Keeps the web command center lint-clean.",
        "pre-commit": "Runs the all-files hygiene gate for YAML, secrets, Ruff, Biome, Markdown, ShellCheck, and Actionlint.",
        "CodeQL": "Runs GitHub code scanning over the tracked Python and JavaScript/TypeScript surfaces.",
        "dependency-review": "Blocks pull requests whose dependency changes fail GitHub's dependency review policy.",
        "trivy-fs": "Scans the repository filesystem and dependency manifests for high-severity vulnerabilities.",
        "trufflehog": "Scans the pushed and pull-request Git history delta for verified or unknown secrets.",
        "zizmor": "Lint-checks GitHub Actions workflow safety on the PR-facing workflow set.",
    }
    for check_name, workflow_name in checks:
        lines.append(
            f"| `{check_name}` | `{workflow_name}` | {explanations.get(check_name, 'Tracked by the current CI workflow.')} |"
        )
    lines.append("")
    return "\n".join(lines)


def _expected_outputs() -> dict[Path, str]:
    return {
        REPO_ROOT
        / "docs"
        / "generated"
        / "governance-dashboard.md": _render_governance_dashboard(),
        REPO_ROOT / "docs" / "generated" / "ci-topology.md": _render_ci_topology(),
        REPO_ROOT / "docs" / "generated" / "required-checks.md": _render_required_checks(),
        REPO_ROOT
        / "docs"
        / "generated"
        / "external-lane-truth-entry.md": _render_external_lane_snapshot(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render thin docs governance references")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    mismatches: list[str] = []
    for path, content in _expected_outputs().items():
        if args.check:
            existing = path.read_text(encoding="utf-8") if path.exists() else None
            if existing != content:
                mismatches.append(path.relative_to(REPO_ROOT).as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    if mismatches:
        print("docs governance render out of date:")
        for path in mismatches:
            print(f"- {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
