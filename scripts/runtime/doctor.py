#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.runtime.disk_space_common import load_policy
from scripts.runtime.report_disk_space import build_disk_governance_operator_summary

RESOLVED_ENV_PATH = ROOT / ".runtime-cache" / "run" / "full-stack" / "resolved.env"
CANONICAL_CORE_POSTGRES_PORT = "15432"
CANONICAL_API_HEALTH = "http://127.0.0.1:9000/healthz"


@dataclass
class DoctorCheck:
    check_id: str
    title: str
    status: str
    summary: str
    next_step: str
    details: dict[str, object] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SourceHarbor first-run doctor")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser.parse_args()


def read_resolved_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    resolved: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        resolved[key.strip()] = value.strip().strip('"').strip("'")
    return resolved


def run_command(*command: str) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def parse_status_output(output: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        key = left.strip().lower()
        if key in {"api", "worker", "web", "mcp"}:
            states[key] = right.strip()
    return states


def check_env_contract() -> DoctorCheck:
    code, stdout, stderr = run_command(
        "python3", "scripts/governance/check_env_contract.py", "--strict"
    )
    if code == 0:
        return DoctorCheck(
            check_id="env_contract",
            title="Environment contract",
            status="PASS",
            summary="The repo env contract and .env.example coverage are aligned.",
            next_step="None.",
            details={"exit_code": code, "output_tail": stdout.splitlines()[-1] if stdout else ""},
        )
    return DoctorCheck(
        check_id="env_contract",
        title="Environment contract",
        status="BLOCK",
        summary="The env contract is not aligned, so first-run cannot be trusted yet.",
        next_step="Fix the reported contract drift before treating bootstrap/full-stack as reliable.",
        details={"exit_code": code, "stderr": stderr or stdout},
    )


def evaluate_database_target(database_url: str, core_port: str, listener_5432: bool) -> DoctorCheck:
    if not database_url:
        return DoctorCheck(
            check_id="database_target",
            title="Database target",
            status="BLOCK",
            summary="DATABASE_URL is missing.",
            next_step="Set DATABASE_URL before retrying first-run.",
        )

    parsed = urlsplit(database_url)
    host = parsed.hostname or "127.0.0.1"
    port = str(parsed.port or "")
    scheme = parsed.scheme

    if scheme != "postgresql+psycopg":
        return DoctorCheck(
            check_id="database_target",
            title="Database target",
            status="BLOCK",
            summary="DATABASE_URL still uses the wrong driver dialect.",
            next_step="Use postgresql+psycopg://... so the local runtime and tests agree.",
            details={"scheme": scheme, "host": host, "port": port},
        )

    if host in {"127.0.0.1", "localhost"} and port == "5432":
        return DoctorCheck(
            check_id="database_target",
            title="Database target",
            status="BLOCK",
            summary="DATABASE_URL points at 127.0.0.1:5432, which reintroduces the host/container split-brain risk.",
            next_step=f"Switch DATABASE_URL to the container-first local port {core_port} before trusting first-run.",
            details={"scheme": scheme, "host": host, "port": port, "listener_5432": listener_5432},
        )

    if host in {"127.0.0.1", "localhost"} and port == core_port:
        return DoctorCheck(
            check_id="database_target",
            title="Database target",
            status="PASS",
            summary="DATABASE_URL is pointed at the container-first local Postgres path.",
            next_step="None.",
            details={"scheme": scheme, "host": host, "port": port, "listener_5432": listener_5432},
        )

    return DoctorCheck(
        check_id="database_target",
        title="Database target",
        status="WARN",
        summary="DATABASE_URL uses a custom target outside the default local container-first path.",
        next_step="Confirm this is intentional before treating local troubleshooting steps as canonical.",
        details={"scheme": scheme, "host": host, "port": port},
    )


def listener_exists(port: int) -> bool:
    code, stdout, _ = run_command("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN")
    return code == 0 and bool(stdout.strip())


def docker_port_mapping() -> str | None:
    code, stdout, _ = run_command("docker", "port", "sourceharbor-core-postgres", "5432/tcp")
    if code != 0 or not stdout.strip():
        return None
    return stdout.splitlines()[0].strip()


def check_postgres_reachability(database_url: str) -> DoctorCheck:
    parsed = urlsplit(database_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
    except OSError as exc:
        return DoctorCheck(
            check_id="postgres_reachability",
            title="Postgres reachability",
            status="BLOCK",
            summary=f"Postgres is not reachable on {host}:{port}.",
            next_step="Start the core services or fix DATABASE_URL before retrying.",
            details={"error": str(exc), "host": host, "port": port},
        )
    finally:
        sock.close()
    return DoctorCheck(
        check_id="postgres_reachability",
        title="Postgres reachability",
        status="PASS",
        summary=f"Postgres is reachable on {host}:{port}.",
        next_step="None.",
        details={"host": host, "port": port, "docker_port": docker_port_mapping()},
    )


def check_temporal(target_host: str) -> DoctorCheck:
    host, _, port_raw = target_host.partition(":")
    port = int(port_raw or "7233")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        sock.connect((host or "127.0.0.1", port))
    except OSError as exc:
        return DoctorCheck(
            check_id="temporal_reachability",
            title="Temporal reachability",
            status="BLOCK",
            summary=f"Temporal is not reachable on {host}:{port}.",
            next_step="Start core services and re-run ./bin/full-stack up before trusting worker readiness.",
            details={"error": str(exc), "target": target_host},
        )
    finally:
        sock.close()
    return DoctorCheck(
        check_id="temporal_reachability",
        title="Temporal reachability",
        status="PASS",
        summary=f"Temporal is reachable on {host}:{port}.",
        next_step="None.",
        details={"target": target_host},
    )


def check_runtime_snapshot(resolved_env: dict[str, str]) -> DoctorCheck:
    if not resolved_env:
        return DoctorCheck(
            check_id="runtime_snapshot",
            title="Runtime snapshot",
            status="WARN",
            summary="No resolved runtime snapshot is present yet.",
            next_step="Run ./bin/bootstrap-full-stack and ./bin/full-stack up to generate .runtime-cache/run/full-stack/resolved.env.",
            details={"path": str(RESOLVED_ENV_PATH)},
        )
    return DoctorCheck(
        check_id="runtime_snapshot",
        title="Runtime snapshot",
        status="PASS",
        summary="The repo-managed runtime snapshot exists and can be used as the local route truth.",
        next_step="None.",
        details={
            "path": str(RESOLVED_ENV_PATH),
            "api_port": resolved_env.get("API_PORT"),
            "web_port": resolved_env.get("WEB_PORT"),
            "database_url": resolved_env.get("DATABASE_URL"),
        },
    )


def check_full_stack_status() -> DoctorCheck:
    code, stdout, stderr = run_command("./bin/full-stack", "status")
    states = parse_status_output(stdout)
    if code != 0:
        return DoctorCheck(
            check_id="full_stack_status",
            title="Full-stack status",
            status="WARN",
            summary="full-stack status could not be read cleanly.",
            next_step="Inspect ./bin/full-stack status manually if runtime diagnosis remains unclear.",
            details={"exit_code": code, "stderr": stderr or stdout},
        )

    running = all(states.get(name, "").startswith("running") for name in ("api", "worker", "web"))
    if running:
        return DoctorCheck(
            check_id="full_stack_status",
            title="Full-stack status",
            status="PASS",
            summary="API, worker, and web are already running under the local full-stack supervisor.",
            next_step="None.",
            details=states,
        )

    return DoctorCheck(
        check_id="full_stack_status",
        title="Full-stack status",
        status="BLOCK",
        summary="The local stack is not fully running yet.",
        next_step="Run ./bin/full-stack up, then rerun doctor to confirm API, worker, and web are all ready.",
        details=states,
    )


def fetch_url(url: str) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=5.0) as response:  # noqa: S310
            status = getattr(response, "status", 200)
            return status == 200, f"http_{status}"
    except URLError as exc:
        return False, str(exc.reason)
    except OSError as exc:
        return False, str(exc)


def check_http_gate(*, url: str, title: str, next_step: str) -> DoctorCheck:
    ok, note = fetch_url(url)
    if ok:
        return DoctorCheck(
            check_id=title.lower().replace(" ", "_"),
            title=title,
            status="PASS",
            summary=f"{title} is responding at {url}.",
            next_step="None.",
            details={"url": url},
        )
    return DoctorCheck(
        check_id=title.lower().replace(" ", "_"),
        title=title,
        status="WARN",
        summary=f"{title} is not responding at {url}.",
        next_step=next_step,
        details={"url": url, "error": note},
    )


def check_write_token() -> DoctorCheck:
    token_present = bool((os.getenv("SOURCE_HARBOR_API_KEY") or "").strip())
    if token_present:
        return DoctorCheck(
            check_id="write_token",
            title="Write-route auth token",
            status="PASS",
            summary="A local write token is present in the current shell for curl-based API probes.",
            next_step="None.",
        )
    return DoctorCheck(
        check_id="write_token",
        title="Write-route auth token",
        status="WARN",
        summary="No SOURCE_HARBOR_API_KEY is exported in the current shell, so direct write-route curls will fail even if the stack is healthy.",
        next_step='Export SOURCE_HARBOR_API_KEY="${SOURCE_HARBOR_API_KEY:-sourceharbor-local-dev-token}" before probing write APIs from the shell.',
    )


def check_disk_governance() -> DoctorCheck:
    try:
        payload = build_disk_governance_operator_summary(ROOT, load_policy(ROOT))
    except (OSError, ValueError) as exc:
        return DoctorCheck(
            check_id="disk_governance",
            title="Disk governance",
            status="WARN",
            summary="Disk governance data could not be loaded cleanly for this run.",
            next_step="Run ./bin/disk-space-audit --json manually, then fix the reported policy/report-path issue before treating the disk governance gate as current truth.",
            details={"error": str(exc)},
        )
    status = str(payload.get("status") or "unavailable").upper()
    details = dict(payload.get("details") or {})
    if status not in {"PASS", "WARN", "BLOCK"}:
        status = "PASS" if str(payload.get("status") or "").lower() == "ready" else "WARN"
    return DoctorCheck(
        check_id="disk_governance",
        title="Disk governance",
        status=status,
        summary=str(payload.get("summary") or "Disk governance summary unavailable."),
        next_step=str(payload.get("next_step") or "Run ./bin/disk-space-audit --json manually."),
        details=details,
    )


def make_secret_gate(name: str, env_var: str, next_step: str) -> DoctorCheck:
    present = bool((os.getenv(env_var) or "").strip())
    if present:
        return DoctorCheck(
            check_id=env_var.lower(),
            title=name,
            status="PASS",
            summary=f"{env_var} is present.",
            next_step="None.",
        )
    return DoctorCheck(
        check_id=env_var.lower(),
        title=name,
        status="WARN",
        summary=f"{env_var} is missing, so this live validation lane is externally blocked.",
        next_step=next_step,
    )


def overall_status(checks: list[DoctorCheck]) -> str:
    if any(check.status == "BLOCK" for check in checks):
        return "BLOCK"
    if any(check.status == "WARN" for check in checks):
        return "WARN"
    return "PASS"


def render_text(checks: list[DoctorCheck], live_gates: list[DoctorCheck]) -> str:
    blocks = [check for check in checks if check.status == "BLOCK"]
    warns = [check for check in checks if check.status == "WARN"]
    lines = [
        "SourceHarbor first-run doctor",
        f"Overall: {overall_status(checks)}",
        "",
        "First-run gates",
    ]
    for check in checks:
        lines.extend(
            [
                f"[{check.status}] {check.title}",
                f"  Summary: {check.summary}",
                f"  Next: {check.next_step}",
            ]
        )
    lines.extend(["", "Live-validation gates"])
    for gate in live_gates:
        lines.extend(
            [
                f"[{gate.status}] {gate.title}",
                f"  Summary: {gate.summary}",
                f"  Next: {gate.next_step}",
            ]
        )
    if blocks or warns:
        lines.extend(["", "Recommended next steps"])
        for index, check in enumerate(blocks + warns, start=1):
            lines.append(f"{index}. {check.next_step}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    resolved_env = read_resolved_env(RESOLVED_ENV_PATH)
    database_url = resolved_env.get("DATABASE_URL") or os.getenv("DATABASE_URL") or ""
    temporal_target_host = (
        resolved_env.get("TEMPORAL_TARGET_HOST")
        or os.getenv("TEMPORAL_TARGET_HOST")
        or "127.0.0.1:7233"
    )
    api_base = (
        resolved_env.get("SOURCE_HARBOR_API_BASE_URL")
        or os.getenv("SOURCE_HARBOR_API_BASE_URL")
        or "http://127.0.0.1:9000"
    )
    web_port = resolved_env.get("WEB_PORT") or os.getenv("WEB_PORT") or "3000"
    web_url = f"http://127.0.0.1:{web_port}"
    core_port = (
        resolved_env.get("CORE_POSTGRES_PORT")
        or os.getenv("CORE_POSTGRES_PORT")
        or CANONICAL_CORE_POSTGRES_PORT
    )

    checks = [
        check_env_contract(),
        evaluate_database_target(database_url, core_port, listener_exists(5432)),
        check_postgres_reachability(database_url),
        check_temporal(temporal_target_host),
        check_runtime_snapshot(resolved_env),
        check_disk_governance(),
        check_full_stack_status(),
        check_http_gate(
            url=f"{api_base.rstrip('/')}/healthz",
            title="API health",
            next_step="Run ./bin/full-stack up and confirm the API becomes healthy before retrying smoke or retrieval checks.",
        ),
        check_http_gate(
            url=web_url,
            title="Web surface",
            next_step="Run ./bin/full-stack up and confirm the web command center becomes reachable before relying on UI routes.",
        ),
        check_write_token(),
    ]
    live_gates = [
        make_secret_gate(
            "YouTube live smoke",
            "YOUTUBE_API_KEY",
            "Add YOUTUBE_API_KEY only when you want the long live smoke lane, not for basic first-run readiness.",
        ),
        make_secret_gate(
            "Notification provider auth",
            "RESEND_API_KEY",
            "Add RESEND_API_KEY only when you want real external notification delivery proof.",
        ),
        make_secret_gate(
            "Notification sender identity",
            "RESEND_FROM_EMAIL",
            "Add RESEND_FROM_EMAIL only after you have a verified Resend sender/domain for real external notification delivery proof.",
        ),
        make_secret_gate(
            "Computer use / Gemini review",
            "GEMINI_API_KEY",
            "Add GEMINI_API_KEY only when you want Gemini-backed UI audit review or computer-use validation.",
        ),
    ]

    payload = {
        "overall": overall_status(checks),
        "first_run_checks": [asdict(item) for item in checks],
        "live_validation_gates": [asdict(item) for item in live_gates],
        "resolved_env_path": str(RESOLVED_ENV_PATH),
        "canonical_local_api_health": CANONICAL_API_HEALTH,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(checks, live_gates))
    return 1 if payload["overall"] == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
