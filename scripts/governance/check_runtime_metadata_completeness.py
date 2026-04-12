#!/usr/bin/env python3
from __future__ import annotations

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
)

REQUIRED_METADATA_FIELDS = (
    "created_at",
    "source_entrypoint",
    "source_run_id",
    "source_commit",
    "verification_scope",
    "freshness_window_hours",
)


def main() -> int:
    config = load_governance_json("runtime-outputs.json")
    evidence_contract = load_governance_json("evidence-contract.json")
    runtime_root = ROOT / str(config["runtime_root"])
    required_metadata_fields = tuple(
        str(item) for item in evidence_contract.get("required_metadata_fields", [])
    )
    errors: list[str] = []

    for bucket_config in evidence_contract.get("buckets", {}).values():
        if not bool(bucket_config.get("freshness_required")):
            continue
        base = ROOT / str(bucket_config.get("path") or runtime_root)
        if not base.exists():
            continue

        for artifact in sorted(
            item
            for item in base.rglob("*")
            if is_runtime_metadata_managed_artifact(item)
        ):
            metadata = read_runtime_metadata(artifact)
            if metadata is None:
                errors.append(f"{artifact}: missing runtime metadata sidecar")
                continue
            for field in required_metadata_fields:
                value = metadata.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors.append(f"{artifact}: metadata field `{field}` is missing or blank")
            if not isinstance(metadata.get("freshness_window_hours"), int):
                errors.append(
                    f"{artifact}: metadata field `freshness_window_hours` must be an integer"
                )

    if errors:
        print("[runtime-metadata-completeness] FAIL")
        for item in errors[:20]:
            print(f"  - {item}")
        return 1

    print("[runtime-metadata-completeness] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
