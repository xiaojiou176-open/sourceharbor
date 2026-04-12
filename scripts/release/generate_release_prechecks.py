#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import write_json_artifact

REQUIRED_CWV_METRICS = ("lcp_ms_p75", "inp_ms_p75", "cls_p75")
RELEASE_REPORTS_DIR = Path("artifacts") / "releases"


def _latest_tag(repo_root: Path) -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError:
        return None
    return out or None


def _resolve_release_tag(
    explicit_release_tag: str | None, discovered_release_tag: str | None
) -> tuple[str | None, str]:
    normalized_explicit = (explicit_release_tag or "").strip() or None
    if normalized_explicit:
        return normalized_explicit, "input"
    return discovered_release_tag, "git-describe"


def _load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _as_positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _as_non_negative_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _validate_budget(path: Path) -> tuple[bool, str, dict[str, float] | None]:
    payload = _load_json_object(path)
    if payload is None:
        return False, f"path={path}; reason=missing_or_invalid_json", None
    budgets = payload.get("budgets")
    if not isinstance(budgets, dict):
        return False, f"path={path}; reason=missing_budgets_object", None

    normalized: dict[str, float] = {}
    missing_or_invalid: list[str] = []
    for key in REQUIRED_CWV_METRICS:
        value = _as_positive_float(budgets.get(key))
        if value is None:
            missing_or_invalid.append(key)
            continue
        normalized[key] = value

    if missing_or_invalid:
        return (
            False,
            f"path={path}; reason=missing_or_non_positive_budget_metrics; metrics={','.join(missing_or_invalid)}",
            None,
        )

    if normalized["cls_p75"] > 1:
        return (
            False,
            f"path={path}; reason=cls_budget_out_of_range; value={normalized['cls_p75']}",
            None,
        )

    return (
        True,
        (
            f"path={path}; lcp_ms_p75={normalized['lcp_ms_p75']}; "
            f"inp_ms_p75={normalized['inp_ms_p75']}; cls_p75={normalized['cls_p75']}"
        ),
        normalized,
    )


def _validate_rum_baseline(path: Path) -> tuple[bool, str, dict[str, float] | None]:
    payload = _load_json_object(path)
    if payload is None:
        return False, f"path={path}; reason=missing_or_invalid_json", None
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return False, f"path={path}; reason=missing_metrics_object", None

    normalized: dict[str, float] = {}
    missing_or_invalid: list[str] = []
    for key in REQUIRED_CWV_METRICS:
        if key == "cls_p75":
            value = _as_non_negative_float(metrics.get(key))
        else:
            value = _as_positive_float(metrics.get(key))
        if value is None:
            missing_or_invalid.append(key)
            continue
        normalized[key] = value

    if missing_or_invalid:
        return (
            False,
            f"path={path}; reason=missing_or_non_positive_rum_metrics; metrics={','.join(missing_or_invalid)}",
            None,
        )

    if normalized["cls_p75"] > 1:
        return (
            False,
            f"path={path}; reason=cls_rum_out_of_range; value={normalized['cls_p75']}",
            None,
        )

    sample_size = _as_positive_float(metrics.get("sample_size", payload.get("sample_size")))
    if sample_size is None:
        return (
            False,
            f"path={path}; reason=sample_size_missing_or_non_positive; value={metrics.get('sample_size', payload.get('sample_size'))}",
            None,
        )

    return (
        True,
        (
            f"path={path}; lcp_ms_p75={normalized['lcp_ms_p75']}; "
            f"inp_ms_p75={normalized['inp_ms_p75']}; cls_p75={normalized['cls_p75']}; "
            f"sample_size={int(sample_size)}"
        ),
        normalized,
    )


def _compare_rum_against_budget(
    budget: dict[str, float] | None, rum: dict[str, float] | None
) -> tuple[bool, str]:
    if budget is None or rum is None:
        return False, "reason=budget_or_rum_not_usable"
    exceeded = [
        f"{key}:{rum[key]}>{budget[key]}" for key in REQUIRED_CWV_METRICS if rum[key] > budget[key]
    ]
    if exceeded:
        return False, f"reason=rum_exceeds_budget; exceeded={','.join(exceeded)}"
    return True, "reason=rum_within_budget_thresholds"


