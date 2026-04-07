#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import (
    current_git_commit,
    load_governance_json,
    read_runtime_metadata,
    rel_path,
    runtime_metadata_path,
    write_runtime_metadata,
)


def _candidate_artifacts() -> list[Path]:
    contract = load_governance_json("evidence-contract.json")
    candidates: list[Path] = []
    for subconfig in contract.get("buckets", {}).values():
        base = ROOT / str(subconfig.get("path") or "")
        if not base.exists():
            continue
        candidates.extend(
            sorted(
                item
                for item in base.rglob("*")
                if item.is_file() and not item.name.endswith(".meta.json")
            )
        )
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build evidence index files grouped by source_run_id."
    )
    parser.add_argument(
        "--rebuild-all", action="store_true", help="Rebuild all discovered run indexes."
    )
    args = parser.parse_args()

    grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for artifact in _candidate_artifacts():
        metadata = read_runtime_metadata(artifact)
        if metadata is None:
            continue
        run_id = str(metadata.get("source_run_id") or metadata.get("run_id") or "").strip()
        if not run_id:
            continue
        top = artifact.relative_to(ROOT / ".runtime-cache").parts[0]
        grouped[run_id][top].append(rel_path(artifact))

    contract = load_governance_json("evidence-contract.json")
    index_root = ROOT / str(
        contract.get("evidence_index", {}).get("root") or ".runtime-cache/reports/evidence-index"
    )
    index_root.mkdir(parents=True, exist_ok=True)
    current_head = current_git_commit()
    expected_paths: set[Path] = set()

    for run_id, categories in sorted(grouped.items()):
        payload = {
            "version": 1,
            "run_id": run_id,
            "logs": sorted(categories.get("logs", [])),
            "reports": sorted(categories.get("reports", [])),
            "evidence": sorted(categories.get("evidence", [])),
        }
        index_path = index_root / f"{run_id}.json"
        metadata_path = runtime_metadata_path(index_path)
        expected_paths.add(index_path)
        expected_paths.add(metadata_path)
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        metadata = read_runtime_metadata(index_path) or {}
        metadata_current = (
            str(metadata.get("source_commit") or "").strip() == current_head
            and str(metadata.get("source_entrypoint") or "").strip()
            == "scripts/runtime/build_evidence_index.py"
            and str(metadata.get("source_run_id") or "").strip() == run_id
            and str(metadata.get("verification_scope") or "").strip() == "evidence-index"
        )
        existing = index_path.read_text(encoding="utf-8") if index_path.is_file() else None
        if not args.rebuild_all and existing == rendered and metadata_current:
            continue

        index_path.write_text(rendered, encoding="utf-8")
        write_runtime_metadata(
            index_path,
            source_entrypoint="scripts/runtime/build_evidence_index.py",
            verification_scope="evidence-index",
            source_run_id=run_id,
            freshness_window_hours=24,
            source_commit=current_head,
            extra={"report_kind": "evidence-index"},
        )

    for stale_path in index_root.glob("*.json*"):
        if stale_path not in expected_paths:
            stale_path.unlink(missing_ok=True)

    print(f"[build-evidence-index] PASS ({len(grouped)} run ids indexed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
