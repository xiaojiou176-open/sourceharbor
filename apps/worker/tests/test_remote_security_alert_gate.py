from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "governance"
        / "check_remote_security_alerts.py"
    )
    spec = importlib.util.spec_from_file_location("remote_security_alert_gate_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_origin_repo_slug_parses_github_ssh_remote(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "git_output",
        lambda *args, **kwargs: "git@github.com:xiaojiou176-open/sourceharbor.git\n",
    )

    assert module._origin_repo_slug() == "xiaojiou176-open/sourceharbor"


def test_governance_gates_invoke_remote_security_alert_check() -> None:
    root = Path(__file__).resolve().parents[3]
    gate = (root / "scripts" / "governance" / "gate.sh").read_text(encoding="utf-8")
    quality_gate = (root / "scripts" / "governance" / "quality_gate.sh").read_text(encoding="utf-8")

    assert "python3 scripts/governance/check_remote_security_alerts.py" in gate
    assert "python3 scripts/governance/check_remote_security_alerts.py" in quality_gate
