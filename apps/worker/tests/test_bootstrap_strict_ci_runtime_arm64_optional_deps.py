from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _write_prepare_web_runtime_stub(repo_root: Path, *, runtime_relative: str) -> Path:
    ci_dir = repo_root / "scripts" / "ci"
    ci_dir.mkdir(parents=True, exist_ok=True)
    helper_path = ci_dir / "prepare_web_runtime.sh"
    helper_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"\n'
        f'runtime_dir="$ROOT_DIR/{runtime_relative}"\n'
        "shell_exports=0\n"
        "skip_install=0\n"
        "while [[ $# -gt 0 ]]; do\n"
        '  case "$1" in\n'
        "    --shell-exports) shell_exports=1; shift ;;\n"
        "    --skip-install) skip_install=${2:-1}; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        'mkdir -p "$runtime_dir"\n'
        'if [[ "$skip_install" != "1" ]]; then\n'
        '  (cd "$runtime_dir" && npm ci --no-audit --no-fund)\n'
        "fi\n"
        'if [[ "$shell_exports" == "1" ]]; then\n'
        "  printf 'export WEB_RUNTIME_WEB_DIR=%q\\n' \"$runtime_dir\"\n"
        "else\n"
        "  printf 'WEB_RUNTIME_WEB_DIR=%s\\n' \"$runtime_dir\"\n"
        "fi\n",
        encoding="utf-8",
    )
    helper_path.chmod(0o755)
    return helper_path


