from __future__ import annotations

import builtins
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "release" / "generate_release_prechecks.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_prechecks(tmp_path: Path, *extra_args: str) -> dict[str, object]:
    output_path = tmp_path / "prechecks.json"
    cmd = [
        sys.executable,
        str(_script_path()),
        "--repo-root",
        str(_repo_root()),
        "--output",
        str(output_path),
        *extra_args,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return json.loads(output_path.read_text(encoding="utf-8"))


def test_release_prechecks_include_observability_checks_by_default(tmp_path: Path) -> None:
    payload = _run_prechecks(tmp_path)
    checks = payload.get("checks")
    assert isinstance(checks, list)

    checks_by_name = {item["name"]: item for item in checks if isinstance(item, dict)}
    assert "api_red_metrics_minimum" in checks_by_name
    assert "api_trace_header_echo" in checks_by_name
    assert "slo_thresholds_documented" in checks_by_name

    assert checks_by_name["api_red_metrics_minimum"]["required"] is True
    assert checks_by_name["api_trace_header_echo"]["required"] is True
    assert checks_by_name["slo_thresholds_documented"]["required"] is True


def test_release_prechecks_can_skip_runtime_observability_checks(tmp_path: Path) -> None:
    payload = _run_prechecks(tmp_path, "--skip-observability-checks")
    checks = payload.get("checks")
    assert isinstance(checks, list)

    check_names = {item["name"] for item in checks if isinstance(item, dict)}
    assert "api_red_metrics_minimum" not in check_names
    assert "api_trace_header_echo" not in check_names
    assert "slo_thresholds_documented" in check_names


def test_observability_fallback_uses_isolated_uv_python3(
    monkeypatch,  # noqa: ANN001
) -> None:
    module = _load_module(_script_path(), "generate_release_prechecks_uv_fallback_test")
    original_import = builtins.__import__
    recorded: dict[str, object] = {}

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: ANN001
        if name in {"fastapi.testclient", "apps.api.app.main"}:
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    def fake_run(cmd, **kwargs):  # noqa: ANN001
        recorded["cmd"] = cmd
        recorded["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=json.dumps(
                {
                    "red": True,
                    "trace": True,
                    "metrics_status": 200,
                    "trace_status": 200,
                    "trace_echo": "release-trace-0001",
                }
            )
            + "\n",
            stderr="",
        )

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(module.subprocess, "run", fake_run)

    checks = module._build_observability_checks(_repo_root())

    checks_by_name = {item["name"]: item for item in checks if isinstance(item, dict)}
    assert checks_by_name["api_red_metrics_minimum"]["status"] == "pass"
    assert checks_by_name["api_trace_header_echo"]["status"] == "pass"
    assert recorded["cmd"][:5] == ["uv", "run", "--isolated", "python3", "-c"]
    assert isinstance(recorded["cmd"][5], str)
    assert recorded["cwd"] == _repo_root()


def test_resolve_release_tag_prefers_explicit_override() -> None:
    module = _load_module(_script_path(), "generate_release_prechecks_override_test")

    resolved, source = module._resolve_release_tag("v0.1.4", "v0.1.3")

    assert resolved == "v0.1.4"
    assert source == "input"


def test_pick_release_evidence_dir_does_not_fallback_when_explicit_tag_dir_is_missing(
    tmp_path: Path,
) -> None:
    module = _load_module(_script_path(), "generate_release_prechecks_release_dir_test")
    releases_root = tmp_path / "artifacts" / "releases"
    (releases_root / "v0.1.3").mkdir(parents=True)

    picked = module._pick_release_evidence_dir(tmp_path, "v0.1.4")

    assert picked == releases_root / "v0.1.4"


def test_validate_rum_baseline_accepts_zero_cls(tmp_path: Path) -> None:
    module = _load_module(_script_path(), "generate_release_prechecks_test")
    rum_path = tmp_path / "rum-baseline.json"
    rum_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "lcp_ms_p75": 388.0,
                    "inp_ms_p75": 24.0,
                    "cls_p75": 0.0,
                    "sample_size": 5,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    ok, evidence, values = module._validate_rum_baseline(rum_path)

    assert ok is True
    assert "cls_p75=0.0" in evidence
    assert values == {"lcp_ms_p75": 388.0, "inp_ms_p75": 24.0, "cls_p75": 0.0}


def test_verify_db_rollback_readiness_rejects_pending_drill_template(tmp_path: Path) -> None:
    module = _load_module(
        _repo_root() / "scripts" / "release" / "verify_db_rollback_readiness.py",
        "verify_db_rollback_readiness_test",
    )
    drill_path = tmp_path / "drill.json"
    drill_path.write_text(
        json.dumps(
            {
                "release_tag": "v-test",
                "executed_at": "",
                "executor": "",
                "strategy": "sql_down_or_n_minus_1_restore",
                "result": "pending",
                "migrations_checked": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    valid, errors = module._validate_drill_evidence(drill_path)

    assert valid is False
    assert "executed_at must be non-empty" in errors
    assert "executor must be non-empty" in errors
    assert "result must not be `pending`" in errors
    assert "migrations_checked must record at least one migration" in errors


def test_release_attest_readiness_evaluator_rejects_failed_required_prechecks(
    tmp_path: Path,
) -> None:
    module = _load_module(
        _repo_root() / "scripts" / "release" / "check_release_evidence_attest_readiness.py",
        "check_release_evidence_attest_readiness_test",
    )
    release_dir = tmp_path / "artifacts" / "releases" / "v-test"
    rollback_dir = release_dir / "rollback"
    rollback_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (release_dir / "checksums.sha256").write_text("abc  manifest.json\n", encoding="utf-8")
    (rollback_dir / "db-rollback-readiness.json").write_text(
        json.dumps(
            {
                "summary": {"gate_status": "pass"},
                "drill_evidence": {"valid": True, "errors": []},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (rollback_dir / "drill.json").write_text(
        json.dumps(
            {
                "release_tag": "v-test",
                "executed_at": "2026-03-26T12:00:00Z",
                "executor": "operator",
                "strategy": "sql_down_or_n_minus_1_restore",
                "result": "success",
                "migrations_checked": ["20260308_000016_content_type.sql"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    prechecks_path = (
        tmp_path / ".runtime-cache" / "reports" / "release-readiness" / "prechecks.json"
    )
    prechecks_path.parent.mkdir(parents=True)
    prechecks_path.write_text(
        json.dumps(
            {
                "checks": [
                    {"name": "release_tag_resolved", "required": True, "status": "pass"},
                    {
                        "name": "db_rollback_drill_evidence_present",
                        "required": True,
                        "status": "fail",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    state, errors = module._evaluate_release_readiness(release_dir, prechecks_path)

    assert state["rollback_gate_status"] == "pass"
    assert state["rollback_drill_valid"] is True
    assert state["failed_required_prechecks"] == ["db_rollback_drill_evidence_present"]
    assert errors == ["required release prechecks failing: db_rollback_drill_evidence_present"]