def _pick_release_evidence_dir(repo_root: Path, latest_tag: str | None) -> Path | None:
    releases_root = repo_root / RELEASE_REPORTS_DIR
    if not releases_root.is_dir():
        return None
    if latest_tag:
        return releases_root / latest_tag
    candidates = [p for p in releases_root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _find_release_evidence_files(release_dir: Path | None, keyword: str) -> list[Path]:
    if release_dir is None:
        return []
    return sorted(
        path for path in release_dir.rglob("*") if path.is_file() and keyword in path.name.lower()
    )


def _has_slo_thresholds(path: Path) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    required_snippets = (
        "## SLO Thresholds (Defaults)",
        "Green: `>= 100%`",
        "Yellow: `>= 98%`",
        "Green: `>= 80%`",
        "Yellow: `>= 75%`",
        "Green: `>= 85%`",
        "Yellow: `>= 60%`",
    )
    return all(snippet in content for snippet in required_snippets)


def _build_observability_checks(repo_root: Path) -> list[dict[str, object]]:
    scratch_dir = repo_root / ".runtime-cache" / "tmp" / "release-readiness"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = scratch_dir / "release-prechecks-observability.sqlite3"

    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    os.environ.setdefault("TEMPORAL_TARGET_HOST", "127.0.0.1:7233")
    os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
    os.environ.setdefault("TEMPORAL_TASK_QUEUE", "video-analysis")
    os.environ.setdefault("SQLITE_STATE_PATH", str(sqlite_path))
    os.environ.setdefault("NOTIFICATION_ENABLED", "0")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from fastapi.testclient import TestClient

        from apps.api.app.main import app

        client = TestClient(app)
    except Exception as exc:
        if not isinstance(exc, ModuleNotFoundError):
            message = f"observability checks import failed: {type(exc).__name__}: {exc}"
            return [
                {
                    "name": "api_red_metrics_minimum",
                    "status": "fail",
                    "required": True,
                    "weight": 1.0,
                    "evidence": message,
                },
                {
                    "name": "api_trace_header_echo",
                    "status": "fail",
                    "required": True,
                    "weight": 1.0,
                    "evidence": message,
                },
            ]

        try:
            fallback_env = os.environ.copy()
            existing_pythonpath = fallback_env.get("PYTHONPATH", "")
            fallback_pythonpath = [
                str(repo_root),
                str(repo_root / "apps" / "worker"),
            ]
            if existing_pythonpath:
                fallback_pythonpath.append(existing_pythonpath)
            fallback_env["PYTHONPATH"] = ":".join(fallback_pythonpath)
            probe = subprocess.run(
                [
                    "uv",
                    "run",
                    # Use an isolated uv environment so fallback probing does not
                    # materialize a project-scoped `.venv` under the repo root.
                    "--isolated",
                    "python3",
                    "-c",
                    (
                        "import json;"
                        "from fastapi.testclient import TestClient;"
                        "from apps.api.app.main import app;"
                        "client=TestClient(app);"
                        "client.get('/healthz');"
                        "client.get('/release-observability-miss');"
                        "metrics=client.get('/metrics');"
                        "trace_id='release-trace-0001';"
                        "trace=client.get('/healthz', headers={'x-trace-id': trace_id});"
                        "body=metrics.text;"
                        "tokens=['sourceharbor_http_requests_total','sourceharbor_http_request_duration_seconds_sum',"
                        "'sourceharbor_http_request_duration_seconds_count','route=\"/healthz\"','status=\"200\"','status=\"404\"'];"
                        "red=(metrics.status_code==200 and all(t in body for t in tokens));"
                        "trace_ok=(trace.status_code==200 and trace.headers.get('x-trace-id','')==trace_id);"
                        "print(json.dumps({'red': red, 'trace': trace_ok, 'metrics_status': metrics.status_code,"
                        "'trace_status': trace.status_code, 'trace_echo': trace.headers.get('x-trace-id','')}, ensure_ascii=False))"
                    ),
                ],
                cwd=repo_root,
                env=fallback_env,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError:
            message = "observability checks import failed and uv is not installed"
            return [
                {
                    "name": "api_red_metrics_minimum",
                    "status": "fail",
                    "required": True,
                    "weight": 1.0,
                    "evidence": message,
                },
                {
                    "name": "api_trace_header_echo",
                    "status": "fail",
                    "required": True,
                    "weight": 1.0,
                    "evidence": message,
                },
            ]

        if probe.returncode != 0:
            message = "observability checks fallback via uv failed: " + (
                probe.stderr.strip() or probe.stdout.strip() or "unknown error"
            )
            return [
                {
                    "name": "api_red_metrics_minimum",
                    "status": "fail",
                    "required": True,
                    "weight": 1.0,
                    "evidence": message,
                },
                {
                    "name": "api_trace_header_echo",
                    "status": "fail",
                    "required": True,
                    "weight": 1.0,
                    "evidence": message,
                },
            ]

        payload = json.loads(probe.stdout.strip().splitlines()[-1])
        return [
            {
                "name": "api_red_metrics_minimum",
                "status": "pass" if bool(payload.get("red")) else "fail",
                "required": True,
                "weight": 1.0,
                "evidence": (
                    f"metrics_status={payload.get('metrics_status')};"
                    f" red_ready={bool(payload.get('red'))}"
                ),
            },
            {
                "name": "api_trace_header_echo",
                "status": "pass" if bool(payload.get("trace")) else "fail",
                "required": True,
                "weight": 1.0,
                "evidence": (
                    f"trace_status={payload.get('trace_status')};"
                    f" trace_echo={payload.get('trace_echo', 'missing')}"
                ),
            },
        ]

    client.get("/healthz")
    client.get("/release-observability-miss")
    metrics_response = client.get("/metrics")
    metrics_body = metrics_response.text

    red_tokens = (
        "sourceharbor_http_requests_total",
        "sourceharbor_http_request_duration_seconds_sum",
        "sourceharbor_http_request_duration_seconds_count",
        'route="/healthz"',
        'status="200"',
        'status="404"',
    )
    red_ready = metrics_response.status_code == 200 and all(
        token in metrics_body for token in red_tokens
    )
    red_evidence = f"status={metrics_response.status_code}; required_tokens=" + ",".join(
        token for token in red_tokens if token in metrics_body
    )

    trace_id = "release-trace-0001"
    trace_response = client.get("/healthz", headers={"x-trace-id": trace_id})
    trace_echo = trace_response.headers.get("x-trace-id", "")
    trace_ready = trace_response.status_code == 200 and trace_echo == trace_id
    trace_evidence = f"status={trace_response.status_code}; expected={trace_id}; actual={trace_echo or 'missing'}"

    return [
        {
            "name": "api_red_metrics_minimum",
            "status": "pass" if red_ready else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": red_evidence,
        },
        {
            "name": "api_trace_header_echo",
            "status": "pass" if trace_ready else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": trace_evidence,
        },
    ]


def _run_db_rollback_readiness(repo_root: Path, release_tag: str | None) -> dict[str, object]:
    output = (
        repo_root
        / ".runtime-cache"
        / "reports"
        / "release-readiness"
        / "db-rollback-readiness.json"
    )
    cmd = [
        "python3",
        str(repo_root / "scripts" / "release" / "verify_db_rollback_readiness.py"),
        "--repo-root",
        str(repo_root),
        "--output",
        str(output),
    ]
    if release_tag:
        cmd.extend(["--release-tag", release_tag])
    subprocess.run(cmd, check=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release precheck evidence checks")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--release-tag",
        default="",
        help="Explicit release tag to bind current-run artifacts to instead of relying on git describe.",
    )
    parser.add_argument(
        "--output",
        default=".runtime-cache/reports/release-readiness/prechecks.json",
    )
    parser.add_argument(
        "--skip-observability-checks",
        action="store_true",
        help="Skip executable RED/trace checks against local FastAPI app.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output = Path(args.output).resolve()

    changelog_path = repo_root / "CHANGELOG.md"
    perf_budget_path = repo_root / "artifacts" / "performance" / "cwv-budget.json"
    rum_baseline_path = repo_root / "artifacts" / "performance" / "rum-baseline.json"
    testing_slo_path = repo_root / "docs" / "testing-slo.md"
    rollback_runbook_path = repo_root / "docs" / "deploy" / "rollback-runbook.md"
    canary_script_path = repo_root / "scripts" / "deploy" / "canary_rollout.sh"

    latest_tag = _latest_tag(repo_root)
    release_tag, release_tag_source = _resolve_release_tag(args.release_tag, latest_tag)
    db_rollback_payload = _run_db_rollback_readiness(repo_root, release_tag)
    budget_ok, budget_evidence, budget_values = _validate_budget(perf_budget_path)
    rum_ok, rum_evidence, rum_values = _validate_rum_baseline(rum_baseline_path)
    rum_vs_budget_ok, rum_vs_budget_evidence = _compare_rum_against_budget(
        budget_values, rum_values
    )
    release_dir = _pick_release_evidence_dir(repo_root, release_tag)
    manifest_path = release_dir / "manifest.json" if release_dir else None
    checksums_path = release_dir / "checksums.sha256" if release_dir else None
    release_manifest_ok = bool(
        release_dir
        and manifest_path
        and checksums_path
        and manifest_path.is_file()
        and checksums_path.is_file()
    )
    canary_evidence_files = _find_release_evidence_files(release_dir, "canary")
    rollback_evidence_files = _find_release_evidence_files(release_dir, "rollback")
    rollback_summary = db_rollback_payload.get("summary", {})
    blocked_count = int(rollback_summary.get("blocked_without_down", 0) or 0)
    missing_policy_count = int(rollback_summary.get("missing_policy", 0) or 0)
    drill = db_rollback_payload.get("drill_evidence", {})
    drill_valid = bool(drill.get("valid", False))
    drill_errors = drill.get("errors", [])
    if not isinstance(drill_errors, list):
        drill_errors = []
    drill_error_text = ",".join(str(item) for item in drill_errors) if drill_errors else "none"

    checks = [
        {
            "name": "release_tag_resolved",
            "status": "pass" if release_tag else "fail",
            "required": True,
            "weight": 2.0,
            "value": release_tag,
            "evidence": (
                f"release_tag={release_tag or 'missing'}; source={release_tag_source}; "
                f"git_latest_tag={latest_tag or 'missing'}"
            ),
        },
        {
            "name": "changelog_exists",
            "status": "pass" if changelog_path.is_file() else "fail",
            "required": True,
            "weight": 1.5,
            "evidence": f"path={changelog_path}",
        },
        {
            "name": "performance_budget_present",
            "status": "pass" if budget_ok else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": budget_evidence,
        },
        {
            "name": "rum_baseline_present",
            "status": "pass" if rum_ok else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": rum_evidence,
        },
        {
            "name": "rum_within_budget_thresholds",
            "status": "pass" if rum_vs_budget_ok else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": rum_vs_budget_evidence,
        },
        {
            "name": "slo_thresholds_documented",
            "status": "pass" if _has_slo_thresholds(testing_slo_path) else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": f"path={testing_slo_path}",
        },
        {
            "name": "release_manifest_artifact_present",
            "status": "pass" if release_manifest_ok else "fail",
            "required": True,
            "weight": 1.0,
            "evidence": (
                f"release_dir={release_dir}; manifest={manifest_path}; checksums={checksums_path}"
                if release_dir
                else f"release_dir=missing; reports_root={repo_root / RELEASE_REPORTS_DIR}"
            ),
        },
        {
            "name": "rollback_runbook_present",
            "status": (
                "pass"
                if rollback_runbook_path.is_file() and bool(rollback_evidence_files)
                else "fail"
            ),
            "required": True,
            "weight": 1.0,
            "evidence": (
                f"runbook={rollback_runbook_path}; release_dir={release_dir}; "
                f"evidence_files={','.join(str(p) for p in rollback_evidence_files[:3]) or 'none'}"
            ),
        },
        {
            "name": "canary_rollout_script_present",
            "status": (
                "pass" if canary_script_path.is_file() and bool(canary_evidence_files) else "fail"
            ),
            "required": True,
            "weight": 1.0,
            "evidence": (
                f"script={canary_script_path}; release_dir={release_dir}; "
                f"evidence_files={','.join(str(p) for p in canary_evidence_files[:3]) or 'none'}"
            ),
        },
        {
            "name": "db_rollback_paths_covered",
            "status": "pass" if missing_policy_count == 0 else "fail",
            "required": True,
            "weight": 2.0,
            "value": missing_policy_count,
            "evidence": (
                "missing_policy="
                f"{missing_policy_count}; report=.runtime-cache/reports/release-readiness/db-rollback-readiness.json"
            ),
        },
        {
            "name": "db_rollback_blocker_gate",
            "status": "pass" if blocked_count == 0 else "fail",
            "required": True,
            "weight": 2.0,
            "value": blocked_count,
            "evidence": (
                f"blocked_without_down={blocked_count}; release_tag="
                f"{db_rollback_payload.get('release_tag', release_tag or 'unknown')}"
            ),
        },
        {
            "name": "db_rollback_drill_evidence_present",
            "status": "pass" if drill_valid else "fail",
            "required": True,
            "weight": 1.5,
            "evidence": f"path={drill.get('path', 'missing')}; errors={drill_error_text}",
        },
    ]

    if not args.skip_observability_checks:
        checks.extend(_build_observability_checks(repo_root))

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "checks": checks,
    }

    write_json_artifact(
        output,
        payload,
        source_entrypoint="scripts/release/generate_release_prechecks.py",
        verification_scope="release-prechecks",
        source_run_id="release-prechecks",
        freshness_window_hours=24,
        extra={"report_kind": "release-prechecks"},
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
