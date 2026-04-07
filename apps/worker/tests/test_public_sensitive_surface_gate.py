from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "governance"
        / "check_public_sensitive_surface.py"
    )
    spec = importlib.util.spec_from_file_location("public_sensitive_surface_gate_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scan_text_rejects_sensitive_presence_wording() -> None:
    module = _load_module()

    errors = module._scan_text(
        "The current maintainer canary confirms RESEND_API_KEY is available in one controlled local environment.",
        rel_path="docs/project-status.md",
    )

    assert len(errors) == 1
    assert "forbidden secret-presence wording" in errors[0]


def test_scan_text_rejects_operator_secret_story_terms() -> None:
    module = _load_module()

    errors = module._scan_text(
        "Keep the validated provider configuration in the secure operator environment and update the secure operator credential flow.",
        rel_path="docs/proof.md",
    )

    assert len(errors) == 3
    assert any("validated provider configuration" in item for item in errors)
    assert any("secure operator environment" in item for item in errors)
    assert any("secure operator credential flow" in item for item in errors)


def test_scan_text_rejects_concrete_home_cache_path_fragments() -> None:
    module = _load_module()

    errors = module._scan_text(
        "Use ~/.cache/sourceharbor/browser/chrome-user-data/Profile 1 for local proof.",
        rel_path="docs/testing.md",
    )

    assert len(errors) == 3
    assert any(".cache/sourceharbor" in item for item in errors)
    assert any("chrome-user-data" in item for item in errors)
    assert any("Profile 1" in item for item in errors)


def test_scan_text_allows_generic_env_contract_wording() -> None:
    module = _load_module()

    errors = module._scan_text(
        "Use SOURCE_HARBOR_CHROME_USER_DATA_DIR and SOURCE_HARBOR_CHROME_PROFILE_DIR when the local proof lane needs a repo-owned browser root.",
        rel_path="docs/testing.md",
    )

    assert errors == []


def test_gate_and_quality_gate_invoke_public_sensitive_surface_check() -> None:
    root = Path(__file__).resolve().parents[3]
    gate = (root / "scripts" / "governance" / "gate.sh").read_text(encoding="utf-8")
    quality_gate = (root / "scripts" / "governance" / "quality_gate.sh").read_text(encoding="utf-8")

    assert "python3 scripts/governance/check_public_sensitive_surface.py" in gate
    assert "python3 scripts/governance/check_public_sensitive_surface.py" in quality_gate
