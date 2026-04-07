from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _run_bash(
    script: str, *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", "-lc", script],
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_load_repo_env_empty_parent_value_does_not_override_repo_env_file(
    tmp_path: Path,
) -> None:
    root = _repo_root()
    key = "TEST_LOAD_ENV_PRIORITY_KEY"
    (tmp_path / ".env").write_text(f"export {key}='from_repo_env'\n", encoding="utf-8")

    probe = f"""
source "{root}/scripts/lib/load_env.sh"
load_repo_env "{tmp_path}" "env_precedence_regression" "local"
printf '%s\n' "${{{key}:-}}"
"""

    proc = _run_bash(probe, env={key: ""})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "from_repo_env"


def test_load_repo_env_non_empty_parent_value_still_has_highest_precedence(
    tmp_path: Path,
) -> None:
    root = _repo_root()
    key = "TEST_LOAD_ENV_PRIORITY_KEY"
    (tmp_path / ".env").write_text(f"export {key}='from_repo_env'\n", encoding="utf-8")

    probe = f"""
source "{root}/scripts/lib/load_env.sh"
load_repo_env "{tmp_path}" "env_precedence_regression" "local"
printf '%s\n' "${{{key}:-}}"
"""

    proc = _run_bash(probe, env={key: "from_parent"})
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "from_parent"


def test_load_repo_env_legacy_sourceharbor_paths_normalize_to_cache_root(
    tmp_path: Path,
) -> None:
    root = _repo_root()
    home = tmp_path / "home"
    legacy_root = home / ".sourceharbor"
    (legacy_root / "state").mkdir(parents=True, exist_ok=True)
    (legacy_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (legacy_root / "workspace").mkdir(parents=True, exist_ok=True)
    (legacy_root / "project-venv").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        (
            'export PIPELINE_ARTIFACT_ROOT="$HOME/.sourceharbor/artifacts"\n'
            'export PIPELINE_WORKSPACE_DIR="$HOME/.sourceharbor/workspace"\n'
            'export SQLITE_PATH="$HOME/.sourceharbor/state/worker_state.db"\n'
            'export SQLITE_STATE_PATH="$HOME/.sourceharbor/state/api_state.db"\n'
            'export UV_PROJECT_ENVIRONMENT="$HOME/.sourceharbor/project-venv"\n'
        ),
        encoding="utf-8",
    )

    probe = f"""
source "{root}/scripts/lib/load_env.sh"
load_repo_env "{tmp_path}" "legacy_path_normalization" "local"
printf 'ART=%s\\n' "${{PIPELINE_ARTIFACT_ROOT:-}}"
printf 'WS=%s\\n' "${{PIPELINE_WORKSPACE_DIR:-}}"
printf 'SQLITE=%s\\n' "${{SQLITE_PATH:-}}"
printf 'SQLITE_STATE=%s\\n' "${{SQLITE_STATE_PATH:-}}"
printf 'UV=%s\\n' "${{UV_PROJECT_ENVIRONMENT:-}}"
"""

    proc = _run_bash(
        probe,
        env={
            "HOME": str(home),
            "PIPELINE_ARTIFACT_ROOT": "",
            "PIPELINE_WORKSPACE_DIR": "",
            "SQLITE_PATH": "",
            "SQLITE_STATE_PATH": "",
            "UV_PROJECT_ENVIRONMENT": "",
        },
    )
    assert proc.returncode == 0, proc.stderr
    lines = dict(line.split("=", 1) for line in proc.stdout.strip().splitlines())
    assert lines["ART"] == str(home / ".cache" / "sourceharbor" / "artifacts")
    assert lines["WS"] == str(home / ".cache" / "sourceharbor" / "workspace")
    assert lines["SQLITE"] == str(home / ".cache" / "sourceharbor" / "state" / "worker_state.db")
    assert lines["SQLITE_STATE"] == str(home / ".cache" / "sourceharbor" / "state" / "api_state.db")
    assert lines["UV"] == str(home / ".cache" / "sourceharbor" / "project-venv")
