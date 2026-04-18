#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path


def resolve_base_url(repo_root: Path, explicit_base_url: str) -> str:
    normalized = explicit_base_url.strip()
    if normalized:
        return normalized.rstrip("/")
    resolved_env = repo_root / ".runtime-cache" / "run" / "full-stack" / "resolved.env"
    if not resolved_env.is_file():
        return "http://127.0.0.1:3000"
    values: dict[str, str] = {}
    for raw_line in resolved_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    if values.get("SOURCE_HARBOR_WEB_BASE_URL"):
        return values["SOURCE_HARBOR_WEB_BASE_URL"].rstrip("/")
    if values.get("WEB_PORT"):
        return f"http://127.0.0.1:{values['WEB_PORT']}"
    return "http://127.0.0.1:3000"


def ensure_full_stack_up(repo_root: Path) -> None:
    subprocess.run(
        ["./bin/full-stack", "up"],
        cwd=repo_root,
        check=True,
    )


def run_capture_helper(repo_root: Path, output_dir: Path) -> None:
    cmd = [
        "uv",
        "run",
        "--with",
        "playwright",
        "python",
        "scripts/runtime/capture_frontstage_proof_pack.py",
        "--base-url",
        resolve_base_url(repo_root, ""),
        "--output-dir",
        str(output_dir),
    ]
    try:
        subprocess.run(cmd, cwd=repo_root, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "frontstage clean UI audit preflight failed while capturing the proof pack; "
            "check that `./bin/full-stack up` has responsive routes on `/`, `/feed`, `/subscriptions`, and `/reader/demo` before rerunning."
        ) from exc


def post_json(url: str, payload: dict[str, object], api_key: str) -> dict[str, object]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode())


def get_json(url: str, api_key: str) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"X-API-Key": api_key})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode())


def create_mini_pack(source_dir: Path, mini_dir: Path) -> None:
    if mini_dir.exists():
        shutil.rmtree(mini_dir)
    mini_dir.mkdir(parents=True, exist_ok=True)
    keep = [
        "desktop-home-clean.png",
        "desktop-feed-clean.png",
        "mobile-subscriptions-clean.png",
        "desktop-reader-demo-expanded-clean.png",
    ]
    for name in keep:
        shutil.copy2(source_dir / name, mini_dir / name)
    (mini_dir / "playwright-axe-report.json").write_text(
        '{"summary":"frontstage clean mini proof pack"}',
        encoding="utf-8",
    )
    (mini_dir / "manifest.json").write_text(
        json.dumps({"shots": keep}, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture a clean local frontstage proof pack and run the repo UI audit on it."
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:9000",
        help="Local SourceHarbor API base URL.",
    )
    parser.add_argument(
        "--api-key",
        default="sourceharbor-local-dev-token",
        help="Local SourceHarbor write/read token for UI audit routes.",
    )
    parser.add_argument(
        "--artifact-root-name",
        default="sourceharbor-frontstage-proof-clean",
        help="Artifact root name relative to system tempdir for /api/v1/ui-audit/run.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Base URL for the local web runtime; defaults to the current resolved route.",
    )
    parser.add_argument(
        "--skip-stack-up",
        action="store_true",
        help="Skip calling ./bin/full-stack up before capture.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    artifact_dir = Path(tempfile.gettempdir()) / args.artifact_root_name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_stack_up:
        ensure_full_stack_up(repo_root)
    base_url = resolve_base_url(repo_root, args.base_url)
    cmd = [
        "uv",
        "run",
        "--with",
        "playwright",
        "python",
        "scripts/runtime/capture_frontstage_proof_pack.py",
        "--base-url",
        base_url,
        "--output-dir",
        str(artifact_dir),
    ]
    try:
        subprocess.run(cmd, cwd=repo_root, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "frontstage clean UI audit preflight failed while capturing the proof pack; "
            f"check that `./bin/full-stack up` exposes responsive frontstage routes under {base_url} before rerunning."
        ) from exc

    run_payload = post_json(
        f"{args.api_base_url.rstrip('/')}/api/v1/ui-audit/run",
        {"artifact_root": args.artifact_root_name},
        args.api_key,
    )
    effective_run = run_payload
    effective_root_name = args.artifact_root_name
    fallback_run: dict[str, object] | None = None
    gemini_review = run_payload.get("gemini_review")
    if (
        isinstance(gemini_review, dict)
        and str(gemini_review.get("status") or "").lower() == "failed"
        and str(gemini_review.get("reason_code") or "").lower() == "provider_error"
    ):
        mini_name = f"{args.artifact_root_name}-mini"
        mini_dir = Path(tempfile.gettempdir()) / mini_name
        create_mini_pack(artifact_dir, mini_dir)
        fallback_run = post_json(
            f"{args.api_base_url.rstrip('/')}/api/v1/ui-audit/run",
            {"artifact_root": mini_name},
            args.api_key,
        )
        effective_run = fallback_run
        effective_root_name = mini_name

    run_id = str(effective_run.get("run_id") or "").strip()
    if not run_id:
        print(json.dumps(effective_run, indent=2))
        return 1

    findings_high = get_json(
        f"{args.api_base_url.rstrip('/')}/api/v1/ui-audit/{run_id}/findings?severity=high",
        args.api_key,
    )
    findings_medium = get_json(
        f"{args.api_base_url.rstrip('/')}/api/v1/ui-audit/{run_id}/findings?severity=medium",
        args.api_key,
    )

    report = {
        "artifact_root": str(artifact_dir),
        "run": run_payload,
        "effective_artifact_root_name": effective_root_name,
        "effective_run": effective_run,
        "fallback_run": fallback_run,
        "high_findings": findings_high.get("items", []),
        "medium_findings": findings_medium.get("items", []),
    }
    (artifact_dir / "ui-audit-report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
