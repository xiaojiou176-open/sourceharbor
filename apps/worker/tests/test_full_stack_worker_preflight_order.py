from __future__ import annotations

import os
import socket
import socketserver
import subprocess
import threading
import time
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


def _prepare_full_stack_script(tmp_path: Path) -> Path:
    root = _repo_root()
    target_script_dir = tmp_path / "scripts"
    target_lib_dir = target_script_dir / "lib"
    target_runtime_dir = target_script_dir / "runtime"
    target_lib_dir.mkdir(parents=True, exist_ok=True)
    target_runtime_dir.mkdir(parents=True, exist_ok=True)

    full_stack_target = target_script_dir / "full_stack.sh"
    runtime_full_stack_target = target_runtime_dir / "full_stack.sh"
    full_stack_target.write_text(
        (root / "scripts" / "full_stack.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    runtime_full_stack_target.write_text(
        (root / "scripts" / "runtime" / "full_stack.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_lib_dir / "load_env.sh").write_text(
        (root / "scripts" / "lib" / "load_env.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_lib_dir / "temporal_ready.sh").write_text(
        (root / "scripts" / "lib" / "temporal_ready.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_runtime_dir / "logging.sh").write_text(
        (root / "scripts" / "runtime" / "logging.sh").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (target_runtime_dir / "log_jsonl_event.py").write_text(
        (root / "scripts" / "runtime" / "log_jsonl_event.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    full_stack_target.chmod(0o755)
    runtime_full_stack_target.chmod(0o755)
    return full_stack_target


def _wait_for_tcp_ready(port: int, *, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise AssertionError(f"temporary TCP server on port {port} did not become ready")


def _wait_for_path_absent(path: Path, *, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not path.exists():
            return
        time.sleep(0.05)
    raise AssertionError(f"path still exists after timeout: {path}")


def test_full_stack_up_fails_temporal_reachability_preflight_before_any_service_start(
    tmp_path: Path,
) -> None:
    full_stack_target = _prepare_full_stack_script(tmp_path)
    proc = _run_bash(
        f'"{full_stack_target}" up',
        cwd=tmp_path,
        env={
            "SQLITE_PATH": str(tmp_path / "state.sqlite3"),
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "TEMPORAL_TARGET_HOST": "127.0.0.1:1",
            "TEMPORAL_NAMESPACE": "default",
            "TEMPORAL_TASK_QUEUE": "video-analysis",
            "PIPELINE_WORKSPACE_DIR": str(tmp_path / "workspace"),
            "PIPELINE_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        },
    )

    assert proc.returncode != 0
    assert "DIAGNOSE stage=worker_preflight_temporal conclusion=temporal_not_ready" in proc.stderr

    api_pid = tmp_path / ".runtime-cache" / "run" / "full-stack" / "api.pid"
    api_log = tmp_path / "logs" / "full-stack" / "api.log"
    last_failure_reason = tmp_path / ".runtime-cache" / "run" / "full-stack" / "last_failure_reason"

    assert not api_pid.exists()
    assert not api_log.exists()
    assert last_failure_reason.exists()
    failure_text = last_failure_reason.read_text(encoding="utf-8")
    assert "stage=worker_preflight_temporal" in failure_text
    assert "conclusion=temporal_not_ready" in failure_text


def test_full_stack_up_records_temporal_preflight_failure_before_service_start(
    tmp_path: Path,
) -> None:
    full_stack_target = _prepare_full_stack_script(tmp_path)
    proc = _run_bash(
        f'"{full_stack_target}" up',
        cwd=tmp_path,
        env={
            "SQLITE_PATH": str(tmp_path / "state.sqlite3"),
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "TEMPORAL_TARGET_HOST": "temporal-invalid-target",
            "TEMPORAL_NAMESPACE": "default",
            "TEMPORAL_TASK_QUEUE": "video-analysis",
            "PIPELINE_WORKSPACE_DIR": str(tmp_path / "workspace"),
            "PIPELINE_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        },
    )

    assert proc.returncode != 0
    assert (
        "DIAGNOSE stage=worker_preflight_temporal conclusion=invalid_temporal_target_host"
        in proc.stderr
    )

    api_pid = tmp_path / ".runtime-cache" / "run" / "full-stack" / "api.pid"
    api_log = tmp_path / "logs" / "full-stack" / "api.log"
    last_failure_reason = tmp_path / ".runtime-cache" / "run" / "full-stack" / "last_failure_reason"

    assert not api_pid.exists()
    assert not api_log.exists()
    assert last_failure_reason.exists()
    failure_text = last_failure_reason.read_text(encoding="utf-8")
    assert "stage=worker_preflight_temporal" in failure_text
    assert "conclusion=temporal_not_ready" in failure_text


def test_full_stack_down_attempts_repo_owned_core_services_cleanup(tmp_path: Path) -> None:
    full_stack_target = _prepare_full_stack_script(tmp_path)
    deploy_dir = tmp_path / "scripts" / "deploy"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    calls_log = tmp_path / "core-services-calls.log"

    (deploy_dir / "core_services.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$FULL_STACK_CORE_SERVICES_CALLS_LOG"
""",
        encoding="utf-8",
    )
    (deploy_dir / "core_services.sh").chmod(0o755)

    proc = _run_bash(
        f'"{full_stack_target}" down',
        cwd=tmp_path,
        env={"FULL_STACK_CORE_SERVICES_CALLS_LOG": str(calls_log)},
    )

    assert proc.returncode == 0, proc.stderr
    assert calls_log.exists()
    assert calls_log.read_text(encoding="utf-8").strip() == f"down --env-file {tmp_path / '.env'}"


def test_full_stack_up_attempts_self_heal_for_unhealthy_temporal_namespace_before_fail_close(
    tmp_path: Path,
) -> None:
    full_stack_target = _prepare_full_stack_script(tmp_path)
    scripts_dir = tmp_path / "scripts"
    deploy_dir = scripts_dir / "deploy"
    web_bin_dir = tmp_path / "apps" / "web" / "node_modules" / ".bin"
    fake_bin_dir = tmp_path / "fake-bin"
    worker_signature_regex = f"worker\\.main run-worker {tmp_path.name}"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    deploy_dir.mkdir(parents=True, exist_ok=True)
    web_bin_dir.mkdir(parents=True, exist_ok=True)
    fake_bin_dir.mkdir(parents=True, exist_ok=True)

    runtime_full_stack_target = scripts_dir / "runtime" / "full_stack.sh"
    runtime_full_stack_target.write_text(
        runtime_full_stack_target.read_text(encoding="utf-8").replace(
            "(worker\\.main run-worker|scripts/dev_worker\\.sh)",
            f"({worker_signature_regex})",
        ),
        encoding="utf-8",
    )

    (scripts_dir / "dev_api.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ["API_PORT"])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        return


HTTPServer(("127.0.0.1", port), Handler).serve_forever()
PY
""",
        encoding="utf-8",
    )
    (scripts_dir / "dev_worker.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 1\n",
        encoding="utf-8",
    )
    (deploy_dir / "core_services.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "up" ]]; then
  : > "${FULL_STACK_TEMPORAL_HEALTH_MARKER}"
fi
""",
        encoding="utf-8",
    )
    (web_bin_dir / "next").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
port="3000"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      port="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
python3 - "$port" <<'PY'
import socket
import sys
import time

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", int(sys.argv[1])))
sock.listen()
while True:
    time.sleep(1)
PY
""",
        encoding="utf-8",
    )
    (fake_bin_dir / "temporal").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "operator" && "${2:-}" == "namespace" && "${3:-}" == "describe" ]]; then
  if [[ -f "${FULL_STACK_TEMPORAL_HEALTH_MARKER}" ]]; then
    exit 0
  fi
  exit 1
fi
exit 0
""",
        encoding="utf-8",
    )
    (fake_bin_dir / "uv").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
        encoding="utf-8",
    )
    for path in (
        scripts_dir / "dev_api.sh",
        scripts_dir / "dev_worker.sh",
        deploy_dir / "core_services.sh",
        web_bin_dir / "next",
        fake_bin_dir / "temporal",
        fake_bin_dir / "uv",
    ):
        path.chmod(0o755)

    marker = tmp_path / "core-services-self-healed"
    base_env = {
        "PATH": f"{fake_bin_dir}:{os.environ['PATH']}",
        "API_PORT": "19100",
        "WEB_PORT": "19101",
        "SQLITE_PATH": str(tmp_path / "state.sqlite3"),
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "TEMPORAL_NAMESPACE": "default",
        "TEMPORAL_TASK_QUEUE": "video-analysis",
        "PIPELINE_WORKSPACE_DIR": str(tmp_path / "workspace"),
        "PIPELINE_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        "FULL_STACK_TEMPORAL_HEALTH_MARKER": str(marker),
    }

    class _SilentHandler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            return

    with socketserver.TCPServer(("127.0.0.1", 0), _SilentHandler) as temporal_server:
        temporal_port = temporal_server.server_address[1]
        temporal_thread = threading.Thread(
            target=temporal_server.serve_forever,
            daemon=True,
        )
        temporal_thread.start()
        _wait_for_tcp_ready(temporal_port)
        env = {**base_env, "TEMPORAL_TARGET_HOST": f"127.0.0.1:{temporal_port}"}
        try:
            proc = _run_bash(
                f'"{full_stack_target}" up',
                cwd=tmp_path,
                env=env,
            )
        finally:
            _run_bash(
                f'"{full_stack_target}" down',
                cwd=tmp_path,
                env=env,
            )
            temporal_server.shutdown()
            temporal_thread.join(timeout=5)

    assert proc.returncode != 0, proc.stderr
    assert marker.exists()
    assert "attempting_core_services_self_heal" in proc.stderr
    assert (
        "DIAGNOSE stage=worker_start_retry" in proc.stderr
        or "DIAGNOSE stage=worker_start conclusion=worker_failed_to_start" in proc.stderr
        or "DIAGNOSE stage=worker_start conclusion=worker_process_not_detected" in proc.stderr
    )


def test_full_stack_up_waits_for_worker_temporal_pollers_after_worker_start(
    tmp_path: Path,
) -> None:
    full_stack_target = _prepare_full_stack_script(tmp_path)
    scripts_dir = tmp_path / "scripts"
    web_bin_dir = tmp_path / "apps" / "web" / "node_modules" / ".bin"
    fake_bin_dir = tmp_path / "fake-bin"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    web_bin_dir.mkdir(parents=True, exist_ok=True)
    fake_bin_dir.mkdir(parents=True, exist_ok=True)

    (scripts_dir / "dev_api.sh").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
python3 - "$@" <<'PY'
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

port = int(os.environ["API_PORT"])

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A003
        return

HTTPServer(("127.0.0.1", port), Handler).serve_forever()
PY
""",
        encoding="utf-8",
    )
    (scripts_dir / "dev_worker.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nsleep 300\n",
        encoding="utf-8",
    )
    (web_bin_dir / "next").write_text(
        """#!/usr/bin/env bash
set -euo pipefail
port="3000"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      port="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done
python3 - "$port" <<'PY'
import socket
import sys
import time

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("127.0.0.1", int(sys.argv[1])))
sock.listen()
while True:
    time.sleep(1)
PY
""",
        encoding="utf-8",
    )
    (fake_bin_dir / "uv").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nexit "${TEMPORAL_READY_PROBE_EXIT_CODE:-1}"\n',
        encoding="utf-8",
    )
    for path in (
        scripts_dir / "dev_api.sh",
        scripts_dir / "dev_worker.sh",
        web_bin_dir / "next",
        fake_bin_dir / "uv",
    ):
        path.chmod(0o755)

    class _SilentHandler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            return

    with socketserver.TCPServer(("127.0.0.1", 0), _SilentHandler) as temporal_server:
        temporal_port = temporal_server.server_address[1]
        temporal_thread = threading.Thread(
            target=temporal_server.serve_forever,
            daemon=True,
        )
        temporal_thread.start()
        _wait_for_tcp_ready(temporal_port)
        try:
            proc = _run_bash(
                f'"{full_stack_target}" up',
                cwd=tmp_path,
                env={
                    "PATH": f"{fake_bin_dir}:{os.environ['PATH']}",
                    "API_PORT": "19000",
                    "WEB_PORT": "19001",
                    "SQLITE_PATH": str(tmp_path / "state.sqlite3"),
                    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
                    "TEMPORAL_TARGET_HOST": f"127.0.0.1:{temporal_port}",
                    "TEMPORAL_NAMESPACE": "default",
                    "TEMPORAL_TASK_QUEUE": "video-analysis",
                    "PIPELINE_WORKSPACE_DIR": str(tmp_path / "workspace"),
                    "PIPELINE_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
                    "FULL_STACK_TEMPORAL_POLLER_READY_TIMEOUT_SECONDS": "1",
                    "TEMPORAL_READY_PROBE_EXIT_CODE": "1",
                },
            )
        finally:
            temporal_server.shutdown()
            temporal_thread.join(timeout=5)

    assert proc.returncode != 0
    assert (
        "DIAGNOSE stage=worker_temporal_pollers conclusion=pollers_not_ready" in proc.stderr
        or "DIAGNOSE stage=worker_preflight_temporal conclusion=temporal_not_ready" in proc.stderr
        or "DIAGNOSE stage=worker_start_retry" in proc.stderr
    )

    worker_pid = tmp_path / ".runtime-cache" / "run" / "full-stack" / "worker.pid"
    last_failure_reason = tmp_path / ".runtime-cache" / "run" / "full-stack" / "last_failure_reason"

    _wait_for_path_absent(worker_pid)
    if last_failure_reason.exists():
        failure_text = last_failure_reason.read_text(encoding="utf-8")
        assert (
            (
                "stage=worker_temporal_pollers" in failure_text
                and "conclusion=pollers_not_ready" in failure_text
            )
            or (
                "stage=worker_preflight_temporal" in failure_text
                and "conclusion=temporal_not_ready" in failure_text
            )
            or (
                "stage=worker_start" in failure_text
                and "conclusion=worker_failed_to_start" in failure_text
            )
        )
    else:
        assert "DIAGNOSE stage=worker_start_retry" in proc.stderr
