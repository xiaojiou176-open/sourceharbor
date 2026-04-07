from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "governance"
        / "check_host_specific_path_references.py"
    )
    spec = importlib.util.spec_from_file_location("host_path_governance_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scan_text_rejects_host_specific_user_paths() -> None:
    module = _load_module()
    bad_user_path = "/" + "Users" + "/alice/Documents/project"
    bad_user_prefix = "/" + "Users" + "/alice"

    errors = module._scan_text(
        f'bad path = "{bad_user_path}"',
        rel_path="README.md",
    )

    assert len(errors) == 1
    assert bad_user_prefix in errors[0]


def test_scan_text_rejects_old_workspace_prefix() -> None:
    module = _load_module()
    old_workspace_prefix = "VS Code" + "/1_Personal_Project"
    bad_workspace_path = (
        "/" + "Users" + "/yuyifeng/Documents/" + old_workspace_prefix + "/开源/sourceharbor"
    )

    errors = module._scan_text(
        f"cwd={bad_workspace_path}",
        rel_path="README.md",
    )

    assert len(errors) >= 1
    assert old_workspace_prefix in errors[0]


def test_scan_text_allows_controlled_contract_paths() -> None:
    module = _load_module()

    errors = module._scan_text(
        "standard image workdir is /workspace and temp outputs may use /tmp/sourceharbor-live-smoke-123",
        rel_path="docs/start-here.md",
    )

    assert errors == []


def test_scan_text_rejects_personal_email_domains() -> None:
    module = _load_module()
    personal_email = "sourceharbor-maintainer" + "@" + "gmail.com"

    errors = module._scan_text(
        f"contact {personal_email} privately",
        rel_path="CODE_OF_CONDUCT.md",
    )

    assert len(errors) == 1
    assert "forbidden personal-email reference" in errors[0]
    assert "so***" + "@" + "gmail.com" in errors[0]


def test_governance_gate_invokes_host_path_check() -> None:
    gate = (Path(__file__).resolve().parents[3] / "scripts" / "governance" / "gate.sh").read_text(
        encoding="utf-8"
    )

    assert "python3 scripts/governance/check_host_specific_path_references.py" in gate