def test_configure_strict_ci_python_environment_uses_tmp_scoped_repo_env() -> None:
    source = (_repo_root() / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir) / "repo"
        scripts_dir = repo_root / "scripts"
        ci_dir = scripts_dir / "ci"
        tmp_root = Path(tmp_dir) / "tmp-root"
        scripts_dir.mkdir(parents=True)
        ci_dir.mkdir(parents=True)
        tmp_root.mkdir()

        (ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(source, encoding="utf-8")

        child_env = {
            **os.environ,
            "TMPDIR": str(tmp_root),
        }
        child_env.pop("UV_PROJECT_ENVIRONMENT", None)
        child_env.pop("VIRTUAL_ENV", None)
        child_env.pop("UV_LINK_MODE", None)

        result = subprocess.run(
            [
                "bash",
                "-c",
                "export STRICT_CI_BOOTSTRAP_LOAD_HELPERS_ONLY=1; "
                "source ./scripts/ci/bootstrap_strict_ci_runtime.sh; "
                "configure_strict_ci_python_environment; "
                'printf "UV=%s\\nVENV=%s\\nPATH0=%s\\n" '
                '"$UV_PROJECT_ENVIRONMENT" "$VIRTUAL_ENV" "${PATH%%:*}"',
            ],
            cwd=repo_root,
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        lines = dict(
            line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line
        )
        uv_path = Path(lines["UV"])

        assert uv_path.is_relative_to(tmp_root / "sourceharbor-strict-ci")
        assert uv_path.name
        assert lines["UV"] == lines["VENV"]
        assert lines["PATH0"] == lines["UV"] + "/bin"


def test_web_node_modules_ready_rejects_corrupt_dependency_tree() -> None:
    source = (_repo_root() / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        ci_dir = scripts_dir / "ci"
        runtime_web_dir = (
            repo_root / ".runtime-cache" / "tmp" / "web-runtime" / "workspace" / "apps" / "web"
        )
        bin_dir = repo_root / "bin"

        scripts_dir.mkdir(parents=True)
        ci_dir.mkdir(parents=True)
        _write_prepare_web_runtime_stub(
            repo_root,
            runtime_relative=".runtime-cache/tmp/web-runtime/workspace/apps/web",
        )
        (runtime_web_dir / "node_modules" / ".bin").mkdir(parents=True)
        bin_dir.mkdir()

        (ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(source, encoding="utf-8")
        (runtime_web_dir / "node_modules" / ".bin" / "eslint").write_text(
            "#!/usr/bin/env bash\nexit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "node").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf \"Cannot find module 'eslint-visitor-keys'\\n\" >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )

        (runtime_web_dir / "node_modules" / ".bin" / "eslint").chmod(0o755)
        (bin_dir / "node").chmod(0o755)

        result = subprocess.run(
            [
                "bash",
                "-c",
                "export STRICT_CI_BOOTSTRAP_LOAD_HELPERS_ONLY=1; "
                "source ./scripts/ci/bootstrap_strict_ci_runtime.sh; "
                "web_node_modules_ready",
            ],
            cwd=repo_root,
            env={**os.environ, "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"},
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        assert "eslint-visitor-keys" in result.stderr


def test_bootstrap_runtime_fails_fast_when_linux_arm64_optional_native_web_packages_are_missing() -> (
    None
):
    source = (_repo_root() / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )
    package_json = (_repo_root() / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    package_lock = (_repo_root() / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        ci_dir = scripts_dir / "ci"
        web_dir = repo_root / "apps" / "web"
        bin_dir = repo_root / "bin"

        scripts_dir.mkdir(parents=True)
        ci_dir.mkdir(parents=True)
        web_dir.mkdir(parents=True)
        bin_dir.mkdir()
        _write_prepare_web_runtime_stub(
            repo_root,
            runtime_relative=".runtime-cache/tmp/web-runtime/workspace/apps/web",
        )

        (ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(source, encoding="utf-8")
        (web_dir / "package.json").write_text(package_json, encoding="utf-8")
        (web_dir / "package-lock.json").write_text(package_lock, encoding="utf-8")
        (bin_dir / "uv").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'UV_PROJECT_ENVIRONMENT=%s\\n\' "${UV_PROJECT_ENVIRONMENT:-}" >> "${UV_LOG:?}"\n'
            "exit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "uname").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'case "${1:-}" in\n'
            "  -s) printf 'Linux\\n' ;;\n"
            "  -m) printf 'aarch64\\n' ;;\n"
            '  *) /usr/bin/uname "$@" ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        (bin_dir / "npm").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'%s\\n\' "$*" >> "${NPM_LOG:?}"\n'
            "prefix=''\n"
            'args=("$@")\n'
            "index=0\n"
            "while [[ $index -lt ${#args[@]} ]]; do\n"
            '  current="${args[$index]}"\n'
            "  if [[ \"$current\" == '--prefix' ]]; then\n"
            "    index=$((index + 1))\n"
            '    prefix="${args[$index]}"\n'
            "    index=$((index + 1))\n"
            "    continue\n"
            "  fi\n"
            '  command_name="$current"\n'
            "  break\n"
            "done\n"
            'target_dir="${PWD}/${prefix}"\n'
            "if [[ \"$command_name\" == 'ci' ]]; then\n"
            '  mkdir -p "$target_dir/node_modules"\n'
            '  mkdir -p "$target_dir/node_modules/.bin"\n'
            '  mkdir -p "$target_dir/node_modules/eslint"\n'
            '  mkdir -p "$target_dir/node_modules/eslint-visitor-keys"\n'
            '  : > "$target_dir/node_modules/.bin/eslint"\n'
            '  : > "$target_dir/node_modules/eslint/package.json"\n'
            '  : > "$target_dir/node_modules/eslint-visitor-keys/package.json"\n'
            '  chmod +x "$target_dir/node_modules/.bin/eslint"\n'
            "  exit 0\n"
            "fi\n"
            "if [[ \"$command_name\" == 'install' ]]; then\n"
            '  mkdir -p "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss"\n'
            '  : > "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu/rollup.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss-linux-arm64-gnu/lightningcss.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss/lightningcss.linux-arm64-gnu.node"\n'
            "  exit 0\n"
            "fi\n"
            "printf 'unexpected npm command: %s\\n' \"$*\" >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        (bin_dir / "node").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'missing lightningcss linux arm64 native binary\\n' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )

        for path in (
            ci_dir / "bootstrap_strict_ci_runtime.sh",
            bin_dir / "uv",
            bin_dir / "uname",
            bin_dir / "npm",
            bin_dir / "node",
        ):
            path.chmod(0o755)

        npm_log = repo_root / "npm.log"
        uv_log = repo_root / "uv.log"
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["NPM_LOG"] = str(npm_log)
        env["UV_LOG"] = str(uv_log)
        env.pop("UV_PROJECT_ENVIRONMENT", None)
        env.pop("VIRTUAL_ENV", None)
        env.pop("UV_LINK_MODE", None)

        result = subprocess.run(
            ["bash", str(ci_dir / "bootstrap_strict_ci_runtime.sh")],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0

        npm_calls = npm_log.read_text(encoding="utf-8")
        assert "ci --no-audit --no-fund" in npm_calls
        assert "--prefix apps/web install" not in npm_calls
        uv_environment = uv_log.read_text(encoding="utf-8").strip().split("=", 1)[1]
        assert Path(uv_environment).is_relative_to(
            Path(tempfile.gettempdir()) / "sourceharbor-strict-ci"
        )
        assert uv_environment.endswith("/Linux-aarch64")


def test_bootstrap_runtime_allows_followup_ci_retry_when_arm64_native_web_packages_remain_missing() -> (
    None
):
    source = (_repo_root() / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )
    package_json = (_repo_root() / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    package_lock = (_repo_root() / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        ci_dir = scripts_dir / "ci"
        web_dir = repo_root / "apps" / "web"
        bin_dir = repo_root / "bin"

        scripts_dir.mkdir(parents=True)
        ci_dir.mkdir(parents=True)
        web_dir.mkdir(parents=True)
        bin_dir.mkdir()
        _write_prepare_web_runtime_stub(
            repo_root,
            runtime_relative=".runtime-cache/tmp/web-runtime/workspace/apps/web",
        )

        (ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(source, encoding="utf-8")
        (web_dir / "package.json").write_text(package_json, encoding="utf-8")
        (web_dir / "package-lock.json").write_text(package_lock, encoding="utf-8")
        (bin_dir / "uv").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "uname").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'case "${1:-}" in\n'
            "  -s) printf 'Linux\\n' ;;\n"
            "  -m) printf 'aarch64\\n' ;;\n"
            '  *) /usr/bin/uname "$@" ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        (bin_dir / "npm").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'%s\\n\' "$*" >> "${NPM_LOG:?}"\n'
            "prefix=''\n"
            'args=("$@")\n'
            "index=0\n"
            "while [[ $index -lt ${#args[@]} ]]; do\n"
            '  current="${args[$index]}"\n'
            "  if [[ \"$current\" == '--prefix' ]]; then\n"
            "    index=$((index + 1))\n"
            '    prefix="${args[$index]}"\n'
            "    index=$((index + 1))\n"
            "    continue\n"
            "  fi\n"
            '  command_name="$current"\n'
            "  break\n"
            "done\n"
            'target_dir="${PWD}/${prefix}"\n'
            "if [[ \"$command_name\" == 'ci' ]]; then\n"
            '  rm -rf "$target_dir/node_modules"\n'
            '  mkdir -p "$target_dir/node_modules"\n'
            '  mkdir -p "$target_dir/node_modules/.bin"\n'
            '  mkdir -p "$target_dir/node_modules/eslint"\n'
            '  mkdir -p "$target_dir/node_modules/eslint-visitor-keys"\n'
            '  : > "$target_dir/node_modules/.bin/eslint"\n'
            '  : > "$target_dir/node_modules/eslint/package.json"\n'
            '  : > "$target_dir/node_modules/eslint-visitor-keys/package.json"\n'
            '  chmod +x "$target_dir/node_modules/.bin/eslint"\n'
            "  exit 0\n"
            "fi\n"
            "if [[ \"$command_name\" == 'install' ]]; then\n"
            '  mkdir -p "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss"\n'
            '  : > "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu/rollup.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss-linux-arm64-gnu/lightningcss.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss/lightningcss.linux-arm64-gnu.node"\n'
            "  exit 0\n"
            "fi\n"
            "printf 'unexpected npm command: %s\\n' \"$*\" >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        (bin_dir / "node").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'missing lightningcss linux arm64 native binary\\n' >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        for path in (
            ci_dir / "bootstrap_strict_ci_runtime.sh",
            bin_dir / "uv",
            bin_dir / "uname",
            bin_dir / "npm",
            bin_dir / "node",
        ):
            path.chmod(0o755)

        npm_log = repo_root / "npm.log"
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["NPM_LOG"] = str(npm_log)
        env.pop("UV_PROJECT_ENVIRONMENT", None)
        env.pop("VIRTUAL_ENV", None)
        env.pop("UV_LINK_MODE", None)

        subprocess.run(
            [
                "bash",
                "-c",
                "source ./scripts/ci/bootstrap_strict_ci_runtime.sh && npm --prefix apps/web ci --no-audit --no-fund",
            ],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        npm_calls = npm_log.read_text(encoding="utf-8")
        assert npm_calls.count("--prefix apps/web ci --no-audit --no-fund") >= 1
        assert "--prefix apps/web install" not in npm_calls


def test_ci_web_test_build_fails_fast_when_arm64_optional_native_web_packages_are_missing() -> None:
    repo = _repo_root()
    bootstrap_source = (repo / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )
    web_test_build_source = (repo / "scripts" / "ci" / "web_test_build.sh").read_text(
        encoding="utf-8"
    )
    package_json = (repo / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    package_lock = (repo / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        ci_dir = scripts_dir / "ci"
        web_dir = repo_root / "apps" / "web"
        bin_dir = repo_root / "bin"

        scripts_dir.mkdir(parents=True)
        ci_dir.mkdir(parents=True)
        web_dir.mkdir(parents=True)
        bin_dir.mkdir()
        _write_prepare_web_runtime_stub(
            repo_root,
            runtime_relative=".runtime-cache/tmp/web-runtime/workspace/apps/web",
        )

        (ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(bootstrap_source, encoding="utf-8")

        (ci_dir / "web_test_build.sh").write_text(web_test_build_source, encoding="utf-8")
        (ci_dir / "contract.py").write_text(
            "import sys\n"
            "if sys.argv[1:] == ['shell-exports']:\n"
            "    print('export STRICT_CI_COVERAGE_MIN=95')\n"
            "    print('export STRICT_CI_CORE_COVERAGE_MIN=95')\n"
            "    print('export STRICT_CI_WEB_BUTTON_COMBINED_THRESHOLD=1.0')\n"
            "    print('export STRICT_CI_WEB_BUTTON_E2E_THRESHOLD=0.6')\n"
            "    print('export STRICT_CI_WEB_BUTTON_UNIT_THRESHOLD=0.93')\n",
            encoding="utf-8",
        )
        for helper_name in (
            "check_design_tokens.py",
            "check_web_coverage_threshold.py",
            "check_web_button_coverage.py",
        ):
            (scripts_dir / helper_name).write_text(
                "import sys\nraise SystemExit(0)\n",
                encoding="utf-8",
            )
        (web_dir / "package.json").write_text(package_json, encoding="utf-8")
        (web_dir / "package-lock.json").write_text(package_lock, encoding="utf-8")
        (bin_dir / "uv").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'uv %s\\n\' "$*" >> "${UV_LOG:?}"\n'
            "exit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "uname").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'case "${1:-}" in\n'
            "  -s) printf 'Linux\\n' ;;\n"
            "  -m) printf 'aarch64\\n' ;;\n"
            '  *) /usr/bin/uname "$@" ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        (bin_dir / "npm").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'%s\\n\' "$*" >> "${NPM_LOG:?}"\n'
            "prefix=''\n"
            'args=("$@")\n'
            "index=0\n"
            "while [[ $index -lt ${#args[@]} ]]; do\n"
            '  current="${args[$index]}"\n'
            "  if [[ \"$current\" == '--prefix' ]]; then\n"
            "    index=$((index + 1))\n"
            '    prefix="${args[$index]}"\n'
            "    index=$((index + 1))\n"
            "    continue\n"
            "  fi\n"
            '  command_name="$current"\n'
            "  break\n"
            "done\n"
            'target_dir="${PWD}/${prefix}"\n'
            "if [[ \"$command_name\" == 'ci' ]]; then\n"
            '  rm -rf "$target_dir/node_modules"\n'
            '  mkdir -p "$target_dir/node_modules"\n'
            '  mkdir -p "$target_dir/node_modules/.bin"\n'
            '  mkdir -p "$target_dir/node_modules/eslint"\n'
            '  mkdir -p "$target_dir/node_modules/eslint-visitor-keys"\n'
            '  : > "$target_dir/node_modules/.bin/eslint"\n'
            '  : > "$target_dir/node_modules/eslint/package.json"\n'
            '  : > "$target_dir/node_modules/eslint-visitor-keys/package.json"\n'
            "  exit 0\n"
            "fi\n"
            "if [[ \"$command_name\" == 'install' ]]; then\n"
            '  mkdir -p "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss"\n'
            '  : > "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu/rollup.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss-linux-arm64-gnu/lightningcss.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss/lightningcss.linux-arm64-gnu.node"\n'
            "  exit 0\n"
            "fi\n"
            "if [[ \"$command_name\" == 'run' ]]; then\n"
            "  exit 0\n"
            "fi\n"
            "printf 'unexpected npm command: %s\\n' \"$*\" >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        (bin_dir / "node").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf \"Cannot find module 'eslint-visitor-keys'\\n\" >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )

        for path in (
            ci_dir / "bootstrap_strict_ci_runtime.sh",
            ci_dir / "web_test_build.sh",
            bin_dir / "uv",
            bin_dir / "uname",
            bin_dir / "npm",
            bin_dir / "node",
        ):
            path.chmod(0o755)

        npm_log = repo_root / "npm.log"
        uv_log = repo_root / "uv.log"
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["NPM_LOG"] = str(npm_log)
        env["UV_LOG"] = str(uv_log)

        result = subprocess.run(
            ["bash", str(ci_dir / "web_test_build.sh")],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0

        npm_calls = npm_log.read_text(encoding="utf-8")
        assert "ci --no-audit --no-fund" in npm_calls
        assert "--prefix apps/web install" not in npm_calls
        assert "npm --prefix apps/web ci" not in uv_log.read_text(encoding="utf-8")


def test_bootstrap_runtime_reinstalls_web_dependencies_when_transitive_lint_dependency_is_missing() -> (
    None
):
    source = (_repo_root() / "scripts" / "ci" / "bootstrap_strict_ci_runtime.sh").read_text(
        encoding="utf-8"
    )
    package_json = (_repo_root() / "apps" / "web" / "package.json").read_text(encoding="utf-8")
    package_lock = (_repo_root() / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        ci_dir = scripts_dir / "ci"
        web_dir = repo_root / "apps" / "web"
        runtime_web_dir = (
            repo_root / ".runtime-cache" / "temp" / "web-runtime" / "workspace" / "apps" / "web"
        )
        cache_dir = repo_root / ".runtime-cache" / "run" / "strict-ci"
        bin_dir = repo_root / "bin"

        scripts_dir.mkdir(parents=True)
        ci_dir.mkdir(parents=True)
        web_dir.mkdir(parents=True)
        cache_dir.mkdir(parents=True)
        bin_dir.mkdir()
        _write_prepare_web_runtime_stub(
            repo_root,
            runtime_relative=".runtime-cache/tmp/web-runtime/workspace/apps/web",
        )

        (ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(source, encoding="utf-8")
        (web_dir / "package.json").write_text(package_json, encoding="utf-8")
        (web_dir / "package-lock.json").write_text(package_lock, encoding="utf-8")
        (bin_dir / "uv").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "uname").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'case "${1:-}" in\n'
            "  -s) printf 'Linux\\n' ;;\n"
            "  -m) printf 'x86_64\\n' ;;\n"
            '  *) /usr/bin/uname "$@" ;;\n'
            "esac\n",
            encoding="utf-8",
        )
        (bin_dir / "npm").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'%s\\n\' "$*" >> "${NPM_LOG:?}"\n'
            "prefix=''\n"
            'args=("$@")\n'
            "index=0\n"
            "while [[ $index -lt ${#args[@]} ]]; do\n"
            '  current="${args[$index]}"\n'
            "  if [[ \"$current\" == '--prefix' ]]; then\n"
            "    index=$((index + 1))\n"
            '    prefix="${args[$index]}"\n'
            "    index=$((index + 1))\n"
            "    continue\n"
            "  fi\n"
            '  command_name="$current"\n'
            "  break\n"
            "done\n"
            'target_dir="${PWD}/${prefix}"\n'
            "if [[ \"$command_name\" == 'ci' ]]; then\n"
            '  mkdir -p "$target_dir/node_modules/.bin"\n'
            '  mkdir -p "$target_dir/node_modules/eslint"\n'
            '  mkdir -p "$target_dir/node_modules/eslint-visitor-keys"\n'
            '  : > "$target_dir/node_modules/.bin/eslint"\n'
            '  : > "$target_dir/node_modules/eslint/package.json"\n'
            '  : > "$target_dir/node_modules/eslint-visitor-keys/package.json"\n'
            '  chmod +x "$target_dir/node_modules/.bin/eslint"\n'
            "  exit 0\n"
            "fi\n"
            "if [[ \"$command_name\" == 'install' ]]; then\n"
            '  mkdir -p "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss-linux-arm64-gnu"\n'
            '  mkdir -p "$target_dir/node_modules/lightningcss"\n'
            '  : > "$target_dir/node_modules/@rollup/rollup-linux-arm64-gnu/rollup.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss-linux-arm64-gnu/lightningcss.linux-arm64-gnu.node"\n'
            '  : > "$target_dir/node_modules/lightningcss/lightningcss.linux-arm64-gnu.node"\n'
            "  exit 0\n"
            "fi\n"
            "printf 'unexpected npm command: %s\\n' \"$*\" >&2\n"
            "exit 1\n",
            encoding="utf-8",
        )
        (bin_dir / "node").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
            encoding="utf-8",
        )
        for path in (
            ci_dir / "bootstrap_strict_ci_runtime.sh",
            bin_dir / "uv",
            bin_dir / "uname",
            bin_dir / "npm",
            bin_dir / "node",
        ):
            path.chmod(0o755)

        broken_node_modules = runtime_web_dir / "node_modules"
        (broken_node_modules / ".bin").mkdir(parents=True)
        (broken_node_modules / "eslint").mkdir(parents=True)
        (broken_node_modules / ".bin" / "eslint").write_text("", encoding="utf-8")
        (broken_node_modules / "eslint" / "package.json").write_text("{}", encoding="utf-8")

        web_hash = subprocess.check_output(
            [
                "python3",
                "-c",
                (
                    "import hashlib, pathlib; "
                    "lock=pathlib.Path('apps/web/package-lock.json').read_text(encoding='utf-8'); "
                    "pkg=pathlib.Path('apps/web/package.json').read_text(encoding='utf-8'); "
                    "payload=''.join([hashlib.sha256(lock.encode()).hexdigest()+'  apps/web/package-lock.json\\n', "
                    "hashlib.sha256(pkg.encode()).hexdigest()+'  apps/web/package.json\\n', 'Linux-x86_64\\n']); "
                    "print(hashlib.sha256(payload.encode()).hexdigest())"
                ),
            ],
            cwd=repo_root,
            text=True,
        ).strip()
        (cache_dir / "web-Linux-x86_64.sha256").write_text(web_hash, encoding="utf-8")

        npm_log = repo_root / "npm.log"
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        env["NPM_LOG"] = str(npm_log)

        result = subprocess.run(
            ["bash", str(ci_dir / "bootstrap_strict_ci_runtime.sh")],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert (runtime_web_dir / "node_modules").is_dir()
