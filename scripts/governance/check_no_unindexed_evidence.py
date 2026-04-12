#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import (
    is_runtime_metadata_managed_artifact,
    load_governance_json,
    read_runtime_metadata,
    rel_path,
)


def main() -> int:
    contract = load_governance_json("evidence-contract.json")
    evidence_root = ROOT / str(
        contract.get("buckets", {}).get("evidence", {}).get("path") or ".runtime-cache/evidence"
    )
    reports_root = (
        ROOT
        / str(
            contract.get("buckets", {}).get("reports", {}).get("path") or ".runtime-cache/reports"
        )
        / "tests"
    )
    index_root = ROOT / str(
        contract.get("evidence_index", {}).get("root") or ".runtime-cache/reports/evidence-index"
    )
    errors: list[str] = []

    def _check_artifact(path: Path) -> None:
        metadata = read_runtime_metadata(path)
        if metadata is None:
            errors.append(f"{rel_path(path)}: missing runtime metadata")
            return
        run_id = str(metadata.get("source_run_id") or "").strip()
        if not run_id:
            errors.append(f"{rel_path(path)}: missing source_run_id in metadata")
            return
        index_path = index_root / f"{run_id}.json"
        if not index_path.is_file():
            errors.append(f"{rel_path(path)}: missing evidence index for run_id={run_id}")
            return
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        indexed_paths = (
            set(payload.get("evidence", []))
            | set(payload.get("reports", []))
            | set(payload.get("logs", []))
        )
        if rel_path(path) not in indexed_paths:
            errors.append(
                f"{rel_path(path)}: evidence index {rel_path(index_path)} does not reference artifact"
            )

    if evidence_root.exists():
        for artifact in sorted(
            item
            for item in evidence_root.rglob("*")
            if is_runtime_metadata_managed_artifact(item)
        ):
            _check_artifact(artifact)
    if reports_root.exists():
        for artifact in sorted(
            item
            for item in reports_root.rglob("*")
            if is_runtime_metadata_managed_artifact(item)
        ):
            _check_artifact(artifact)

    if errors:
        print("[no-unindexed-evidence] FAIL")
        for item in errors[:50]:
            print(f"  - {item}")
        return 1

    print("[no-unindexed-evidence] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
