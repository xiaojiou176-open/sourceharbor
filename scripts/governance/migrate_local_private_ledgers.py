#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import current_git_commit, write_runtime_metadata


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _rel_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_ledger_config(root: Path) -> dict[str, Any]:
    config_path = root / "config" / "governance" / "local-private-ledgers.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def _ledger_paths(root: Path) -> tuple[Path, list[Path]]:
    payload = _load_ledger_config(root)
    for ledger in payload.get("ledgers", []):
        authoritative = str(ledger.get("authoritative_target_path") or "").strip()
        if not authoritative:
            continue
        compatibility_paths = [
            (root / str(path)).resolve() for path in ledger.get("compatibility_paths", [])
        ]
        return ((root / authoritative).resolve(), compatibility_paths)
    raise RuntimeError("no authoritative local-private ledger target configured")


def _receipt_path(target_root: Path) -> Path:
    return target_root / ".migration-receipts.json"


def _load_receipts(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "entries": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _source_signature(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {
        "source_size_bytes": int(stat.st_size),
        "source_mtime_ns": int(stat.st_mtime_ns),
    }


def migrate_ledgers(root: Path) -> dict[str, Any]:
    target_root, compatibility_paths = _ledger_paths(root)
    target_root.mkdir(parents=True, exist_ok=True)
    receipt_path = _receipt_path(target_root)
    receipts = _load_receipts(receipt_path)
    receipt_entries = dict(receipts.get("entries") or {})

    discovered_sources: list[Path] = []
    for source_root in compatibility_paths:
        if not source_root.is_dir():
            continue
        discovered_sources.extend(sorted(source_root.glob("*.md"), key=lambda path: path.name))

    actions: list[dict[str, Any]] = []
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_commit = current_git_commit()
    run_id = "local-private-ledger-migration"

    for source in discovered_sources:
        signature = _source_signature(source)
        target = target_root / source.name
        source_key = _rel_path(root, source)
        receipt = receipt_entries.get(source_key)
        if (
            receipt
            and target.is_file()
            and receipt.get("target_path") == _rel_path(root, target)
            and receipt.get("source_size_bytes") == signature["source_size_bytes"]
            and receipt.get("source_mtime_ns") == signature["source_mtime_ns"]
        ):
            write_runtime_metadata(
                target,
                source_entrypoint="scripts/governance/migrate_local_private_ledgers.py",
                verification_scope="local-private-ledger-migration",
                source_run_id=run_id,
                source_commit=source_commit,
                freshness_window_hours=24,
                created_at=generated_at,
                extra={
                    "report_kind": "ai-ledger-authoritative-copy",
                    "source_path": source_key,
                },
            )
            actions.append(
                {
                    "source_path": source_key,
                    "target_path": _rel_path(root, target),
                    "status": "up-to-date",
                }
            )
            continue

        shutil.copy2(source, target)
        receipt_entries[source_key] = {
            "target_path": _rel_path(root, target),
            **signature,
            "copied_at": generated_at,
        }
        write_runtime_metadata(
            target,
            source_entrypoint="scripts/governance/migrate_local_private_ledgers.py",
            verification_scope="local-private-ledger-migration",
            source_run_id=run_id,
            source_commit=source_commit,
            freshness_window_hours=24,
            created_at=generated_at,
            extra={
                "report_kind": "ai-ledger-authoritative-copy",
                "source_path": source_key,
            },
        )
        actions.append(
            {
                "source_path": source_key,
                "target_path": _rel_path(root, target),
                "status": "copied" if not receipt else "refreshed",
            }
        )

    receipts["entries"] = receipt_entries
    receipt_path.write_text(
        json.dumps(receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_runtime_metadata(
        receipt_path,
        source_entrypoint="scripts/governance/migrate_local_private_ledgers.py",
        verification_scope="local-private-ledger-migration",
        source_run_id=run_id,
        source_commit=source_commit,
        freshness_window_hours=24,
        created_at=generated_at,
        extra={"report_kind": "local-private-ledger-migration-receipts"},
    )

    copied = sum(1 for item in actions if item["status"] == "copied")
    refreshed = sum(1 for item in actions if item["status"] == "refreshed")
    up_to_date = sum(1 for item in actions if item["status"] == "up-to-date")

    return {
        "version": 1,
        "generated_at": generated_at,
        "repo_root": str(root),
        "authoritative_target_path": _rel_path(root, target_root),
        "compatibility_paths": [_rel_path(root, path) for path in compatibility_paths],
        "receipts_path": _rel_path(root, receipt_path),
        "discovered_source_files": [_rel_path(root, path) for path in discovered_sources],
        "actions": actions,
        "summary": {
            "discovered_count": len(discovered_sources),
            "copied_count": copied,
            "refreshed_count": refreshed,
            "up_to_date_count": up_to_date,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy local-private plan ledgers from compatibility paths into the authoritative ai-ledgers root."
    )
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument(
        "--report",
        default=".runtime-cache/reports/governance/local-private-ledger-migration.json",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    report = migrate_ledgers(root)
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = (root / report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("[local-private-ledger-migration] PASS")
        print(f"  - discovered={report['summary']['discovered_count']}")
        print(f"  - copied={report['summary']['copied_count']}")
        print(f"  - refreshed={report['summary']['refreshed_count']}")
        print(f"  - up_to_date={report['summary']['up_to_date_count']}")
        print(f"  - target={report['authoritative_target_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
