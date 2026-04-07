from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_script(
    tmp_path: Path, *, env: dict[str, str], args: list[str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_repo_root() / "scripts" / "runtime" / "maintain_external_cache.py"),
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(tmp_path / "policy.json"),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _write_policy(path: Path) -> None:
    payload = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "repo_runtime_root": ".runtime-cache",
            "user_state_root": "$HOME/.cache/sourceharbor",
            "user_cache_root": "$HOME/.cache/sourceharbor",
            "user_project_venv": "$HOME/.cache/sourceharbor/project-venv",
            "legacy_state_root": "$HOME/.video-digestor",
            "legacy_cache_root": "$HOME/.cache/video-digestor",
        },
        "legacy_extra_roots": ["$HOME/.sourceharbor"],
        "duplicate_env_policy": {
            "canonical_mainline_path": "$HOME/.cache/sourceharbor/project-venv",
            "duplicate_glob": "$HOME/.cache/sourceharbor/project-venv*",
            "reference_files": [".env"],
        },
        "migration_variables": [],
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "external_cache_maintenance": {
            "report_path": ".runtime-cache/reports/governance/external-cache-maintenance.json",
            "stamp_path": "$HOME/.cache/sourceharbor/maintenance/external-cache-maintenance-stamp.json",
            "auto_interval_minutes": 60,
            "groups": {
                "project-venv": {
                    "path": "$HOME/.cache/sourceharbor/project-venv",
                    "kind": "protected-mainline",
                    "max_total_size_mb": 1024,
                },
                "duplicate-envs": {
                    "path_glob": "$HOME/.cache/sourceharbor/project-venv-*",
                    "kind": "duplicate-env",
                    "ttl_days": 7,
                    "quiet_minutes": 10080,
                    "max_total_size_mb": 1024,
                },
            },
        },
        "excluded_paths": ["$HOME/.cache/sourceharbor/project-venv"],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_external_cache_maintenance_deletes_old_duplicate_env(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cache_root = home / ".cache" / "sourceharbor"
    canonical = cache_root / "project-venv"
    duplicate = cache_root / "project-venv-codex"
    canonical.mkdir(parents=True)
    duplicate.mkdir(parents=True)
    (canonical / "pyvenv.cfg").write_text("canonical", encoding="utf-8")
    (duplicate / "pyvenv.cfg").write_text("duplicate", encoding="utf-8")
    stale_ts = time.time() - 8 * 24 * 3600
    os.utime(duplicate, (stale_ts, stale_ts))
    os.utime(duplicate / "pyvenv.cfg", (stale_ts, stale_ts))
    (tmp_path / ".env").write_text(
        'export SOURCE_HARBOR_CACHE_ROOT="$HOME/.cache/sourceharbor"\n'
        'export UV_PROJECT_ENVIRONMENT="$HOME/.cache/sourceharbor/project-venv"\n',
        encoding="utf-8",
    )
    _write_policy(tmp_path / "policy.json")

    env = os.environ.copy()
    env["HOME"] = str(home)
    result = _run_script(tmp_path, env=env, args=["--apply", "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert not duplicate.exists()
    assert canonical.exists()
    actions = payload["actions"]
    assert any(
        item["path"].endswith("project-venv-codex") and item["status"] == "deleted"
        for item in actions
    )


def test_external_cache_maintenance_auto_mode_respects_stamp(tmp_path: Path) -> None:
    home = tmp_path / "home"
    maintenance_dir = home / ".cache" / "sourceharbor" / "maintenance"
    maintenance_dir.mkdir(parents=True)
    recent_run = datetime.now(UTC) - timedelta(minutes=10)
    (maintenance_dir / "external-cache-maintenance-stamp.json").write_text(
        json.dumps(
            {"last_run_at": recent_run.replace(microsecond=0).isoformat().replace("+00:00", "Z")},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("", encoding="utf-8")
    _write_policy(tmp_path / "policy.json")

    env = os.environ.copy()
    env["HOME"] = str(home)
    result = _run_script(tmp_path, env=env, args=["--auto", "--apply"])

    assert result.returncode == 0, result.stderr
    assert "[external-cache-maintenance] SKIP" in result.stdout
