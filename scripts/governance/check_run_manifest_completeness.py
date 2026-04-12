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


def _log_has_complete_event(log_path: Path, run_id: str) -> bool:
    try:
        for raw in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if (
                str(
                    payload.get("run_id")
                    or payload.get("test_run_id")
                    or payload.get("gate_run_id")
                    or ""
                ).strip()
                != run_id
            ):
                continue
            if str(payload.get("event") or "").strip() == "complete":
                return True
    except OSError:
        return False
    return False


def _shared_log_file(path: Path) -> bool:
    if path.suffix != ".jsonl":
        return False
    seen_run_ids: set[str] = set()
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidate = str(
                payload.get("run_id")
                or payload.get("test_run_id")
                or payload.get("gate_run_id")
                or ""
            ).strip()
            if not candidate:
                continue
            seen_run_ids.add(candidate)
            if len(seen_run_ids) > 1:
                return True
    except OSError:
        return False
    return False


def _runtime_artifacts_for_run(run_id: str, *, manifest_log_path: Path | None) -> list[Path]:
    artifacts: list[Path] = []
    contract = load_governance_json("evidence-contract.json")
    for bucket_config in contract.get("buckets", {}).values():
        base = ROOT / str(bucket_config.get("path") or "")
        if not base.exists():
            continue
        for item in base.rglob("*"):
            if not is_runtime_metadata_managed_artifact(item):
                continue
            if item.is_relative_to(ROOT / ".runtime-cache" / "reports" / "evidence-index"):
                continue
            metadata = read_runtime_metadata(item)
            if metadata is None:
                continue
            if str(metadata.get("source_run_id") or "").strip() == run_id:
                if item != manifest_log_path and _shared_log_file(item):
                    continue
                artifacts.append(item)
    return sorted(artifacts)


def main() -> int:
    contract = load_governance_json("evidence-contract.json")
    manifest_root = ROOT / str(contract.get("manifest_root") or ".runtime-cache/run/manifests")
    required_manifest_fields = [str(item) for item in contract.get("required_manifest_fields", [])]
    index_root = ROOT / str(
        contract.get("evidence_index", {}).get("root") or ".runtime-cache/reports/evidence-index"
    )
    errors: list[str] = []
    if not manifest_root.exists():
        print("[run-manifest-completeness] PASS (no manifests)")
        return 0

    for manifest_path in sorted(
        item
        for item in manifest_root.glob("*.json")
        if item.is_file() and not item.name.endswith(".meta.json")
    ):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            errors.append(f"{rel_path(manifest_path)}: missing run_id")
            continue
        for field in required_manifest_fields:
            if not str(payload.get(field) or "").strip():
                errors.append(
                    f"{rel_path(manifest_path)}: missing required manifest field `{field}`"
                )
        log_path_raw = str(payload.get("log_path") or "").strip()
        if log_path_raw:
            candidate = Path(log_path_raw)
            log_path = candidate if candidate.is_absolute() else ROOT / candidate
        else:
            log_path = None
        if log_path is None or not log_path.is_file():
            errors.append(f"{rel_path(manifest_path)}: log_path missing or file absent")
            continue
        log_metadata = read_runtime_metadata(log_path)
        if log_metadata is None:
            errors.append(f"{rel_path(manifest_path)}: log file missing runtime metadata")
        elif str(log_metadata.get("source_run_id") or "").strip() != run_id:
            errors.append(
                f"{rel_path(manifest_path)}: log metadata source_run_id does not match manifest run_id"
            )

        artifacts = _runtime_artifacts_for_run(run_id, manifest_log_path=log_path)
        run_complete = _log_has_complete_event(log_path, run_id)
        if not artifacts:
            if run_complete:
                errors.append(
                    f"{rel_path(manifest_path)}: no runtime artifacts found for run_id={run_id}"
                )
            continue

        index_path = index_root / f"{run_id}.json"
        if not index_path.is_file():
            if run_complete:
                errors.append(
                    f"{rel_path(manifest_path)}: missing evidence index for run_id={run_id}"
                )
            continue
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        indexed = (
            set(index_payload.get("logs", []))
            | set(index_payload.get("reports", []))
            | set(index_payload.get("evidence", []))
        )
        missing = [rel_path(path) for path in artifacts if rel_path(path) not in indexed]
        if missing and run_complete:
            errors.append(
                f"{rel_path(manifest_path)}: evidence index missing {len(missing)} runtime artifact(s); first={missing[0]}"
            )

    if errors:
        print("[run-manifest-completeness] FAIL")
        for item in errors[:50]:
            print(f"  - {item}")
        return 1

    print("[run-manifest-completeness] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
