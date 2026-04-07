#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = ROOT / "artifacts" / "licenses" / "third-party-license-inventory.json"
NOTICE_PATH = ROOT / "THIRD_PARTY_NOTICES.md"
PYTHON_RUNTIME_SCOPE_NOTE = (
    "the canonical `uv run --extra dev python` environment, using a throwaway temp uv "
    "environment instead of root `.venv` or repo-owned runtime roots"
)


def _python_inventory_command(code: str) -> list[str]:
    return ["uv", "run", "--extra", "dev", "python", "-c", code]


def _run_python_runtime_inventory() -> list[dict[str, str]]:
    code = r"""
import importlib.metadata as md
import json

rows = []
for dist in md.distributions():
    name = (dist.metadata.get("Name") or "").strip()
    if not name or name.lower() == "sourceharbor":
        continue
    license_expression = (dist.metadata.get("License-Expression") or "").strip()
    license_value = (dist.metadata.get("License") or "").strip()
    classifiers = [
        item for item in dist.metadata.get_all("Classifier", []) if item.startswith("License ::")
    ]
    if license_expression:
        license_source = "license-expression"
        normalized = license_expression
    elif license_value:
        license_source = "license-field"
        normalized = license_value
    elif classifiers:
        license_source = "classifier"
        normalized = classifiers[0].split("::")[-1].strip()
    else:
        license_source = "unknown"
        normalized = "UNKNOWN"
    rows.append(
        {
            "name": name,
            "version": dist.version,
            "license": normalized or "UNKNOWN",
            "license_source": license_source,
            "classifiers": classifiers,
            "summary": (dist.metadata.get("Summary") or "").strip(),
            "homepage": (dist.metadata.get("Home-page") or dist.metadata.get("Project-URL") or "").strip(),
        }
    )

    rows.sort(key=lambda item: item["name"].lower())
print(json.dumps(rows, ensure_ascii=False))
"""
    env = dict(os.environ)
    uv_env_path = Path(tempfile.mkdtemp(prefix="video-analysis-third-party-license-"))
    env["UV_PROJECT_ENVIRONMENT"] = str(uv_env_path)
    env.setdefault("UV_LINK_MODE", "copy")
    try:
        result = subprocess.run(
            _python_inventory_command(code),
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    finally:
        shutil.rmtree(uv_env_path, ignore_errors=True)
    return json.loads(result.stdout)


def _package_name_from_lock_path(path: str) -> str:
    marker = "node_modules/"
    if marker not in path:
        return path or "<root>"
    return path.rsplit(marker, maxsplit=1)[-1]


def _package_display_name(lock_path: str, entry: dict[str, object]) -> str:
    if "node_modules/" not in lock_path:
        package_name = str(entry.get("name") or "").strip()
        if package_name:
            return package_name
    return _package_name_from_lock_path(lock_path)


def _load_web_runtime_inventory() -> list[dict[str, str]]:
    payload = json.loads((ROOT / "apps" / "web" / "package-lock.json").read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for lock_path, entry in payload.get("packages", {}).items():
        if not isinstance(entry, dict) or lock_path == "":
            continue
        if entry.get("dev") is True:
            continue
        # npm file/link dependencies appear twice in package-lock:
        # a shim entry under node_modules/* with {"link": true}, and
        # the actual target package metadata at the resolved path.
        # Only the target package should count toward notices inventory.
        if entry.get("link") is True:
            continue
        rows.append(
            {
                "name": _package_display_name(lock_path, entry),
                "version": str(entry.get("version") or ""),
                "license": str(entry.get("license") or "UNKNOWN"),
                "license_source": "package-lock",
                "resolved": str(entry.get("resolved") or ""),
                "integrity": str(entry.get("integrity") or ""),
            }
        )
    rows.sort(key=lambda item: item["name"].lower())
    return rows


def _build_inventory() -> dict[str, object]:
    python_rows = _run_python_runtime_inventory()
    web_rows = _load_web_runtime_inventory()
    python_unknown = sum(1 for row in python_rows if row["license"] == "UNKNOWN")
    web_unknown = sum(1 for row in web_rows if row["license"] == "UNKNOWN")
    return {
        "version": 1,
        "scope": {
            "python": f"runtime environment from {PYTHON_RUNTIME_SCOPE_NOTE}",
            "web": "production packages from `apps/web/package-lock.json` with dev=false",
        },
        "summary": {
            "python_runtime_packages": len(python_rows),
            "python_unknown_licenses": python_unknown,
            "web_runtime_packages": len(web_rows),
            "web_unknown_licenses": web_unknown,
        },
        "python_runtime": python_rows,
        "web_runtime": web_rows,
    }


def _render_notice(inventory: dict[str, object]) -> str:
    python_rows = inventory["python_runtime"]
    web_rows = inventory["web_runtime"]
    summary = inventory["summary"]
    lines = [
        "<!-- generated: scripts/governance/render_third_party_notices.py; do not edit directly -->",
        "",
        "# Third-Party Notices",
        "",
        "This file is the machine-generated third-party rights ledger for the tracked public repository surface.",
        "",
        "## Scope",
        "",
        f"- Python runtime inventory comes from {PYTHON_RUNTIME_SCOPE_NOTE}.",
        "- Web runtime inventory comes from `apps/web/package-lock.json` and excludes `dev=true` packages.",
        "- `UNKNOWN` means the package metadata did not expose a machine-readable license field/classifier in this inventory pass; it is a follow-up item, not a silent pass.",
        "",
        "## Summary",
        "",
        "| Ecosystem | Packages | UNKNOWN license declarations |",
        "| --- | ---: | ---: |",
        f"| Python runtime | {summary['python_runtime_packages']} | {summary['python_unknown_licenses']} |",
        f"| Web runtime | {summary['web_runtime_packages']} | {summary['web_unknown_licenses']} |",
        "",
        "## Python Runtime Packages",
        "",
        "| Package | Version | License | Evidence Source |",
        "| --- | --- | --- | --- |",
    ]
    for row in python_rows:
        lines.append(
            f"| `{row['name']}` | `{row['version']}` | `{row['license']}` | `{row['license_source']}` |"
        )
    lines.extend(
        [
            "",
            "## Web Runtime Packages",
            "",
            "| Package | Version | License | Evidence Source |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in web_rows:
        lines.append(
            f"| `{row['name']}` | `{row['version']}` | `{row['license']}` | `{row['license_source']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_or_check(path: Path, content: str, check: bool) -> list[str]:
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if current == content:
        return []
    if check:
        return [str(path.relative_to(ROOT).as_posix())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    inventory = _build_inventory()
    inventory_text = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    notice_text = _render_notice(inventory)

    stale: list[str] = []
    stale.extend(_write_or_check(ARTIFACT_PATH, inventory_text, args.check))
    stale.extend(_write_or_check(NOTICE_PATH, notice_text, args.check))

    if args.check and stale:
        print("[third-party-notices] FAIL")
        for item in stale:
            print(f"  - stale generated file: {item}")
        print("  - run: python3 scripts/governance/render_third_party_notices.py")
        return 1

    if not args.check:
        print("[third-party-notices] rendered")
    else:
        print("[third-party-notices] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
