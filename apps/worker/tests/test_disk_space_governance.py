from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_script(
    script_name: str,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, str(_repo_root() / "scripts" / "runtime" / script_name), *(args or [])],
        cwd=cwd,
        env=merged_env,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_runtime_module(module_name: str):
    module_path = _repo_root() / "scripts" / "runtime" / module_name
    spec = importlib.util.spec_from_file_location(
        f"test_{module_name.replace('.', '_')}", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_policy(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _checker_path() -> Path:
    return _repo_root() / "scripts" / "governance" / "check_disk_space_governance.py"


def _audit_checker_path() -> Path:
    return _repo_root() / "scripts" / "governance" / "check_disk_space_audit_report.py"


def _run_checker(tmp_path: Path, *, policy_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_checker_path()),
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_audit_checker(
    tmp_path: Path, *, policy_path: Path, report_path: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_audit_checker_path()),
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--report",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _required_migration_variables() -> list[dict]:
    return [
        {
            "name": "PIPELINE_ARTIFACT_ROOT",
            "canonical_path": "$HOME/.sourceharbor/artifacts",
            "path_kind": "directory",
            "ownership": "repo-primary",
            "allow_existing_target": False,
            "retire_source_on_migrate": True,
        },
        {
            "name": "PIPELINE_WORKSPACE_DIR",
            "canonical_path": "$HOME/.sourceharbor/workspace",
            "path_kind": "directory",
            "ownership": "repo-primary",
            "allow_existing_target": False,
            "retire_source_on_migrate": True,
        },
        {
            "name": "SQLITE_PATH",
            "canonical_path": "$HOME/.sourceharbor/state/worker_state.db",
            "path_kind": "file",
            "ownership": "repo-primary",
            "allow_existing_target": False,
            "retire_source_on_migrate": True,
        },
        {
            "name": "SQLITE_STATE_PATH",
            "canonical_path": "$HOME/.sourceharbor/state/api_state.db",
            "path_kind": "file",
            "ownership": "repo-primary",
            "allow_existing_target": False,
            "retire_source_on_migrate": True,
        },
        {
            "name": "UV_PROJECT_ENVIRONMENT",
            "canonical_path": "$HOME/.cache/sourceharbor/project-venv",
            "path_kind": "directory",
            "ownership": "repo-primary",
            "allow_existing_target": True,
            "existing_target_verify_command": [
                "bash",
                "-lc",
                'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
            ],
            "retire_source_on_migrate": False,
        },
    ]


def _minimal_checker_policy() -> dict:
    return {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {},
        "duplicate_env_policy": {
            "canonical_mainline_path": "$HOME/.cache/sourceharbor/project-venv",
            "duplicate_glob": "$HOME/.cache/sourceharbor/project-venv*",
            "reference_files": [
                ".env",
                ".env.example",
                "scripts/lib/standard_env.sh",
                "infra/systemd/sourceharbor-api.service",
                "infra/systemd/sourceharbor-worker.service",
            ],
        },
        "migration_variables": _required_migration_variables(),
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }


def test_report_disk_space_classifies_layers_and_keeps_docker_unverified(tmp_path: Path) -> None:
    (tmp_path / ".runtime-cache" / "tmp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "tmp" / "sample.txt").write_text("x" * 32, encoding="utf-8")
    external_owned = tmp_path / "external-owned"
    shared_root = tmp_path / "shared-cache"
    external_owned.mkdir()
    shared_root.mkdir()
    (external_owned / "owned.bin").write_bytes(b"a" * 64)
    (shared_root / "shared.bin").write_bytes(b"b" * 128)
    (tmp_path / ".env").write_text(
        "export PIPELINE_WORKSPACE_DIR='$HOME/.video-digestor/workspace'\n"
    )

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\necho 'daemon unavailable' >&2\nexit 1\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {
            "legacy_state_root": "$HOME/.video-digestor",
            "legacy_cache_root": "$HOME/.cache/video-digestor",
        },
        "legacy_reference_files": [".env"],
        "audit_targets": [
            {
                "id": "repo-root",
                "label": "Repo root",
                "path": ".",
                "layer": "repo-internal",
                "ownership": "repo-exclusive",
                "category": "repo-root",
                "count_in_layer_total": True,
            },
            {
                "id": "repo-hotspot",
                "label": "Repo tmp",
                "path": ".runtime-cache/tmp",
                "layer": "repo-internal",
                "ownership": "repo-exclusive",
                "category": "runtime",
            },
            {
                "id": "external-owned",
                "label": "External owned",
                "path": "external-owned",
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "external",
                "count_in_layer_total": True,
            },
            {
                "id": "shared-root",
                "label": "Shared cache",
                "path": "shared-cache",
                "layer": "shared-layer",
                "ownership": "shared",
                "category": "shared",
                "count_in_layer_total": True,
            },
        ],
        "docker_named_volumes": ["sourceharbor_core_postgres_data"],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["totals"]["repo-internal"]["size_bytes"] > 0
    assert payload["totals"]["repo-external-repo-owned"]["size_bytes"] == 64
    assert payload["totals"]["shared-layer"]["size_bytes"] == 128
    assert payload["totals"]["unverified-layer"]["size_bytes"] is None
    assert payload["legacy_compatibility"]["active_markers_detected"] is True
    assert payload["legacy_compatibility"]["legacy_retirement_blocked"] is True
    assert payload["governance"]["legacy_default_write_drift"]["detected"] is False


def test_report_disk_space_counts_present_docker_volume_into_repo_external_total(
    tmp_path: Path,
) -> None:
    mountpoint = tmp_path / "docker-volumes" / "sourceharbor_core_postgres_data"
    mountpoint.mkdir(parents=True, exist_ok=True)
    (mountpoint / "data.bin").write_bytes(b"x" * 256)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [[ "$1" == "info" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "volume" && "$2" == "inspect" && "$3" == "sourceharbor_core_postgres_data" ]]; then\n'
        f'  printf \'[{{"Name":"sourceharbor_core_postgres_data","Mountpoint":"{mountpoint}"}}]\\n\'\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "volume" && "$2" == "inspect" && "$3" == "miniflux_db_data" ]]; then\n'
        "  exit 1\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [
            {
                "id": "external-owned",
                "label": "External owned",
                "path": "external-owned",
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "external",
                "count_in_layer_total": True,
            }
        ],
        "docker_named_volumes": ["sourceharbor_core_postgres_data", "miniflux_db_data"],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    external_owned = tmp_path / "external-owned"
    external_owned.mkdir()
    (external_owned / "owned.bin").write_bytes(b"a" * 64)
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["docker"]["status"] == "ok"
    assert payload["docker"]["volumes"][0]["status"] == "present"
    assert payload["docker"]["volumes"][1]["status"] == "missing"
    assert payload["totals"]["repo-external-repo-owned"]["size_bytes"] == 320
    assert payload["totals"]["confirmed_total"]["size_bytes"] == 320
    assert payload["totals"]["unverified-layer"]["size_bytes"] == 0


def test_report_disk_space_counts_user_state_root_without_double_counting_child_highlights(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "sourceharbor-state"
    artifacts = state_root / "artifacts"
    workspace = state_root / "workspace"
    sqlite_state = state_root / "state"
    artifacts.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    sqlite_state.mkdir(parents=True, exist_ok=True)
    (artifacts / "artifact.bin").write_bytes(b"a" * 16)
    (workspace / "job.txt").write_text("workspace", encoding="utf-8")
    (sqlite_state / "worker.db").write_bytes(b"sqlite" * 3)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {
            "user_state_root": str(state_root),
        },
        "legacy_reference_files": [],
        "audit_targets": [
            {
                "id": "user-state-root",
                "label": "User state root",
                "path": str(state_root),
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "external-state",
                "count_in_layer_total": True,
                "highlight": True,
            },
            {
                "id": "user-state-artifacts",
                "label": "User state artifacts",
                "path": str(artifacts),
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "protected-state",
                "highlight": True,
            },
            {
                "id": "user-state-workspace",
                "label": "User state workspace",
                "path": str(workspace),
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "protected-state",
                "highlight": True,
            },
            {
                "id": "user-state-sqlite",
                "label": "User state sqlite",
                "path": str(sqlite_state),
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "protected-state",
                "highlight": True,
            },
        ],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    expected_total = 16 + len("workspace") + (len(b"sqlite") * 3)
    assert payload["totals"]["repo-external-repo-owned"]["size_bytes"] == expected_total
    highlight_paths = {item["path"] for item in payload["highlights"]}
    assert "sourceharbor-state" in highlight_paths
    assert "sourceharbor-state/artifacts" in highlight_paths
    assert "sourceharbor-state/workspace" in highlight_paths
    assert "sourceharbor-state/state" in highlight_paths


def test_report_disk_space_emits_duplicate_env_groups_without_counting_canonical_as_duplicate(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache-root"
    canonical_env = cache_root / "project-venv"
    duplicate_env = cache_root / "project-venv-codex"
    canonical_env.mkdir(parents=True, exist_ok=True)
    duplicate_env.mkdir(parents=True, exist_ok=True)
    (canonical_env / "canonical.bin").write_bytes(b"c" * 8)
    (duplicate_env / "duplicate.bin").write_bytes(b"d" * 12)
    (tmp_path / ".env.example").write_text(
        f'export UV_PROJECT_ENVIRONMENT="{canonical_env}"\n',
        encoding="utf-8",
    )

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "duplicate_env_policy": {
            "canonical_mainline_path": "cache-root/project-venv",
            "duplicate_glob": "cache-root/project-venv*",
            "reference_files": [".env.example"],
        },
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    duplicate_envs = payload["governance"]["repo_external_duplicate_envs"]
    assert duplicate_envs["total_duplicate_size_bytes"] == 12
    group = duplicate_envs["groups"][0]
    assert group["status"] == "duplicates-detected"
    canonical_entry = next(item for item in group["entries"] if item["is_canonical"])
    duplicate_entry = next(item for item in group["entries"] if not item["is_canonical"])
    assert canonical_entry["reference_status"] == "canonical-mainline"
    assert duplicate_entry["reference_status"] == "unreferenced-by-known-entrypoints"


def test_report_disk_space_marks_duplicate_env_as_still_referenced_when_entrypoint_mentions_it(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache-root"
    canonical_env = cache_root / "project-venv"
    duplicate_env = cache_root / "project-venv-codex"
    canonical_env.mkdir(parents=True, exist_ok=True)
    duplicate_env.mkdir(parents=True, exist_ok=True)
    (duplicate_env / "duplicate.bin").write_bytes(b"d" * 12)
    (tmp_path / ".env").write_text(
        f'export UV_PROJECT_ENVIRONMENT="{duplicate_env}"\n',
        encoding="utf-8",
    )

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "duplicate_env_policy": {
            "canonical_mainline_path": "cache-root/project-venv",
            "duplicate_glob": "cache-root/project-venv*",
            "reference_files": [".env"],
        },
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    group = payload["governance"]["repo_external_duplicate_envs"]["groups"][0]
    duplicate_entry = next(item for item in group["entries"] if not item["is_canonical"])
    assert duplicate_entry["reference_status"] == "still-referenced"
    assert duplicate_entry["reference_hits"] == [".env"]


def test_operator_summary_warns_when_duplicate_envs_exist_without_repo_web_runtime(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache-root"
    canonical_env = cache_root / "project-venv"
    duplicate_env = cache_root / "project-venv-codex"
    canonical_env.mkdir(parents=True, exist_ok=True)
    duplicate_env.mkdir(parents=True, exist_ok=True)
    (duplicate_env / "duplicate.bin").write_bytes(b"d" * 12)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "duplicate_env_policy": {
            "canonical_mainline_path": "cache-root/project-venv",
            "duplicate_glob": "cache-root/project-venv*",
            "reference_files": [],
        },
        "legacy_reference_files": [],
        "audit_targets": [
            {
                "id": "repo-web-runtime",
                "label": "Repo web runtime workspace",
                "path": ".runtime-cache/tmp/web-runtime",
                "layer": "repo-internal",
                "ownership": "repo-exclusive",
                "category": "runtime-duplicate",
            }
        ],
        "docker_named_volumes": [],
        "cleanup_waves": {"repo-tmp": {"candidates": []}},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)
    report_module = _load_runtime_module("report_disk_space.py")
    policy_payload = report_module.load_policy(tmp_path, str(policy_path))

    summary = report_module.build_disk_governance_operator_summary(tmp_path, policy_payload)

    assert summary["status"] == "warn"
    assert "duplicate project envs" in summary["summary"]
    assert summary["details"]["duplicate_env_count"] == 1


def test_report_disk_space_emits_repo_internal_residue_buckets(tmp_path: Path) -> None:
    proof_dir = tmp_path / ".runtime-cache" / "tmp" / "manual-image-audit"
    log_dir = tmp_path / ".runtime-cache" / "logs" / "app"
    ai_ledger_dir = tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers"
    ledger_dir = tmp_path / ".agents" / "Plans"
    release_dir = tmp_path / "artifacts" / "releases"
    orphan_dir = tmp_path / "apps" / "web" / "node_modules.broken.20260327-0755"
    proof_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    ai_ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    release_dir.mkdir(parents=True, exist_ok=True)
    orphan_dir.mkdir(parents=True, exist_ok=True)
    (proof_dir / "proof.png").write_bytes(b"p" * 11)
    (log_dir / "api.jsonl").write_bytes(b"l" * 13)
    (ai_ledger_dir / "current-ledger.md").write_text("authoritative", encoding="utf-8")
    (ledger_dir / "plan.md").write_text("plan", encoding="utf-8")
    (release_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (orphan_dir / "index.js").write_text("broken", encoding="utf-8")

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    residue = payload["governance"]["repo_internal_residue"]
    assert residue["proof_scratch"]["size_bytes"] == 11
    assert residue["active_logs"]["size_bytes"] == 13
    assert residue["local_private_ledgers"]["size_bytes"] == len("authoritative") + len("plan")
    assert residue["tracked_release_evidence"]["size_bytes"] == len("{}")
    assert residue["orphan_residue"]["size_bytes"] == len("broken")
    assert residue["orphan_residue"]["paths"][0]["path"].endswith(
        "node_modules.broken.20260327-0755"
    )
    local_private_paths = {item["path"] for item in residue["local_private_ledgers"]["paths"]}
    assert ".runtime-cache/evidence/ai-ledgers" in local_private_paths
    assert ".agents" in local_private_paths


def test_cleanup_disk_space_safe_wave_dry_run_preserves_files(tmp_path: Path) -> None:
    pycache_dir = tmp_path / "pkg" / "__pycache__"
    pycache_dir.mkdir(parents=True)
    (pycache_dir / "module.pyc").write_bytes(b"x")

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "safe": {
                "candidates": [
                    {
                        "id": "pycache",
                        "path_glob": "**/__pycache__",
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "safe-clear",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "safe",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["safe_clear_bytes"] > 0
    assert payload["verify_first_bytes"] == 0
    assert "release_potential_bytes" not in payload
    assert pycache_dir.exists()


def test_cleanup_disk_space_reports_bucketed_totals_and_protected_entries(tmp_path: Path) -> None:
    safe_dir = tmp_path / ".runtime-cache" / "tmp" / "pytest-cache"
    safe_dir.mkdir(parents=True, exist_ok=True)
    (safe_dir / "index.bin").write_bytes(b"s" * 9)
    verify_dir = tmp_path / "legacy-cache" / "closure-fix-venv"
    verify_dir.mkdir(parents=True, exist_ok=True)
    (verify_dir / "venv.bin").write_bytes(b"v" * 12)
    canonical_env = tmp_path / "canonical-cache" / "project-venv"
    canonical_env.mkdir(parents=True, exist_ok=True)
    protected_root = tmp_path / "current-state"
    protected_root.mkdir(parents=True, exist_ok=True)
    (protected_root / "state.bin").write_bytes(b"p" * 20)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [str(protected_root)],
        "cleanup_waves": {
            "safe": {
                "candidates": [
                    {
                        "id": "runtime-pytest-cache",
                        "path": ".runtime-cache/tmp/pytest-cache",
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "safe-clear",
                    }
                ]
            },
            "external-history": {
                "candidates": [
                    {
                        "id": "closure-fix-venv",
                        "path": "legacy-cache/closure-fix-venv",
                        "quiet_minutes": 0,
                        "reference_markers": ["closure-fix-venv"],
                        "equivalent_paths": ["canonical-cache/project-venv"],
                        "verify_command": ["bash", "-lc", "test -d canonical-cache/project-venv"],
                        "layer": "repo-external-repo-owned",
                        "ownership": "repo-primary",
                        "classification": "verify-first",
                    }
                ]
            },
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["safe_clear_bytes"] == 9
    assert payload["verify_first_bytes"] == 12
    assert payload["protected_bytes"] == 20
    assert payload["classification_totals"]["safe-clear"]["size_bytes"] == 9
    assert payload["classification_totals"]["verify-first"]["size_bytes"] == 12
    assert payload["protected_entries"][0]["path"] == str(protected_root.resolve())
    assert "release_potential_bytes" not in payload


def test_cleanup_disk_space_repo_tmp_apply_requires_gates_and_rebuild(tmp_path: Path) -> None:
    candidate = tmp_path / ".runtime-cache" / "tmp" / "web-runtime"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "artifact.bin").write_bytes(b"x" * 16)

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    lsof = fake_bin / "lsof"
    lsof.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    lsof.chmod(0o755)

    rebuild_script = tmp_path / "rebuild.sh"
    rebuild_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "mkdir -p .runtime-cache/tmp/web-runtime\n"
        "printf 'rebuilt\\n' > .runtime-cache/tmp/web-runtime/rebuilt.txt\n",
        encoding="utf-8",
    )
    rebuild_script.chmod(0o755)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "repo-tmp": {
                "candidates": [
                    {
                        "id": "web-runtime",
                        "path": ".runtime-cache/tmp/web-runtime",
                        "quiet_minutes": 0,
                        "lock_markers": ["*.pid", "*.lock"],
                        "requires_lsof_clear": True,
                        "rebuild_command": ["bash", str(rebuild_script)],
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "cautious-clear",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "repo-tmp",
            "--apply",
            "--yes",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "apply"
    assert (candidate / "rebuilt.txt").is_file()
    assert payload["actions"][0]["status"] == "applied"


def test_cleanup_disk_space_repo_tmp_respects_quiet_window(tmp_path: Path) -> None:
    candidate = tmp_path / ".runtime-cache" / "tmp" / "web-runtime"
    candidate.mkdir(parents=True, exist_ok=True)
    artifact = candidate / "artifact.bin"
    artifact.write_bytes(b"x" * 16)
    now = time.time()
    os.utime(artifact, (now, now))

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "repo-tmp": {
                "candidates": [
                    {
                        "id": "web-runtime",
                        "path": ".runtime-cache/tmp/web-runtime",
                        "quiet_minutes": 10,
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "cautious-clear",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "repo-tmp",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["eligible"] is False
    gate_map = {gate["name"]: gate for gate in payload["candidates"][0]["gates"]}
    assert gate_map["quiet-window"]["ok"] is False


def test_cleanup_disk_space_repo_tmp_respects_lock_paths(tmp_path: Path) -> None:
    candidate = tmp_path / ".runtime-cache" / "tmp" / "web-runtime"
    candidate.mkdir(parents=True, exist_ok=True)
    lock_dir = tmp_path / ".runtime-cache" / "run" / "web-runtime" / ".prepare-lock"
    lock_dir.mkdir(parents=True, exist_ok=True)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "repo-tmp": {
                "candidates": [
                    {
                        "id": "web-runtime",
                        "path": ".runtime-cache/tmp/web-runtime",
                        "quiet_minutes": 0,
                        "lock_paths": [".runtime-cache/run/web-runtime/.prepare-lock"],
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "cautious-clear",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "repo-tmp",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["eligible"] is False
    gate_map = {gate["name"]: gate for gate in payload["candidates"][0]["gates"]}
    assert gate_map["lock-paths"]["ok"] is False


def test_cleanup_disk_space_repo_tmp_respects_busy_lsof(tmp_path: Path) -> None:
    candidate = tmp_path / ".runtime-cache" / "tmp" / "web-runtime"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "artifact.bin").write_bytes(b"x")

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    lsof = fake_bin / "lsof"
    lsof.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\\n'\n"
        "printf 'python 123 user txt REG 0,1 0 0 busy-file\\n'\n",
        encoding="utf-8",
    )
    lsof.chmod(0o755)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "repo-tmp": {
                "candidates": [
                    {
                        "id": "web-runtime",
                        "path": ".runtime-cache/tmp/web-runtime",
                        "quiet_minutes": 0,
                        "requires_lsof_clear": True,
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "cautious-clear",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        env={"PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "repo-tmp",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["eligible"] is False
    gate_map = {gate["name"]: gate for gate in payload["candidates"][0]["gates"]}
    assert gate_map["lsof-clear"]["ok"] is False


def test_cleanup_disk_space_apply_requires_yes_and_explicit_wave(tmp_path: Path) -> None:
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {"safe": {"candidates": []}},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    missing_yes = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "safe",
            "--apply",
        ],
    )
    missing_wave = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--apply", "--yes"],
    )

    assert missing_yes.returncode != 0
    assert "--apply requires --yes" in missing_yes.stderr
    assert missing_wave.returncode != 0
    assert "--apply requires at least one explicit --wave" in missing_wave.stderr


def test_cleanup_disk_space_external_history_blocks_when_referenced(tmp_path: Path) -> None:
    candidate = tmp_path / "legacy-cache" / "closure-fix-venv"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "venv.bin").write_bytes(b"x")
    (tmp_path / ".env").write_text(
        "export UV_PROJECT_ENVIRONMENT='closure-fix-venv'\n", encoding="utf-8"
    )
    equivalent = tmp_path / "canonical-cache" / "project-venv"
    equivalent.mkdir(parents=True, exist_ok=True)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "external-history": {
                "candidates": [
                    {
                        "id": "closure-fix-venv",
                        "path": "legacy-cache/closure-fix-venv",
                        "quiet_minutes": 0,
                        "reference_markers": ["closure-fix-venv"],
                        "equivalent_paths": ["canonical-cache/project-venv"],
                        "verify_command": ["bash", "-lc", "test -d canonical-cache/project-venv"],
                        "layer": "repo-external-repo-owned",
                        "ownership": "repo-primary",
                        "classification": "verify-first",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "external-history",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["eligible"] is False
    gate_names = {gate["name"] for gate in payload["candidates"][0]["gates"]}
    assert "reference-clear" in gate_names


def test_cleanup_disk_space_external_history_blocks_when_legacy_compatibility_active(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "legacy-cache" / "root-venv-backup"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "venv.bin").write_bytes(b"x")
    (tmp_path / ".env").write_text(
        'export PIPELINE_WORKSPACE_DIR="$HOME/.video-digestor/workspace"\n',
        encoding="utf-8",
    )
    equivalent = tmp_path / "canonical-cache" / "project-venv"
    equivalent.mkdir(parents=True, exist_ok=True)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "legacy_state_root": "$HOME/.video-digestor",
            "legacy_cache_root": "$HOME/.cache/video-digestor",
        },
        "migration_variables": [
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": "canonical-state/workspace",
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            }
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "external-history": {
                "candidates": [
                    {
                        "id": "root-venv-backup",
                        "path": "legacy-cache/root-venv-backup",
                        "quiet_minutes": 0,
                        "reference_markers": ["root-venv-backup"],
                        "equivalent_paths": ["canonical-cache/project-venv"],
                        "layer": "repo-external-repo-owned",
                        "ownership": "repo-primary",
                        "classification": "verify-first",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "external-history",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["candidates"][0]["eligible"] is False
    gate_map = {gate["name"]: gate for gate in payload["candidates"][0]["gates"]}
    assert gate_map["legacy-retired"]["ok"] is False


def test_legacy_disk_migration_dry_run_reports_legacy_retirement_blocked(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy-state"
    cache_root = tmp_path / "legacy-cache"
    (legacy_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (cache_root / "project-venv").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f'export PIPELINE_ARTIFACT_ROOT="{legacy_root / "artifacts"}"',
                f'export PIPELINE_WORKSPACE_DIR="{legacy_root / "workspace"}"',
                f'export SQLITE_PATH="{legacy_root / "state.db"}"',
                f'export SQLITE_STATE_PATH="{legacy_root / "state.db"}"',
                f'export UV_PROJECT_ENVIRONMENT="{cache_root / "project-venv"}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(tmp_path / "canonical-state"),
            "user_cache_root": str(tmp_path / "canonical-cache"),
            "legacy_state_root": str(legacy_root),
            "legacy_cache_root": str(cache_root),
        },
        "migration_variables": [
            {
                "name": "PIPELINE_ARTIFACT_ROOT",
                "canonical_path": str(tmp_path / "canonical-state" / "artifacts"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": str(tmp_path / "canonical-state" / "workspace"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_PATH",
                "canonical_path": str(tmp_path / "canonical-state" / "worker.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_STATE_PATH",
                "canonical_path": str(tmp_path / "canonical-state" / "api.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "UV_PROJECT_ENVIRONMENT",
                "canonical_path": str(tmp_path / "canonical-cache" / "project-venv"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": True,
                "existing_target_verify_command": [
                    "bash",
                    "-lc",
                    'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
                ],
                "retire_source_on_migrate": False,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["legacy_compatibility"]["legacy_retirement_blocked"] is True
    assert payload["variables"][0]["recommended_action"] in {"move", "copy", "env-only"}


def test_legacy_disk_migration_apply_updates_env_and_refreshes_audit(tmp_path: Path) -> None:
    legacy_state = tmp_path / "legacy-state"
    legacy_cache = tmp_path / "legacy-cache"
    canonical_state = tmp_path / "canonical-state"
    canonical_cache = tmp_path / "canonical-cache"
    artifacts = legacy_state / "artifacts"
    workspace = legacy_state / "workspace"
    state_db = legacy_state / "worker-state.db"
    api_state_db = legacy_state / "api-state.db"
    project_venv = legacy_cache / "project-venv"
    artifacts.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    project_venv.mkdir(parents=True, exist_ok=True)
    healthy_target = canonical_cache / "project-venv"
    (healthy_target / "bin").mkdir(parents=True, exist_ok=True)
    python_stub = healthy_target / "bin" / "python"
    python_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python_stub.chmod(0o755)
    (artifacts / "artifact.bin").write_bytes(b"a" * 16)
    (workspace / "job.txt").write_text("job", encoding="utf-8")
    state_db.parent.mkdir(parents=True, exist_ok=True)
    state_db.write_bytes(b"sqlite")
    api_state_db.write_bytes(b"sqlite-api")
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f'export PIPELINE_ARTIFACT_ROOT="{artifacts}"',
                f'export PIPELINE_WORKSPACE_DIR="{workspace}"',
                f'export SQLITE_PATH="{state_db}"',
                f'export SQLITE_STATE_PATH="{api_state_db}"',
                f'export UV_PROJECT_ENVIRONMENT="{project_venv}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(canonical_state),
            "user_cache_root": str(canonical_cache),
            "legacy_state_root": str(legacy_state),
            "legacy_cache_root": str(legacy_cache),
        },
        "migration_variables": [
            {
                "name": "PIPELINE_ARTIFACT_ROOT",
                "canonical_path": str(canonical_state / "artifacts"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": str(canonical_state / "workspace"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_PATH",
                "canonical_path": str(canonical_state / "worker_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_STATE_PATH",
                "canonical_path": str(canonical_state / "api_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "UV_PROJECT_ENVIRONMENT",
                "canonical_path": str(canonical_cache / "project-venv"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": True,
                "existing_target_verify_command": [
                    "bash",
                    "-lc",
                    'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
                ],
                "retire_source_on_migrate": False,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [
            {
                "id": "legacy-state-root",
                "label": "Legacy state root",
                "path": str(legacy_state),
                "layer": "repo-external-repo-owned",
                "ownership": "repo-primary",
                "category": "legacy-compatible",
                "count_in_layer_total": True,
            }
        ],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--mapping",
            f"PIPELINE_ARTIFACT_ROOT={artifacts}::{canonical_state / 'artifacts'}",
            "--mapping",
            f"PIPELINE_WORKSPACE_DIR={workspace}::{canonical_state / 'workspace'}",
            "--mapping",
            f"SQLITE_PATH={state_db}::{canonical_state / 'worker_state.db'}",
            "--mapping",
            f"SQLITE_STATE_PATH={api_state_db}::{canonical_state / 'api_state.db'}",
            "--mapping",
            f"UV_PROJECT_ENVIRONMENT={project_venv}::{canonical_cache / 'project-venv'}",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert str(canonical_state / "artifacts") in env_text
    assert str(canonical_state / "workspace") in env_text
    assert str(canonical_state / "worker_state.db") in env_text
    assert str(canonical_state / "api_state.db") in env_text
    assert str(canonical_cache / "project-venv") in env_text
    assert (canonical_state / "artifacts" / "artifact.bin").is_file()
    assert (canonical_state / "workspace" / "job.txt").is_file()
    assert (canonical_state / "worker_state.db").is_file()
    assert (canonical_state / "api_state.db").is_file()
    assert state_db.exists() is False
    assert api_state_db.exists() is False
    assert payload["legacy_compatibility"]["legacy_paths_referenced_by_local_env"] == []
    assert payload["legacy_compatibility"]["legacy_retirement_blocked"] is False


def test_legacy_disk_migration_apply_supports_auto_mappings(tmp_path: Path) -> None:
    legacy_state = tmp_path / "legacy-state"
    legacy_cache = tmp_path / "legacy-cache"
    canonical_state = tmp_path / "canonical-cache-root"
    canonical_cache = tmp_path / "canonical-cache"
    artifacts = legacy_state / "artifacts"
    workspace = legacy_state / "workspace"
    state_db = legacy_state / "worker-state.db"
    api_state_db = legacy_state / "api-state.db"
    project_venv = legacy_cache / "project-venv"
    artifacts.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    project_venv.mkdir(parents=True, exist_ok=True)
    (artifacts / "artifact.bin").write_bytes(b"a" * 16)
    (workspace / "job.txt").write_text("job", encoding="utf-8")
    state_db.write_bytes(b"sqlite")
    api_state_db.write_bytes(b"sqlite-api")
    healthy_target = canonical_cache / "project-venv"
    (healthy_target / "bin").mkdir(parents=True, exist_ok=True)
    python_stub = healthy_target / "bin" / "python"
    python_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python_stub.chmod(0o755)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f'export PIPELINE_ARTIFACT_ROOT="{artifacts}"',
                f'export PIPELINE_WORKSPACE_DIR="{workspace}"',
                f'export SQLITE_PATH="{state_db}"',
                f'export SQLITE_STATE_PATH="{api_state_db}"',
                f'export UV_PROJECT_ENVIRONMENT="{project_venv}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(canonical_state),
            "user_cache_root": str(canonical_cache),
            "legacy_state_root": str(legacy_state),
            "legacy_cache_root": str(legacy_cache),
        },
        "migration_variables": [
            {
                "name": "PIPELINE_ARTIFACT_ROOT",
                "canonical_path": str(canonical_state / "artifacts"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": str(canonical_state / "workspace"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_PATH",
                "canonical_path": str(canonical_state / "worker_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_STATE_PATH",
                "canonical_path": str(canonical_state / "api_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "UV_PROJECT_ENVIRONMENT",
                "canonical_path": str(canonical_cache / "project-venv"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": True,
                "existing_target_verify_command": [
                    "bash",
                    "-lc",
                    'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
                ],
                "retire_source_on_migrate": False,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--auto-mappings",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert (canonical_state / "artifacts" / "artifact.bin").is_file()
    assert (canonical_state / "workspace" / "job.txt").is_file()
    assert (canonical_state / "worker_state.db").is_file()
    assert (canonical_state / "api_state.db").is_file()
    assert payload["actions"]


def test_legacy_disk_migration_apply_moves_sqlite_sidecars(tmp_path: Path) -> None:
    legacy_state = tmp_path / "legacy-state"
    legacy_cache = tmp_path / "legacy-cache"
    canonical_state = tmp_path / "canonical-cache-root"
    canonical_cache = tmp_path / "canonical-cache"
    state_db = legacy_state / "worker-state.db"
    api_state_db = legacy_state / "api-state.db"
    artifacts = legacy_state / "artifacts"
    workspace = legacy_state / "workspace"
    project_venv = legacy_cache / "project-venv"
    state_db.parent.mkdir(parents=True, exist_ok=True)
    legacy_cache.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    project_venv.mkdir(parents=True, exist_ok=True)
    state_db.write_bytes(b"sqlite")
    Path(f"{state_db}-wal").write_bytes(b"worker-wal")
    Path(f"{state_db}-shm").write_bytes(b"worker-shm")
    api_state_db.write_bytes(b"sqlite-api")
    Path(f"{api_state_db}-wal").write_bytes(b"api-wal")
    Path(f"{api_state_db}-shm").write_bytes(b"api-shm")

    healthy_target = canonical_cache / "project-venv"
    (healthy_target / "bin").mkdir(parents=True, exist_ok=True)
    python_stub = healthy_target / "bin" / "python"
    python_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python_stub.chmod(0o755)

    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f'export PIPELINE_ARTIFACT_ROOT="{legacy_state / "artifacts"}"',
                f'export PIPELINE_WORKSPACE_DIR="{workspace}"',
                f'export SQLITE_PATH="{state_db}"',
                f'export SQLITE_STATE_PATH="{api_state_db}"',
                f'export UV_PROJECT_ENVIRONMENT="{project_venv}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(canonical_state),
            "user_cache_root": str(canonical_cache),
            "legacy_state_root": str(legacy_state),
            "legacy_cache_root": str(legacy_cache),
        },
        "migration_variables": [
            {
                "name": "PIPELINE_ARTIFACT_ROOT",
                "canonical_path": str(canonical_state / "artifacts"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": str(canonical_state / "workspace"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_PATH",
                "canonical_path": str(canonical_state / "worker_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_STATE_PATH",
                "canonical_path": str(canonical_state / "api_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "UV_PROJECT_ENVIRONMENT",
                "canonical_path": str(canonical_cache / "project-venv"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": True,
                "existing_target_verify_command": [
                    "bash",
                    "-lc",
                    'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
                ],
                "retire_source_on_migrate": False,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--auto-mappings",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert (canonical_state / "worker_state.db").is_file()
    assert (canonical_state / "worker_state.db-wal").is_file()
    assert (canonical_state / "worker_state.db-shm").is_file()
    assert (canonical_state / "api_state.db").is_file()
    assert (canonical_state / "api_state.db-wal").is_file()
    assert (canonical_state / "api_state.db-shm").is_file()
    assert not Path(f"{state_db}-wal").exists()
    assert not Path(f"{state_db}-shm").exists()
    assert not Path(f"{api_state_db}-wal").exists()
    assert not Path(f"{api_state_db}-shm").exists()
    assert not legacy_state.exists()
    sqlite_action = next(
        action for action in payload["actions"] if action["variable"] == "SQLITE_PATH"
    )
    assert sqlite_action["moved_companions"]


def test_legacy_disk_migration_apply_cleans_orphan_sqlite_sidecars_after_canonical_cutover(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    legacy_root = home / ".sourceharbor"
    legacy_state = legacy_root / "state"
    canonical_root = home / ".cache" / "sourceharbor"
    canonical_state = canonical_root / "state"
    canonical_state.mkdir(parents=True, exist_ok=True)
    (canonical_state / "worker_state.db").write_bytes(b"canonical-worker")
    (canonical_state / "api_state.db").write_bytes(b"canonical-api")
    legacy_state.mkdir(parents=True, exist_ok=True)
    (legacy_state / "worker_state.db-wal").write_bytes(b"legacy-worker-wal")
    (legacy_state / "worker_state.db-shm").write_bytes(b"legacy-worker-shm")
    (legacy_state / "api_state.db-wal").write_bytes(b"legacy-api-wal")
    (legacy_state / "api_state.db-shm").write_bytes(b"legacy-api-shm")

    (tmp_path / ".env").write_text(
        (
            'export SOURCE_HARBOR_CACHE_ROOT="$HOME/.cache/sourceharbor"\n'
            'export SQLITE_PATH="$HOME/.cache/sourceharbor/state/worker_state.db"\n'
            'export SQLITE_STATE_PATH="$HOME/.cache/sourceharbor/state/api_state.db"\n'
            'export PIPELINE_ARTIFACT_ROOT="$HOME/.cache/sourceharbor/artifacts"\n'
            'export PIPELINE_WORKSPACE_DIR="$HOME/.cache/sourceharbor/workspace"\n'
            'export UV_PROJECT_ENVIRONMENT="$HOME/.cache/sourceharbor/project-venv"\n'
        ),
        encoding="utf-8",
    )

    policy = {
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
        "migration_variables": [
            {
                "name": "PIPELINE_ARTIFACT_ROOT",
                "canonical_path": "$HOME/.cache/sourceharbor/artifacts",
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": "$HOME/.cache/sourceharbor/workspace",
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_PATH",
                "canonical_path": "$HOME/.cache/sourceharbor/state/worker_state.db",
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_STATE_PATH",
                "canonical_path": "$HOME/.cache/sourceharbor/state/api_state.db",
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "UV_PROJECT_ENVIRONMENT",
                "canonical_path": "$HOME/.cache/sourceharbor/project-venv",
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": True,
                "existing_target_verify_command": [
                    "bash",
                    "-lc",
                    'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
                ],
                "retire_source_on_migrate": False,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
        env={"HOME": str(home)},
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--auto-mappings",
            "--json",
        ],
        env={"HOME": str(home)},
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert not legacy_state.exists()
    statuses = {action["status"] for action in payload["actions"]}
    assert "retired-legacy-sidecars" in statuses


def test_legacy_disk_migration_apply_rejects_shared_sqlite_source(tmp_path: Path) -> None:
    legacy_state = tmp_path / "legacy-state"
    state_db = legacy_state / "state.db"
    state_db.parent.mkdir(parents=True, exist_ok=True)
    state_db.write_bytes(b"sqlite")
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f'export SQLITE_PATH="{state_db}"',
                f'export SQLITE_STATE_PATH="{state_db}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(tmp_path / "canonical-state"),
            "user_cache_root": str(tmp_path / "canonical-cache"),
            "legacy_state_root": str(legacy_state),
            "legacy_cache_root": str(tmp_path / "legacy-cache"),
        },
        "migration_variables": [
            {
                "name": "SQLITE_PATH",
                "canonical_path": str(tmp_path / "canonical-state" / "worker_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "SQLITE_STATE_PATH",
                "canonical_path": str(tmp_path / "canonical-state" / "api_state.db"),
                "path_kind": "file",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)
    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--mapping",
            f"SQLITE_PATH={state_db}::{tmp_path / 'canonical-state' / 'worker_state.db'}",
            "--mapping",
            f"SQLITE_STATE_PATH={state_db}::{tmp_path / 'canonical-state' / 'api_state.db'}",
        ],
    )

    assert result.returncode != 0
    assert "shared SQLite source is not safe to auto-split" in result.stderr
    assert state_db.exists()
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert str(state_db) in env_text


def test_legacy_disk_migration_apply_rejects_unhealthy_existing_uv_target(tmp_path: Path) -> None:
    legacy_cache = tmp_path / "legacy-cache" / "project-venv"
    legacy_cache.mkdir(parents=True, exist_ok=True)
    unhealthy_target = tmp_path / "canonical-cache" / "project-venv"
    unhealthy_target.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        f'export UV_PROJECT_ENVIRONMENT="{legacy_cache}"\n',
        encoding="utf-8",
    )
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(tmp_path / "canonical-state"),
            "user_cache_root": str(tmp_path / "canonical-cache"),
            "legacy_state_root": str(tmp_path / "legacy-state"),
            "legacy_cache_root": str(tmp_path / "legacy-cache"),
        },
        "migration_variables": [
            {
                "name": "UV_PROJECT_ENVIRONMENT",
                "canonical_path": str(unhealthy_target),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": True,
                "existing_target_verify_command": [
                    "bash",
                    "-lc",
                    'test -x "$TARGET_PATH/bin/python" && "$TARGET_PATH/bin/python" -V >/dev/null',
                ],
                "retire_source_on_migrate": False,
            }
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)
    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--mapping",
            f"UV_PROJECT_ENVIRONMENT={legacy_cache}::{unhealthy_target}",
        ],
    )

    assert result.returncode != 0
    assert "existing target failed healthcheck" in result.stderr
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert str(legacy_cache) in env_text


def test_cleanup_disk_space_external_history_requires_canonical_equivalent(tmp_path: Path) -> None:
    candidate = tmp_path / "legacy-cache" / "closure-fix-venv"
    candidate.mkdir(parents=True, exist_ok=True)
    (candidate / "venv.bin").write_bytes(b"x")
    legacy_equivalent = tmp_path / "legacy-cache" / "project-venv"
    legacy_equivalent.mkdir(parents=True, exist_ok=True)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 0,
        "canonical_paths": {
            "legacy_state_root": "$HOME/.video-digestor",
            "legacy_cache_root": "$HOME/.cache/video-digestor",
        },
        "migration_variables": [],
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "external-history": {
                "candidates": [
                    {
                        "id": "closure-fix-venv",
                        "path": "legacy-cache/closure-fix-venv",
                        "quiet_minutes": 0,
                        "reference_markers": ["closure-fix-venv"],
                        "equivalent_paths": ["canonical-cache/project-venv"],
                        "verify_command": ["bash", "-lc", "test -d canonical-cache/project-venv"],
                        "layer": "repo-external-repo-owned",
                        "ownership": "repo-primary",
                        "classification": "verify-first",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "external-history",
            "--json",
        ],
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    gate_map = {gate["name"]: gate for gate in payload["candidates"][0]["gates"]}
    assert gate_map["equivalent-mainline-exists"]["ok"] is False


def test_legacy_disk_migration_apply_rolls_back_when_later_target_conflicts(tmp_path: Path) -> None:
    legacy_state = tmp_path / "legacy-state"
    artifacts = legacy_state / "artifacts"
    workspace = legacy_state / "workspace"
    artifacts.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    (artifacts / "artifact.bin").write_bytes(b"x")
    (workspace / "job.txt").write_text("job", encoding="utf-8")
    conflicting_target = tmp_path / "canonical-state" / "workspace"
    conflicting_target.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                f'export PIPELINE_ARTIFACT_ROOT="{artifacts}"',
                f'export PIPELINE_WORKSPACE_DIR="{workspace}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {
            "user_state_root": str(tmp_path / "canonical-state"),
            "user_cache_root": str(tmp_path / "canonical-cache"),
            "legacy_state_root": str(legacy_state),
            "legacy_cache_root": str(tmp_path / "legacy-cache"),
        },
        "migration_variables": [
            {
                "name": "PIPELINE_ARTIFACT_ROOT",
                "canonical_path": str(tmp_path / "canonical-state" / "artifacts"),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
            {
                "name": "PIPELINE_WORKSPACE_DIR",
                "canonical_path": str(conflicting_target),
                "path_kind": "directory",
                "ownership": "repo-primary",
                "allow_existing_target": False,
                "retire_source_on_migrate": True,
            },
        ],
        "legacy_reference_files": [".env"],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {},
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)
    audit = _run_script(
        "report_disk_space.py",
        cwd=tmp_path,
        args=["--repo-root", str(tmp_path), "--policy", str(policy_path), "--json"],
    )
    assert audit.returncode == 0, audit.stderr

    result = _run_script(
        "legacy_disk_migration.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--apply",
            "--yes",
            "--mapping",
            f"PIPELINE_ARTIFACT_ROOT={artifacts}::{tmp_path / 'canonical-state' / 'artifacts'}",
            "--mapping",
            f"PIPELINE_WORKSPACE_DIR={workspace}::{conflicting_target}",
        ],
    )

    assert result.returncode != 0
    assert artifacts.exists()
    assert workspace.exists()
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert str(artifacts) in env_text
    assert str(workspace) in env_text


def test_cleanup_disk_space_apply_restores_path_when_rebuild_fails(tmp_path: Path) -> None:
    candidate = tmp_path / ".runtime-cache" / "tmp" / "web-runtime"
    candidate.mkdir(parents=True, exist_ok=True)
    artifact = candidate / "artifact.bin"
    artifact.write_bytes(b"x" * 16)

    rebuild_script = tmp_path / "fail-rebuild.sh"
    rebuild_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "mkdir -p .runtime-cache/tmp/web-runtime\n"
        "printf 'partial\\n' > .runtime-cache/tmp/web-runtime/partial.txt\n"
        "exit 1\n",
        encoding="utf-8",
    )
    rebuild_script.chmod(0o755)

    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "canonical_paths": {},
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "excluded_paths": [],
        "cleanup_waves": {
            "repo-tmp": {
                "candidates": [
                    {
                        "id": "web-runtime",
                        "path": ".runtime-cache/tmp/web-runtime",
                        "quiet_minutes": 0,
                        "rebuild_command": ["bash", str(rebuild_script)],
                        "layer": "repo-internal",
                        "ownership": "repo-exclusive",
                        "classification": "cautious-clear",
                    }
                ]
            }
        },
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)

    result = _run_script(
        "cleanup_disk_space.py",
        cwd=tmp_path,
        args=[
            "--repo-root",
            str(tmp_path),
            "--policy",
            str(policy_path),
            "--wave",
            "repo-tmp",
            "--apply",
            "--yes",
            "--json",
        ],
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["actions"][0]["status"] == "failed-restored"
    assert artifact.is_file()
    assert (candidate / "partial.txt").exists() is False


def test_check_disk_space_audit_report_requires_legacy_fields(tmp_path: Path) -> None:
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {},
        "migration_variables": [],
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)
    report_path = tmp_path / ".runtime-cache" / "reports" / "governance" / "disk-space-audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "totals": {
                    "repo-internal": {"size_bytes": 0},
                    "repo-external-repo-owned": {"size_bytes": 0},
                    "shared-layer": {"size_bytes": 0},
                    "unverified-layer": {"size_bytes": None},
                    "confirmed_total": {"size_bytes": 0},
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_audit_checker(tmp_path, policy_path=policy_path, report_path=report_path)
    assert result.returncode == 1
    assert "legacy_compatibility.legacy_retirement_blocked" in result.stdout


def test_check_disk_space_audit_report_rejects_non_numeric_totals(tmp_path: Path) -> None:
    policy = {
        "version": 1,
        "report_path": ".runtime-cache/reports/governance/disk-space-audit.json",
        "cleanup_report_path": ".runtime-cache/reports/governance/disk-space-cleanup.json",
        "migration_report_path": ".runtime-cache/reports/governance/disk-space-legacy-migration.json",
        "legacy_retirement_quiet_minutes": 1440,
        "canonical_paths": {},
        "migration_variables": [],
        "legacy_reference_files": [],
        "audit_targets": [],
        "docker_named_volumes": [],
        "cleanup_waves": {},
        "excluded_paths": [],
    }
    policy_path = _write_policy(tmp_path / "policy.json", policy)
    report_path = tmp_path / ".runtime-cache" / "reports" / "governance" / "disk-space-audit.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "totals": {
                    "repo-internal": {"size_bytes": "oops", "size_human": "0 B"},
                    "repo-external-repo-owned": {"size_bytes": 0, "size_human": "0 B"},
                    "shared-layer": {"size_bytes": 0, "size_human": "0 B"},
                    "unverified-layer": {"size_bytes": None, "size_human": "unknown"},
                    "confirmed_total": {"size_bytes": 0, "size_human": "0 B"},
                },
                "legacy_compatibility": {
                    "active_markers_detected": False,
                    "legacy_paths_detected": [],
                    "legacy_paths_recently_active": [],
                    "legacy_paths_referenced_by_local_env": [],
                    "legacy_retirement_blocked": False,
                },
                "governance": {
                    "runtime_tmp_over_budget": {},
                    "legacy_default_write_drift": {},
                    "unexpected_repo_external_paths": {},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_audit_checker(tmp_path, policy_path=policy_path, report_path=report_path)
    assert result.returncode == 1
    assert "totals.repo-internal.size_bytes must be integer" in result.stdout


def test_check_disk_space_governance_rejects_runtime_web_drift(tmp_path: Path) -> None:
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "systemd").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reference").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env.example").write_text(
        'export PIPELINE_ARTIFACT_ROOT="$HOME/.sourceharbor/artifacts"\n'
        'export PIPELINE_WORKSPACE_DIR="$HOME/.sourceharbor/workspace"\n'
        'export SQLITE_PATH="$HOME/.sourceharbor/state/worker_state.db"\n'
        'export SQLITE_STATE_PATH="$HOME/.sourceharbor/state/api_state.db"\n'
        'export UV_PROJECT_ENVIRONMENT="$HOME/.cache/sourceharbor/project-venv"\n'
        "export WEB_RUNTIME_WEB_DIR=.runtime/web\n"
        "export WEB_E2E_RUNTIME_WEB_DIR=.runtime/web\n",
        encoding="utf-8",
    )
    (tmp_path / "infra" / "systemd" / "sourceharbor-api.service").write_text(
        "ExecStart=/bin/bash -lc 'exec \"${UV_PROJECT_ENVIRONMENT:-${HOME}/.cache/sourceharbor/project-venv}/bin/python\"'\n",
        encoding="utf-8",
    )
    (tmp_path / "infra" / "systemd" / "sourceharbor-worker.service").write_text(
        "ExecStart=/bin/bash -lc 'exec \"${UV_PROJECT_ENVIRONMENT:-${HOME}/.cache/sourceharbor/project-venv}/bin/python\"'\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reference" / "runtime-cache-retention.md").write_text(
        "## Canonical Compartments\n- `run/`\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reference" / "disk-space-governance.md").write_text(
        "runtime docs\n",
        encoding="utf-8",
    )
    policy_path = _write_policy(
        tmp_path / "config" / "governance" / "disk-space-governance.json",
        _minimal_checker_policy(),
    )

    result = _run_checker(tmp_path, policy_path=policy_path)
    assert result.returncode == 1
    assert "WEB_RUNTIME_WEB_DIR" in result.stdout


def test_check_disk_space_governance_rejects_shared_layer_cleanup_candidate(tmp_path: Path) -> None:
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "systemd").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reference").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env.example").write_text(
        'export PIPELINE_ARTIFACT_ROOT="$HOME/.sourceharbor/artifacts"\n'
        'export PIPELINE_WORKSPACE_DIR="$HOME/.sourceharbor/workspace"\n'
        'export SQLITE_PATH="$HOME/.sourceharbor/state/worker_state.db"\n'
        'export SQLITE_STATE_PATH="$HOME/.sourceharbor/state/api_state.db"\n'
        'export UV_PROJECT_ENVIRONMENT="$HOME/.cache/sourceharbor/project-venv"\n'
        "export WEB_RUNTIME_WEB_DIR=.runtime-cache/tmp/web-runtime/workspace/apps/web\n"
        "export WEB_E2E_RUNTIME_WEB_DIR=.runtime-cache/tmp/web-runtime/workspace/apps/web\n",
        encoding="utf-8",
    )
    for service in ("sourceharbor-api.service", "sourceharbor-worker.service"):
        (tmp_path / "infra" / "systemd" / service).write_text(
            "ExecStart=/bin/bash -lc 'exec \"${UV_PROJECT_ENVIRONMENT:-${HOME}/.cache/sourceharbor/project-venv}/bin/python\"'\n",
            encoding="utf-8",
        )
    (tmp_path / "docs" / "reference" / "runtime-cache-retention.md").write_text(
        "## Canonical Compartments\n- `run/`\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reference" / "disk-space-governance.md").write_text(
        "runtime docs\n",
        encoding="utf-8",
    )
    policy_path = _write_policy(
        tmp_path / "config" / "governance" / "disk-space-governance.json",
        {
            **_minimal_checker_policy(),
            "audit_targets": [
                {
                    "id": "shared-uv",
                    "label": "Shared uv",
                    "path": "$HOME/.cache/uv",
                    "layer": "shared-layer",
                    "ownership": "shared",
                    "category": "shared-cache",
                }
            ],
            "cleanup_waves": {
                "safe": {
                    "candidates": [
                        {
                            "id": "shared-uv",
                            "path": "$HOME/.cache/uv",
                            "layer": "shared-layer",
                            "ownership": "shared",
                            "classification": "safe-clear",
                        }
                    ]
                }
            },
        },
    )

    result = _run_checker(tmp_path, policy_path=policy_path)
    assert result.returncode == 1
    assert "shared-layer path" in result.stdout


def test_check_disk_space_governance_requires_user_state_root_in_audit_totals(
    tmp_path: Path,
) -> None:
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "systemd").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reference").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env.example").write_text(
        'export PIPELINE_ARTIFACT_ROOT="$HOME/.sourceharbor/artifacts"\n'
        'export PIPELINE_WORKSPACE_DIR="$HOME/.sourceharbor/workspace"\n'
        'export SQLITE_PATH="$HOME/.sourceharbor/state/worker_state.db"\n'
        'export SQLITE_STATE_PATH="$HOME/.sourceharbor/state/api_state.db"\n'
        'export UV_PROJECT_ENVIRONMENT="$HOME/.cache/sourceharbor/project-venv"\n'
        "export WEB_RUNTIME_WEB_DIR=.runtime-cache/tmp/web-runtime/workspace/apps/web\n"
        "export WEB_E2E_RUNTIME_WEB_DIR=.runtime-cache/tmp/web-runtime/workspace/apps/web\n",
        encoding="utf-8",
    )
    for service in ("sourceharbor-api.service", "sourceharbor-worker.service"):
        (tmp_path / "infra" / "systemd" / service).write_text(
            "ExecStart=/bin/bash -lc 'exec \"${UV_PROJECT_ENVIRONMENT:-${HOME}/.cache/sourceharbor/project-venv}/bin/python\"'\n",
            encoding="utf-8",
        )
    (tmp_path / "docs" / "reference" / "runtime-cache-retention.md").write_text(
        "## Canonical Compartments\n- `run/`\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reference" / "disk-space-governance.md").write_text(
        "runtime docs\n",
        encoding="utf-8",
    )
    policy_path = _write_policy(
        tmp_path / "config" / "governance" / "disk-space-governance.json",
        {
            **_minimal_checker_policy(),
            "canonical_paths": {
                "user_state_root": "$HOME/.sourceharbor",
            },
        },
    )

    result = _run_checker(tmp_path, policy_path=policy_path)
    assert result.returncode == 1
    assert "must count canonical user_state_root" in result.stdout


def test_check_disk_space_governance_rejects_excluded_path_and_broad_repo_tmp_lock(
    tmp_path: Path,
) -> None:
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "systemd").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reference").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env.example").write_text(
        'export PIPELINE_ARTIFACT_ROOT="$HOME/.sourceharbor/artifacts"\n'
        'export PIPELINE_WORKSPACE_DIR="$HOME/.sourceharbor/workspace"\n'
        'export SQLITE_PATH="$HOME/.sourceharbor/state/worker_state.db"\n'
        'export SQLITE_STATE_PATH="$HOME/.sourceharbor/state/api_state.db"\n'
        'export UV_PROJECT_ENVIRONMENT="$HOME/.cache/sourceharbor/project-venv"\n'
        "export WEB_RUNTIME_WEB_DIR=.runtime-cache/tmp/web-runtime/workspace/apps/web\n"
        "export WEB_E2E_RUNTIME_WEB_DIR=.runtime-cache/tmp/web-runtime/workspace/apps/web\n",
        encoding="utf-8",
    )
    for service in ("sourceharbor-api.service", "sourceharbor-worker.service"):
        (tmp_path / "infra" / "systemd" / service).write_text(
            "ExecStart=/bin/bash -lc 'exec \"${UV_PROJECT_ENVIRONMENT:-${HOME}/.cache/sourceharbor/project-venv}/bin/python\"'\n",
            encoding="utf-8",
        )
    (tmp_path / "docs" / "reference" / "runtime-cache-retention.md").write_text(
        "## Canonical Compartments\n- `run/`\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reference" / "disk-space-governance.md").write_text(
        "runtime docs\n",
        encoding="utf-8",
    )
    policy_path = _write_policy(
        tmp_path / "config" / "governance" / "disk-space-governance.json",
        {
            **_minimal_checker_policy(),
            "cleanup_waves": {
                "repo-tmp": {
                    "candidates": [
                        {
                            "id": "excluded-mainline",
                            "path": "apps/web/node_modules",
                            "layer": "repo-internal",
                            "ownership": "repo-exclusive",
                            "classification": "cautious-clear",
                            "lock_markers": ["*.lock"],
                        }
                    ]
                }
            },
            "excluded_paths": ["apps/web/node_modules"],
        },
    )

    result = _run_checker(tmp_path, policy_path=policy_path)
    assert result.returncode == 1
    assert "excluded path" in result.stdout
    assert "broad lock_markers" in result.stdout
