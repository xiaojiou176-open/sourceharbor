#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

ROOT = RUNTIME_DIR.parents[1]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import write_json_artifact  # noqa: E402
from sourceharbor_chrome import (  # noqa: E402
    cdp_url,
    default_cdp_port,
    default_profile_dir,
    default_profile_name,
    default_repo_user_data_dir,
    is_cdp_alive,
    list_repo_chrome_processes,
    resolve_repo_runtime,
)

LOGIN_SITE_SETS: dict[str, list[dict[str, str]]] = {
    "login-strong-check": [
        {"label": "google_account", "url": "https://myaccount.google.com/"},
        {"label": "youtube_home", "url": "https://www.youtube.com/"},
        {"label": "bilibili_account", "url": "https://account.bilibili.com/account/home"},
        {"label": "resend_login", "url": "https://resend.com/login"},
    ]
}


def _classify_site_result(*, label: str, requested_url: str, final_url: str, final_title: str) -> dict[str, str]:
    normalized_url = final_url.lower().strip()
    login_state = "unknown"
    if label == "bilibili_account":
        if "account.bilibili.com/account/home" in normalized_url:
            login_state = "authenticated"
        elif "passport.bilibili.com" in normalized_url or "login" in normalized_url:
            login_state = "login_required"
    elif label == "google_account":
        login_state = "authenticated" if "myaccount.google.com" in normalized_url else "unknown"
    elif label == "youtube_home":
        login_state = "authenticated" if "youtube.com" in normalized_url else "unknown"
    elif label == "resend_login":
        login_state = "login_required" if "resend.com/login" in normalized_url else "authenticated"
    proof_kind = "url_page_state" if final_url else "open_tab_only"
    return {
        "requested_url": requested_url,
        "final_url": final_url,
        "final_title": final_title,
        "login_state": login_state,
        "proof_kind": proof_kind,
        "proof_boundary": "repo_owned_chrome_url_page_state",
    }


def _report_path(repo_root: Path) -> Path:
    return repo_root / ".runtime-cache" / "reports" / "runtime" / "repo-chrome-open-tabs.json"


def _fetch_body(url: str, method: str = "GET") -> str:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _fetch_json(url: str, method: str = "GET") -> Any:
    body = _fetch_body(url, method=method)
    return json.loads(body) if body else None


def list_page_targets(port: int) -> list[dict[str, Any]]:
    payload = _fetch_json(f"{cdp_url(port)}/json/list")
    if not isinstance(payload, list):
        raise RuntimeError("CDP /json/list did not return a JSON list")
    return [item for item in payload if isinstance(item, dict) and item.get("type") == "page"]


def close_page_target(port: int, target_id: str) -> None:
    _fetch_body(f"{cdp_url(port)}/json/close/{target_id}", method="GET")


def open_page_target(port: int, url: str) -> dict[str, Any]:
    encoded_url = urllib.parse.quote(url, safe="")
    payload = _fetch_json(f"{cdp_url(port)}/json/new?{encoded_url}", method="PUT")
    if not isinstance(payload, dict):
        raise RuntimeError("CDP /json/new did not return a JSON object")
    return payload


def _site_entries(site_set: str, custom_urls: list[str]) -> list[dict[str, str]]:
    if custom_urls:
        return [
            {"label": f"custom_{index + 1}", "url": url} for index, url in enumerate(custom_urls)
        ]
    if site_set not in LOGIN_SITE_SETS:
        raise RuntimeError(f"unknown site set `{site_set}`")
    return LOGIN_SITE_SETS[site_set]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open repo-owned Chrome tabs on the existing SourceHarbor Chrome CDP instance."
    )
    parser.add_argument("--user-data-dir", default="")
    parser.add_argument("--profile-dir", default=default_profile_dir())
    parser.add_argument("--profile-name", default=default_profile_name())
    parser.add_argument("--cdp-port", default=str(default_cdp_port()))
    parser.add_argument("--site-set", default="login-strong-check")
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--keep-existing-pages", action="store_true")
    parser.add_argument("--settle-seconds", type=float, default=2.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = ROOT
    user_data_dir = Path(args.user_data_dir.strip() or default_repo_user_data_dir()).expanduser()

    try:
        runtime_payload = resolve_repo_runtime(
            user_data_dir=str(user_data_dir),
            profile_name=args.profile_name,
            profile_dir=args.profile_dir,
            cdp_port=args.cdp_port,
        )
        port = int(runtime_payload["cdp_port"])
        repo_chrome_processes = list_repo_chrome_processes(user_data_dir)
        if not repo_chrome_processes:
            raise RuntimeError(
                "repo-owned Chrome process is not running for the configured user-data-dir; "
                "refuse to open tabs on an unowned or mismatched CDP endpoint"
            )
        if not is_cdp_alive(port):
            raise RuntimeError(
                f"repo Chrome CDP endpoint is not responding at {runtime_payload['cdp_url']}; start repo Chrome first"
            )
        entries = _site_entries(args.site_set, args.url)
        closed_targets: list[str] = []
        if not args.keep_existing_pages:
            for target in list_page_targets(port):
                target_id = str(target.get("id") or "").strip()
                if not target_id:
                    continue
                close_page_target(port, target_id)
                closed_targets.append(target_id)
        opened_targets: list[dict[str, Any]] = []
        for entry in entries:
            target_payload = open_page_target(port, entry["url"])
            opened_targets.append(
                {
                    "label": entry["label"],
                    "requested_url": entry["url"],
                    "target_id": target_payload.get("id"),
                    "opened_url": target_payload.get("url"),
                }
            )
        site_results: dict[str, dict[str, str]] = {}
        if opened_targets:
            if args.settle_seconds > 0:
                time.sleep(args.settle_seconds)
            final_targets = {
                str(target.get("id") or "").strip(): target for target in list_page_targets(port)
            }
            for item in opened_targets:
                final_target = final_targets.get(str(item.get("target_id") or "").strip(), {})
                final_url = str(final_target.get("url") or item.get("opened_url") or "").strip()
                final_title = str(final_target.get("title") or "").strip()
                site_results[str(item["label"])] = _classify_site_result(
                    label=str(item["label"]),
                    requested_url=str(item["requested_url"]),
                    final_url=final_url,
                    final_title=final_title,
                )
    except RuntimeError as exc:
        print(f"[open-repo-chrome-tabs] FAIL\n  - {exc}", file=sys.stderr)
        return 1

    report = {
        "version": 1,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo_root": str(repo_root),
        "status": "opened",
        "cdp_url": runtime_payload["cdp_url"],
        "user_data_dir": str(user_data_dir),
        "profile_dir": runtime_payload["profile_dir"],
        "profile_name": runtime_payload["profile_name"],
        "pid_candidates": [process["pid"] for process in repo_chrome_processes],
        "site_set": args.site_set,
        "closed_targets": closed_targets,
        "opened_targets": opened_targets,
        "site_results": site_results,
    }
    write_json_artifact(
        _report_path(repo_root),
        report,
        source_entrypoint="scripts/runtime/open_repo_chrome_tabs.py",
        verification_scope="repo-chrome-open-tabs",
        source_run_id="repo-chrome-open-tabs",
        freshness_window_hours=24,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("[open-repo-chrome-tabs] PASS")
        for item in opened_targets:
            print(f"  - {item['label']}: {item['requested_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
