from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_script(
    tmp_path: Path, *, env: dict[str, str], args: list[str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_repo_root() / "scripts" / "runtime" / "docker_hygiene.py"),
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
            "groups": {},
        },
        "docker_hygiene": {
            "report_path": ".runtime-cache/reports/governance/docker-hygiene.json",
            "repo_container_prefixes": ["sourceharbor-"],
            "repo_network_prefixes": ["sourceharbor"],
            "repo_named_volumes": ["sourceharbor_core_postgres_data"],
            "local_debug_image_quiet_hours": 24,
            "repo_local_debug_images": [
                "ghcr.io/xiaojiou176-open/sourceharbor-ci-standard:local-debug"
            ],
        },
        "excluded_paths": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_docker_hygiene_reports_unverified_when_daemon_unavailable(tmp_path: Path) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "info" ]]; then\n'
        "  echo 'daemon unavailable' >&2\n"
        "  exit 1\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    _write_policy(tmp_path / "policy.json")
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = _run_script(tmp_path, env=env, args=["--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "unverified"
    assert payload["docker_ready"] is False


def test_docker_hygiene_audit_collects_repo_owned_objects(tmp_path: Path) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    log_path = tmp_path / "docker.log"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'echo "$*" >> "' + str(log_path) + '"\n'
        'if [[ "$1" == "info" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "ps" && "$2" == "-a" && "$3" == "--filter" && "$4" == ancestor=* ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "ps" && "$2" == "-a" && "$3" == "--filter" && "$4" == volume=* ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "ps" && "$2" == "-a" ]]; then\n'
        '  printf \'{"ID":"abc","Names":"sourceharbor-core-postgres","Image":"postgres:16","Status":"Exited (0) 1 hour ago","State":"exited"}\\n\'\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "network" && "$2" == "ls" ]]; then\n'
        '  printf \'{"ID":"net1","Name":"sourceharbor_default","Driver":"bridge"}\\n\'\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "network" && "$2" == "inspect" ]]; then\n'
        "  printf '[{\"Containers\":{}}]\\n'\n"
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "volume" && "$2" == "inspect" ]]; then\n'
        '  printf \'[{"Name":"sourceharbor_core_postgres_data","CreatedAt":"2026-03-20T00:00:00Z","Mountpoint":"/var/lib/docker/volumes/sourceharbor_core_postgres_data/_data","Labels":{}}]\\n\'\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "image" && "$2" == "inspect" ]]; then\n'
        '  printf \'[{"RepoTags":["ghcr.io/xiaojiou176-open/sourceharbor-ci-standard:local-debug"],"Created":"2026-03-20T00:00:00Z","Metadata":{"LastTagTime":"2026-03-21T00:00:00Z"}}]\\n\'\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "rm" || "$1" == "network" || "$1" == "image" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    _write_policy(tmp_path / "policy.json")
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    audit = _run_script(tmp_path, env=env, args=["--json"])
    assert audit.returncode == 0, audit.stderr
    payload = json.loads(audit.stdout)
    assert payload["status"] == "pass"
    assert payload["containers"][0]["name"] == "sourceharbor-core-postgres"
    assert payload["networks"][0]["name"] == "sourceharbor_default"
    assert payload["volumes"][0]["name"] == "sourceharbor_core_postgres_data"
    assert payload["volumes"][0]["cleanup_eligible"] is False
    assert payload["images"][0]["exists"] is True
    assert payload["images"][0]["cleanup_eligible"] is True

    apply = _run_script(tmp_path, env=env, args=["--apply", "--json"])
    assert apply.returncode == 0, apply.stderr
    apply_payload = json.loads(apply.stdout)
    assert any(
        item["kind"] == "container" and item["status"] == "deleted"
        for item in apply_payload["actions"]
    )
    assert any(
        item["kind"] == "network" and item["status"] == "deleted"
        for item in apply_payload["actions"]
    )
    assert any(
        item["kind"] == "image" and item["status"] == "deleted" for item in apply_payload["actions"]
    )
    assert all(item["kind"] != "volume" for item in apply_payload["actions"])


def test_docker_hygiene_blocks_recent_local_debug_image_cleanup(tmp_path: Path) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "info" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "ps" && "$2" == "-a" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "network" && "$2" == "ls" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "volume" && "$2" == "inspect" ]]; then\n'
        "  exit 1\n"
        "fi\n"
        'if [[ "$1" == "image" && "$2" == "inspect" ]]; then\n'
        '  printf \'[{"RepoTags":["ghcr.io/xiaojiou176-open/sourceharbor-ci-standard:local-debug"],"Created":"2099-01-01T00:00:00Z","Metadata":{"LastTagTime":"2099-01-01T00:00:00Z"}}]\\n\'\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "image" && "$2" == "rm" ]]; then\n'
        "  echo 'image rm should not be called for recent images' >&2\n"
        "  exit 9\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    _write_policy(tmp_path / "policy.json")
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = _run_script(tmp_path, env=env, args=["--apply", "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["images"][0]["cleanup_eligible"] is False
    assert "image-quiet-window-not-reached" in payload["images"][0]["cleanup_blockers"]
    assert not any(item["kind"] == "image" for item in payload["actions"])
