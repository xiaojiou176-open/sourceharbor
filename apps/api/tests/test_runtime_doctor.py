from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_doctor_module():
    root = Path(__file__).resolve().parents[3]
    module_path = root / "scripts" / "runtime" / "doctor.py"
    spec = importlib.util.spec_from_file_location("sourceharbor_runtime_doctor", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_evaluate_database_target_blocks_host_postgres_split_brain() -> None:
    module = _load_doctor_module()

    result = module.evaluate_database_target(
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/sourceharbor",
        "15432",
        True,
    )

    assert result.status == "BLOCK"
    assert "split-brain" in result.summary


def test_evaluate_database_target_accepts_container_first_local_port() -> None:
    module = _load_doctor_module()

    result = module.evaluate_database_target(
        "postgresql+psycopg://postgres:postgres@127.0.0.1:15432/sourceharbor",
        "15432",
        True,
    )

    assert result.status == "PASS"


def test_parse_status_output_extracts_service_states() -> None:
    module = _load_doctor_module()

    payload = module.parse_status_output(
        "api: running (pid 123)\n"
        "worker: stopped\n"
        "web: running (pid 456)\n"
        "mcp: interactive-only (run ./bin/dev-mcp manually)"
    )

    assert payload["api"].startswith("running")
    assert payload["worker"] == "stopped"
    assert payload["mcp"].startswith("interactive-only")


def test_make_secret_gate_reports_missing_sender_identity_separately() -> None:
    module = _load_doctor_module()

    result = module.make_secret_gate(
        "Notification sender identity",
        "RESEND_FROM_EMAIL",
        "Add RESEND_FROM_EMAIL only after you have a verified Resend sender/domain for real external notification delivery proof.",
    )

    assert result.status == "WARN"
    assert result.check_id == "resend_from_email"
    assert "RESEND_FROM_EMAIL is missing" in result.summary


def test_check_disk_governance_maps_ready_operator_summary_to_pass(monkeypatch) -> None:
    module = _load_doctor_module()
    monkeypatch.setattr(module, "load_policy", lambda _root: {"version": 1})
    monkeypatch.setattr(
        module,
        "build_disk_governance_operator_summary",
        lambda _root, _policy: {
            "status": "ready",
            "summary": "Repo-side duplicate runtime and known duplicate project envs are currently within the expected bounds.",
            "next_step": "None.",
            "details": {"repo_tmp_cleanup_ready": False, "duplicate_envs": []},
        },
    )

    result = module.check_disk_governance()

    assert result.status == "PASS"
    assert "duplicate runtime" in result.summary
    assert result.details["repo_tmp_cleanup_ready"] is False


def test_check_disk_governance_preserves_warn_details(monkeypatch) -> None:
    module = _load_doctor_module()
    monkeypatch.setattr(module, "load_policy", lambda _root: {"version": 1})
    monkeypatch.setattr(
        module,
        "build_disk_governance_operator_summary",
        lambda _root, _policy: {
            "status": "warn",
            "summary": "Repo-side web runtime duplicate is present, but repo-tmp cleanup is still gated.",
            "next_step": "Wait for the repo-tmp gates to clear.",
            "details": {
                "repo_tmp_cleanup_ready": False,
                "blocking_gates": [{"name": "quiet-window", "detail": "0.5m since latest change"}],
            },
        },
    )

    result = module.check_disk_governance()

    assert result.status == "WARN"
    assert result.details["blocking_gates"][0]["name"] == "quiet-window"


def test_check_disk_governance_warns_when_summary_loading_raises(monkeypatch) -> None:
    module = _load_doctor_module()
    monkeypatch.setattr(module, "load_policy", lambda _root: (_ for _ in ()).throw(OSError("boom")))

    result = module.check_disk_governance()

    assert result.status == "WARN"
    assert "could not be loaded cleanly" in result.summary
