from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_public_governance_pack_exists() -> None:
    root = _repo_root()
    required = [
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "SUPPORT.md",
        ".github/CODEOWNERS",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        "docs/reference/public-repo-readiness.md",
        "docs/reference/public-artifact-exposure.md",
        "docs/reference/project-positioning.md",
        "docs/reference/ai-evaluation.md",
    ]

    for relative in required:
        assert (root / relative).is_file(), relative


def test_eval_assets_gate_passes_for_repo_snapshot() -> None:
    root = _repo_root()
    result = subprocess.run(
        [sys.executable, str(root / "scripts/governance/check_eval_assets.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_upstream_compat_matrix_declares_verification_lane() -> None:
    root = _repo_root()
    matrix = json.loads(
        (root / "config/governance/upstream-compat-matrix.json").read_text(encoding="utf-8")
    )

    assert matrix["matrix"]
    assert {row["verification_lane"] for row in matrix["matrix"]}.issubset(
        {"repo-side", "external", "provider"}
    )
