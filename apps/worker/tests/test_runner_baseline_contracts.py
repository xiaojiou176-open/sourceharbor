from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "governance" / "check_runner_baseline.py"
    spec = importlib.util.spec_from_file_location("check_runner_baseline", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_profile_rejects_low_free_space(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    baseline = {
        "profiles": {
            "ci-heavy": {
                "commands": ["bash"],
                "docker_compose_required": False,
                "disk_budget_gb": {
                    "min_free_gb_tmp": 8,
                    "min_free_gb_workspace": 8,
                },
                "purge_paths": [".runtime-cache", "mutants/"],
            }
        }
    }

    monkeypatch.setattr(module, "command_exists", lambda name: True)
    monkeypatch.setattr(
        module.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=100, used=95, free=2 * 1024**3),
    )

    failures, details = module.validate_profile("ci-heavy", baseline, workspace=tmp_path)

    assert any("insufficient free space" in item for item in failures)
    assert any("suggested purge paths" in item for item in details)


def test_validate_profile_reports_disk_details_on_success(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    baseline = {
        "profiles": {
            "preflight-fast": {
                "commands": ["bash", "python3"],
                "docker_compose_required": False,
                "disk_budget_gb": {
                    "min_free_gb_tmp": 1,
                    "min_free_gb_workspace": 1,
                },
            }
        }
    }

    monkeypatch.setattr(module, "command_exists", lambda name: True)
    monkeypatch.setattr(
        module.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(total=100, used=20, free=20 * 1024**3),
    )

    failures, details = module.validate_profile("preflight-fast", baseline, workspace=tmp_path)

    assert failures == []
    assert any(item.startswith("tmp free:") for item in details)
    assert any(item.startswith("workspace free:") for item in details)
