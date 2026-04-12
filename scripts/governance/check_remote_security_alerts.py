#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import git_output


def _origin_repo_slug() -> str:
    remote = git_output("remote", "get-url", "origin").strip()
    if remote.startswith("git@github.com:"):
        slug = remote.removeprefix("git@github.com:")
        return slug[:-4] if slug.endswith(".git") else slug
    if remote.startswith("https://github.com/"):
        slug = remote.removeprefix("https://github.com/")
        return slug[:-4] if slug.endswith(".git") else slug
    raise RuntimeError(f"unsupported origin remote for GitHub alert checks: {remote}")


def _rest_api_json(path: str) -> list[dict[str, object]]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("gh unavailable and GITHUB_TOKEN not set")

    request = Request(
        f"https://api.github.com/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sourceharbor-remote-security-alerts",
        },
    )
    try:
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore").strip()
        raise RuntimeError(detail or f"GitHub REST API failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub REST API unreachable: {exc}") from exc

    return payload if isinstance(payload, list) else []


def _gh_api_json(path: str) -> list[dict[str, object]]:
    if shutil.which("gh"):
        result = subprocess.run(
            ["gh", "api", path],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            payload = json.loads(result.stdout or "[]")
            return payload if isinstance(payload, list) else []
        stderr = result.stderr.strip() or result.stdout.strip()
        if "No such file or directory" not in stderr:
            raise RuntimeError(stderr or f"gh api failed for {path}")
    return _rest_api_json(path)


def main() -> int:
    try:
        repo_slug = _origin_repo_slug()
        secret_alerts = _gh_api_json(
            f"repos/{repo_slug}/secret-scanning/alerts?state=open&per_page=100"
        )
        code_alerts = _gh_api_json(
            f"repos/{repo_slug}/code-scanning/alerts?state=open&per_page=100"
        )
    except Exception as exc:  # noqa: BLE001
        print("[remote-security-alerts] FAIL")
        print(f"  - unable to query GitHub security alerts: {exc}")
        print(
            "  - remediation: ensure `gh` is installed, authenticated, and allowed to access the repository"
        )
        return 1

    errors: list[str] = []
    if secret_alerts:
        errors.append(f"open GitHub secret-scanning alerts: {len(secret_alerts)}")
    for alert in code_alerts:
        number = alert.get("number")
        rule = (
            ((alert.get("rule") or {}).get("id")) if isinstance(alert.get("rule"), dict) else None
        )
        instance = alert.get("most_recent_instance") or {}
        commit = instance.get("commit_sha")
        location = instance.get("location") or {}
        path = location.get("path")
        start_line = location.get("start_line")
        errors.append(
            f"open GitHub code-scanning alert #{number}: rule={rule or '<unknown>'} commit={commit or '<unknown>'} path={path or '<unknown>'}:{start_line or '?'}"
        )

    if errors:
        print("[remote-security-alerts] FAIL")
        for item in errors:
            print(f"  - {item}")
        print(
            "  - remediation: close or fix open GitHub secret-scanning/code-scanning alerts before treating the remote public surface as fully clean"
        )
        return 1

    print("[remote-security-alerts] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
