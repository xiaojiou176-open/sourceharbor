from __future__ import annotations

import os
import socket
import socketserver
import subprocess
import tempfile
import threading
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _choose_free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_ci_api_real_smoke_script(*, database_url: str | None) -> subprocess.CompletedProcess[str]:
    source = (_repo_root() / "scripts" / "ci" / "api_real_smoke.sh").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        scripts_runtime_dir = scripts_dir / "runtime"
        scripts_ci_dir = scripts_dir / "ci"
        bin_dir = repo_root / "bin"
        scripts_dir.mkdir()
        scripts_runtime_dir.mkdir()
        scripts_ci_dir.mkdir()
        bin_dir.mkdir()

        (scripts_ci_dir / "api_real_smoke.sh").write_text(source, encoding="utf-8")
        (scripts_runtime_dir / "logging.sh").write_text(
            (_repo_root() / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (scripts_runtime_dir / "log_jsonl_event.py").write_text(
            (_repo_root() / "scripts" / "runtime" / "log_jsonl_event.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (scripts_ci_dir / "api_real_smoke_local.sh").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'DATABASE_URL=%s\\n' \"${DATABASE_URL:-}\"\n"
            "printf 'API_INTEGRATION_SMOKE_STRICT=%s\\n' \"${API_INTEGRATION_SMOKE_STRICT:-}\"\n",
            encoding="utf-8",
        )
        (bin_dir / "uv").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
            encoding="utf-8",
        )

        for path in (
            scripts_ci_dir / "api_real_smoke_local.sh",
            scripts_runtime_dir / "log_jsonl_event.py",
            scripts_runtime_dir / "logging.sh",
            scripts_ci_dir / "api_real_smoke.sh",
            bin_dir / "uv",
        ):
            path.chmod(0o755)

        env = {
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        }
        if database_url is not None:
            env["DATABASE_URL"] = database_url

        return subprocess.run(
            ["bash", str(scripts_ci_dir / "api_real_smoke.sh")],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


def _run_ci_api_real_smoke_temporal_bootstrap(
    *,
    temporal_target_host: str | None,
    existing_temporal: bool,
) -> subprocess.CompletedProcess[str]:
    source = (_repo_root() / "scripts" / "ci" / "api_real_smoke.sh").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        scripts_runtime_dir = scripts_dir / "runtime"
        scripts_ci_dir = scripts_dir / "ci"
        bin_dir = repo_root / "bin"
        scripts_dir.mkdir()
        scripts_runtime_dir.mkdir()
        scripts_ci_dir.mkdir()
        bin_dir.mkdir()

        (scripts_ci_dir / "api_real_smoke.sh").write_text(source, encoding="utf-8")
        (scripts_runtime_dir / "logging.sh").write_text(
            (_repo_root() / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (scripts_runtime_dir / "log_jsonl_event.py").write_text(
            (_repo_root() / "scripts" / "runtime" / "log_jsonl_event.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (scripts_ci_dir / "api_real_smoke_local.sh").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'TEMPORAL_TARGET_HOST=%s\\n' \"${TEMPORAL_TARGET_HOST:-}\"\n",
            encoding="utf-8",
        )
        (bin_dir / "uv").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
            encoding="utf-8",
        )
        (bin_dir / "temporal").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'printf \'temporal %s\\n\' "$*" >> "${TEMPORAL_INVOCATIONS_LOG:?}"\n'
            "if [[ \"${1:-}\" == 'server' && \"${2:-}\" == 'start-dev' ]]; then\n"
            "  exec python3 - \"$@\" <<'PY'\n"
            "import socket\n"
            "import sys\n"
            "\n"
            "port = 7233\n"
            "args = sys.argv[1:]\n"
            "for index, value in enumerate(args):\n"
            "    if value == '--port' and index + 1 < len(args):\n"
            "        port = int(args[index + 1])\n"
            "sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
            "sock.bind(('127.0.0.1', port))\n"
            "sock.listen(1)\n"
            "try:\n"
            "    while True:\n"
            "        conn, _ = sock.accept()\n"
            "        conn.close()\n"
            "except KeyboardInterrupt:\n"
            "    pass\n"
            "PY\n"
            "fi\n",
            encoding="utf-8",
        )

        for path in (
            scripts_ci_dir / "api_real_smoke_local.sh",
            scripts_runtime_dir / "log_jsonl_event.py",
            scripts_runtime_dir / "logging.sh",
            scripts_ci_dir / "api_real_smoke.sh",
            bin_dir / "uv",
            bin_dir / "temporal",
        ):
            path.chmod(0o755)

        env = {
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
            "TEMPORAL_INVOCATIONS_LOG": str(repo_root / "temporal-invocations.log"),
        }
        if temporal_target_host is not None:
            env["TEMPORAL_TARGET_HOST"] = temporal_target_host

        server: socketserver.TCPServer | None = None
        if existing_temporal:
            host, port_text = (temporal_target_host or "127.0.0.1:7233").rsplit(":", 1)
            server = socketserver.TCPServer((host, int(port_text)), socketserver.BaseRequestHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()

        try:
            return subprocess.run(
                ["bash", str(scripts_ci_dir / "api_real_smoke.sh")],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()


def _run_strict_ci_api_real_smoke_entry(
    *,
    database_url: str | None,
    temporal_target_host: str | None,
    run_inside_child_process: bool = False,
) -> subprocess.CompletedProcess[str]:
    strict_entry_wrapper = (_repo_root() / "scripts" / "strict_ci_entry.sh").read_text(
        encoding="utf-8"
    )
    strict_entry_source = (_repo_root() / "scripts" / "ci" / "strict_entry.sh").read_text(
        encoding="utf-8"
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        scripts_ci_dir = scripts_dir / "ci"
        scripts_runtime_dir = scripts_dir / "runtime"
        scripts_dir.mkdir()
        scripts_ci_dir.mkdir()
        scripts_runtime_dir.mkdir()

        (scripts_dir / "strict_ci_entry.sh").write_text(strict_entry_wrapper, encoding="utf-8")
        (scripts_ci_dir / "strict_entry.sh").write_text(strict_entry_source, encoding="utf-8")
        (scripts_runtime_dir / "logging.sh").write_text(
            (_repo_root() / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (scripts_runtime_dir / "log_jsonl_event.py").write_text(
            (_repo_root() / "scripts" / "runtime" / "log_jsonl_event.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (scripts_ci_dir / "contract.py").write_text(
            "import sys\n"
            "if sys.argv[1:] == ['shell-exports']:\n"
            "    print('export STRICT_CI_STANDARD_IMAGE_REF=test-image')\n"
            "    print('export STRICT_CI_STANDARD_IMAGE_DOCKERFILE=Dockerfile')\n"
            "    print('export STRICT_CI_STANDARD_IMAGE_WORKDIR=/workspace')\n"
            "    print('export STRICT_CI_PLAYWRIGHT_BROWSERS_PATH=/tmp/playwright')\n"
            "    print('export STRICT_CI_UV_CACHE_DIR=/tmp/uv-cache')\n",
            encoding="utf-8",
        )
        if run_inside_child_process:
            (scripts_ci_dir / "bootstrap_strict_ci_runtime.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                'export TEMPORAL_TARGET_HOST="${TEMPORAL_TARGET_HOST:-127.0.0.1:7233}"\n',
                encoding="utf-8",
            )
            (scripts_ci_dir / "api_real_smoke.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'DATABASE_URL=%s\\n' \"${DATABASE_URL:-}\"\n"
                "printf 'TEMPORAL_TARGET_HOST=%s\\n' \"${TEMPORAL_TARGET_HOST:-}\"\n",
                encoding="utf-8",
            )
            (scripts_ci_dir / "run_in_standard_env.sh").write_text(
                '#!/usr/bin/env bash\nset -euo pipefail\nexec "$@"\n',
                encoding="utf-8",
            )
        else:
            (scripts_ci_dir / "run_in_standard_env.sh").write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "printf 'DATABASE_URL=%s\\n' \"${DATABASE_URL:-}\"\n"
                "printf 'TEMPORAL_TARGET_HOST=%s\\n' \"${TEMPORAL_TARGET_HOST:-}\"\n",
                encoding="utf-8",
            )

        executable_paths = [
            scripts_dir / "strict_ci_entry.sh",
            scripts_ci_dir / "strict_entry.sh",
            scripts_ci_dir / "run_in_standard_env.sh",
            scripts_runtime_dir / "logging.sh",
            scripts_runtime_dir / "log_jsonl_event.py",
            scripts_ci_dir / "contract.py",
        ]
        if run_inside_child_process:
            executable_paths.extend(
                [
                    scripts_ci_dir / "bootstrap_strict_ci_runtime.sh",
                    scripts_ci_dir / "api_real_smoke.sh",
                ]
            )

        for path in executable_paths:
            path.chmod(0o755)

        env = {"PATH": os.environ.get("PATH", "")}
        if database_url is not None:
            env["DATABASE_URL"] = database_url
        if temporal_target_host is not None:
            env["TEMPORAL_TARGET_HOST"] = temporal_target_host

        return subprocess.run(
            ["bash", str(scripts_dir / "strict_ci_entry.sh"), "--mode", "api-real-smoke"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )


def test_api_real_smoke_script_enforces_real_postgres_and_strict_mode() -> None:
    script = (_repo_root() / "scripts" / "ci" / "api_real_smoke_local.sh").read_text(
        encoding="utf-8"
    )

    assert 'driver_name" != "postgresql+psycopg"' in script
    assert "creating isolated smoke database" in script
    assert "CREATE DATABASE" in script
    assert "DROP DATABASE IF EXISTS" in script
    assert 'API_INTEGRATION_SMOKE_STRICT="1"' in script
    assert "uv run pytest apps/api/tests/test_api_integration_smoke.py -q -rA" in script
    assert "workflow-closure-timeout-seconds" in script
    assert "/api/v1/workflows/run" in script
    assert '"workflow": "cleanup"' in script
    assert '"wait_for_result": True' in script
    assert '"workflow_name"] == "CleanupWorkspaceWorkflow"' in script
    assert "api -> temporal -> worker cleanup workflow closure probe passed" in script
    assert 'SMOKE_WRITE_TOKEN="${SOURCE_HARBOR_API_KEY:-sourceharbor-local-dev-token}"' in script
    assert 'export SOURCE_HARBOR_API_KEY="${SOURCE_HARBOR_API_KEY:-$SMOKE_WRITE_TOKEN}"' in script
    assert (
        'export WEB_ACTION_SESSION_TOKEN="${WEB_ACTION_SESSION_TOKEN:-$SMOKE_WRITE_TOKEN}"'
        in script
    )
    assert 'local write_token="${SMOKE_WRITE_TOKEN}"' in script
    assert 'API_PORT_EXPLICIT="0"' in script
    assert "choose_available_api_port" in script
    assert "using fallback port" in script
    assert "starting temporary worker for cleanup workflow probe" in script
    assert "./scripts/dev_worker.sh --no-show-hints" in script
    assert (
        "export DATABASE_URL TEMPORAL_TARGET_HOST TEMPORAL_NAMESPACE TEMPORAL_TASK_QUEUE" in script
    )
    assert (
        "export SQLITE_STATE_PATH UI_AUDIT_GEMINI_ENABLED NOTIFICATION_ENABLED SOURCE_HARBOR_ALLOW_UNAUTH_WRITE PYTHONPATH"
        in script
    )
    assert "temporary worker exited before cleanup workflow probe" in script
    assert "describe_task_queue" in script
    assert "TASK_QUEUE_TYPE_WORKFLOW" in script
    assert "TASK_QUEUE_TYPE_ACTIVITY" in script
    assert "detected existing temporal worker pollers on task queue" in script
    assert "timed out waiting for worker pollers on task queue" in script
    assert "temporal_server_is_reachable()" in script
    assert "ensure_temporal_server_online()" in script
    assert "starting temporary temporal dev server inside standard env" in script
    assert "temporary temporal dev server is online" in script
    assert "temporary temporal dev server exited before reaching readiness" in script
    assert "timed out waiting for temporal server readiness" in script
    assert "temporal server start-dev --ip 127.0.0.1 --port 7233" in script
    assert "preflight_loopback_ipv4_connectivity" in script
    assert "host_loopback_ipv4_exhausted" in script
    assert "EADDRNOTAVAIL (Errno 49)" in script
    assert "unset SOURCE_HARBOR_API_KEY" not in script
    assert "unset WEB_ACTION_SESSION_TOKEN" not in script


def test_api_real_smoke_script_can_run_inside_standard_env_without_host_specific_bootstrap() -> (
    None
):
    script = (_repo_root() / "scripts" / "ci" / "api_real_smoke_local.sh").read_text(
        encoding="utf-8"
    )

    assert "run_in_standard_env.sh" not in script
    assert 'SOURCE_HARBOR_IN_STANDARD_ENV="${SOURCE_HARBOR_IN_STANDARD_ENV:-0}"' in script
    assert 'if [[ "$SOURCE_HARBOR_IN_STANDARD_ENV" != "1" ]]; then' in script
    assert "preflight_loopback_ipv4_connectivity" in script


def test_ci_api_real_smoke_script_replaces_bootstrap_sqlite_default_with_postgres() -> None:
    result = _run_ci_api_real_smoke_script(database_url="sqlite+pysqlite:///:memory:")

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
        in result.stdout
    )
    assert "API_INTEGRATION_SMOKE_STRICT=1" in result.stdout


def test_ci_api_real_smoke_script_preserves_explicit_non_sqlite_database_url() -> None:
    result = _run_ci_api_real_smoke_script(
        database_url="postgresql+psycopg://postgres:postgres@db.internal:5432/sourceharbor_ci"
    )

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@db.internal:5432/sourceharbor_ci"
        in result.stdout
    )


def test_ci_api_real_smoke_script_bootstraps_local_temporal_when_missing() -> None:
    port = _choose_free_tcp_port()
    result = _run_ci_api_real_smoke_temporal_bootstrap(
        temporal_target_host=f"127.0.0.1:{port}",
        existing_temporal=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"TEMPORAL_TARGET_HOST=127.0.0.1:{port}" in result.stdout
    assert f"starting local Temporal dev server at 127.0.0.1:{port}" in result.stderr


def test_ci_api_real_smoke_script_normalizes_bootstrapped_host_docker_internal_temporal_target() -> (
    None
):
    port = _choose_free_tcp_port()
    result = _run_ci_api_real_smoke_temporal_bootstrap(
        temporal_target_host=f"host.docker.internal:{port}",
        existing_temporal=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"TEMPORAL_TARGET_HOST=127.0.0.1:{port}" in result.stdout
    assert f"starting local Temporal dev server at host.docker.internal:{port}" in result.stderr


def test_ci_api_real_smoke_script_reuses_existing_local_temporal_listener() -> None:
    port = _choose_free_tcp_port()
    result = _run_ci_api_real_smoke_temporal_bootstrap(
        temporal_target_host=f"127.0.0.1:{port}",
        existing_temporal=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"reusing existing Temporal listener at 127.0.0.1:{port}" in result.stderr
    assert "starting local Temporal dev server" not in result.stderr


def test_ci_api_real_smoke_script_skips_bootstrap_for_non_local_temporal_target() -> None:
    result = _run_ci_api_real_smoke_temporal_bootstrap(
        temporal_target_host="temporal.internal:7233",
        existing_temporal=False,
    )

    assert result.returncode == 0, result.stderr
    assert "TEMPORAL_TARGET_HOST=temporal.internal:7233" in result.stdout
    assert (
        "skipping Temporal dev bootstrap for non-local target temporal.internal:7233"
        in result.stderr
    )


def test_strict_ci_entry_injects_api_real_smoke_postgres_default_before_standard_env() -> None:
    result = _run_strict_ci_api_real_smoke_entry(
        database_url="sqlite+pysqlite:///:memory:",
        temporal_target_host=None,
    )

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
        in result.stdout
    )


def test_strict_ci_entry_preserves_explicit_api_real_smoke_postgres_before_standard_env() -> None:
    result = _run_strict_ci_api_real_smoke_entry(
        database_url="postgresql+psycopg://postgres:postgres@db.internal:5432/sourceharbor_ci",
        temporal_target_host=None,
    )

    assert result.returncode == 0, result.stderr
    assert (
        "DATABASE_URL=postgresql+psycopg://postgres:postgres@db.internal:5432/sourceharbor_ci"
        in result.stdout
    )


def test_strict_ci_entry_injects_api_real_smoke_temporal_target_host_before_standard_env() -> None:
    result = _run_strict_ci_api_real_smoke_entry(
        database_url=None,
        temporal_target_host=None,
    )

    assert result.returncode == 0, result.stderr
    assert "TEMPORAL_TARGET_HOST=127.0.0.1:7233" in result.stdout


def test_strict_ci_entry_preserves_explicit_api_real_smoke_temporal_target_host_before_standard_env() -> (
    None
):
    result = _run_strict_ci_api_real_smoke_entry(
        database_url=None,
        temporal_target_host="temporal.internal:7233",
    )

    assert result.returncode == 0, result.stderr
    assert "TEMPORAL_TARGET_HOST=temporal.internal:7233" in result.stdout


def test_strict_ci_entry_exports_api_real_smoke_temporal_target_host_to_standard_env_child_process() -> (
    None
):
    result = _run_strict_ci_api_real_smoke_entry(
        database_url=None,
        temporal_target_host="temporal.internal:7233",
        run_inside_child_process=True,
    )

    assert result.returncode == 0, result.stderr
    assert "TEMPORAL_TARGET_HOST=temporal.internal:7233" in result.stdout


def test_strict_ci_entry_injects_web_e2e_postgres_default_before_standard_env() -> None:
    strict_entry_wrapper = (_repo_root() / "scripts" / "strict_ci_entry.sh").read_text(
        encoding="utf-8"
    )
    strict_entry_source = (_repo_root() / "scripts" / "ci" / "strict_entry.sh").read_text(
        encoding="utf-8"
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        scripts_dir = repo_root / "scripts"
        scripts_ci_dir = scripts_dir / "ci"
        scripts_runtime_dir = scripts_dir / "runtime"
        scripts_dir.mkdir()
        scripts_ci_dir.mkdir()
        scripts_runtime_dir.mkdir()

        (scripts_dir / "strict_ci_entry.sh").write_text(strict_entry_wrapper, encoding="utf-8")
        (scripts_ci_dir / "strict_entry.sh").write_text(strict_entry_source, encoding="utf-8")
        (scripts_runtime_dir / "logging.sh").write_text(
            (_repo_root() / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (scripts_runtime_dir / "log_jsonl_event.py").write_text(
            (_repo_root() / "scripts" / "runtime" / "log_jsonl_event.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (scripts_ci_dir / "contract.py").write_text(
            "import sys\n"
            "if sys.argv[1:] == ['shell-exports']:\n"
            "    print('export STRICT_CI_STANDARD_IMAGE_REF=test-image')\n"
            "    print('export STRICT_CI_STANDARD_IMAGE_DOCKERFILE=Dockerfile')\n"
            "    print('export STRICT_CI_STANDARD_IMAGE_WORKDIR=/workspace')\n"
            "    print('export STRICT_CI_PLAYWRIGHT_BROWSERS_PATH=/tmp/playwright')\n"
            "    print('export STRICT_CI_UV_CACHE_DIR=/tmp/uv-cache')\n",
            encoding="utf-8",
        )
        (scripts_ci_dir / "run_in_standard_env.sh").write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "printf 'DATABASE_URL=%s\\n' \"${DATABASE_URL:-}\"\n",
            encoding="utf-8",
        )
        for path in (
            scripts_dir / "strict_ci_entry.sh",
            scripts_ci_dir / "strict_entry.sh",
            scripts_ci_dir / "run_in_standard_env.sh",
            scripts_runtime_dir / "logging.sh",
            scripts_runtime_dir / "log_jsonl_event.py",
            scripts_ci_dir / "contract.py",
        ):
            path.chmod(0o755)

        result = subprocess.run(
            ["bash", str(scripts_dir / "strict_ci_entry.sh"), "--mode", "web-e2e"],
            cwd=repo_root,
            env={"PATH": os.environ.get("PATH", ""), "DATABASE_URL": "sqlite+pysqlite:///:memory:"},
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert (
            "DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
            in result.stdout
        )


def test_strict_ci_entry_marks_debug_build_as_diagnostic_only() -> None:
    strict_entry = (_repo_root() / "scripts" / "ci" / "strict_entry.sh").read_text(encoding="utf-8")

    assert (
        'sourceharbor_log info strict_ci_entry_diagnostic_mode "using debug-build diagnostic path"'
        in strict_entry
    )
    assert (
        'sourceharbor_log info strict_ci_entry_release_qualifying "using pinned-image release-qualifying path"'
        in strict_entry
    )
