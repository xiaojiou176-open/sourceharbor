#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "governance") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "governance"))

from common import (
    artifact_age_hours,
    ensure_runtime_metadata,
    is_runtime_metadata_managed_artifact,
    load_governance_json,
    parse_iso8601,
    rel_path,
    runtime_metadata_path,
    write_json_artifact,
    write_runtime_metadata,
)


def _iter_runtime_files(path: Path) -> list[Path]:
    return sorted(item for item in path.rglob("*") if is_runtime_metadata_managed_artifact(item))


def _infer_source_run_id(path: Path) -> str:
    if path.suffix == ".jsonl":
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                payload = json.loads(lines[-1])
                run_id = str(
                    payload.get("run_id")
                    or payload.get("test_run_id")
                    or payload.get("gate_run_id")
                    or ""
                ).strip()
                if run_id:
                    return run_id
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return f"legacy-{path.stem}"
    if path.suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return f"legacy-{path.stem}"
        if isinstance(payload, dict):
            for key in ("run_id", "last_verified_run_id"):
                value = str(payload.get(key) or "").strip()
                if value:
                    return value
        return f"legacy-{path.stem}"
    return f"legacy-{path.stem}"


def _default_created_at(name: str, path: Path) -> str:
    if name == "tmp":
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        datetime.fromtimestamp(path.stat().st_mtime, UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _runtime_age_hours(name: str, path: Path, metadata: dict[str, object]) -> float:
    if name == "tmp" and isinstance(metadata.get("created_at"), str):
        created_at = parse_iso8601(str(metadata["created_at"]))
        return max(0.0, (datetime.now(UTC) - created_at).total_seconds() / 3600.0)
    return artifact_age_hours(path, metadata)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize, audit, and optionally prune repo-side runtime cache artifacts."
    )
    parser.add_argument("--apply", action="store_true", help="Delete files that exceed ttl_days.")
    parser.add_argument(
        "--assert-clean",
        action="store_true",
        help="Fail when ttl/freshness/budget violations exist.",
    )
    parser.add_argument(
        "--normalize-only",
        action="store_true",
        help="Write missing metadata sidecars without applying retention.",
    )
    parser.add_argument(
        "--write-report", default=".runtime-cache/reports/governance/runtime-cache-maintenance.json"
    )
    parser.add_argument(
        "--subdir",
        action="append",
        dest="subdirs",
        help="Limit maintenance to selected runtime subdirectories.",
    )
    args = parser.parse_args()

    config = load_governance_json("runtime-outputs.json")
    runtime_root = ROOT / str(config["runtime_root"])
    selected = set(args.subdirs or config.get("subdirectories", {}).keys())
    report: dict[str, object] = {"version": 1, "subdirectories": {}, "status": "pass"}
    errors: list[str] = []
    allowed_subdirs = set(config.get("subdirectories", {}).keys())
    unknown_direct_children: list[str] = []

    if runtime_root.exists():
        for child in sorted(runtime_root.iterdir()):
            if child.name in allowed_subdirs:
                continue
            unknown_direct_children.append(rel_path(child))

    if args.apply and not args.normalize_only:
        for rel in unknown_direct_children:
            target = ROOT / rel
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        if unknown_direct_children:
            unknown_direct_children = []

    for name, subconfig in config.get("subdirectories", {}).items():
        if name not in selected:
            continue
        base = runtime_root / name
        base.mkdir(parents=True, exist_ok=True)
        files = _iter_runtime_files(base)
        ttl_hours = int(subconfig["ttl_days"]) * 24
        size_bytes = 0
        expired: list[str] = []
        stale: list[str] = []

        for item in files:
            try:
                created_at_value = _default_created_at(name, item)
            except FileNotFoundError:
                continue
            inferred_run_id = _infer_source_run_id(item)
            if name == "tmp":
                metadata = {
                    "created_at": created_at_value,
                    "source_run_id": inferred_run_id,
                    "freshness_window_hours": None,
                }
                try:
                    size_bytes += item.stat().st_size
                    age_hours = _runtime_age_hours(name, item, metadata)
                except FileNotFoundError:
                    continue
                if ttl_hours > 0 and age_hours > ttl_hours:
                    expired.append(rel_path(item))
                continue
            try:
                metadata = ensure_runtime_metadata(
                    item,
                    source_entrypoint="scripts/runtime/prune_runtime_cache.py",
                    verification_scope=f"runtime:{name}",
                    source_run_id=inferred_run_id,
                    freshness_window_hours=ttl_hours
                    if bool(subconfig["freshness_required"])
                    else None,
                    created_at=created_at_value,
                    extra={
                        "classification": subconfig["classification"],
                        "runtime_subdir": name,
                        "owner": subconfig["owner"],
                    },
                )
            except FileNotFoundError:
                continue
            if not str(metadata.get("source_run_id") or "").strip() and inferred_run_id:
                metadata = {
                    **metadata,
                    "source_run_id": inferred_run_id,
                }
                write_runtime_metadata(
                    item,
                    source_entrypoint=str(
                        metadata.get("source_entrypoint")
                        or "scripts/runtime/prune_runtime_cache.py"
                    ),
                    verification_scope=str(metadata.get("verification_scope") or f"runtime:{name}"),
                    source_run_id=inferred_run_id,
                    source_commit=str(metadata.get("source_commit") or ""),
                    freshness_window_hours=metadata.get("freshness_window_hours"),
                    created_at=str(metadata.get("created_at") or created_at_value),
                    extra={
                        key: value
                        for key, value in metadata.items()
                        if key
                        not in {
                            "version",
                            "artifact_path",
                            "created_at",
                            "source_entrypoint",
                            "source_run_id",
                            "source_commit",
                            "verification_scope",
                            "freshness_window_hours",
                        }
                    },
                )
                metadata = ensure_runtime_metadata(
                    item,
                    source_entrypoint="scripts/runtime/prune_runtime_cache.py",
                    verification_scope=f"runtime:{name}",
                    source_run_id=inferred_run_id,
                    freshness_window_hours=ttl_hours
                    if bool(subconfig["freshness_required"])
                    else None,
                    created_at=created_at_value,
                    extra={
                        "classification": subconfig["classification"],
                        "runtime_subdir": name,
                        "owner": subconfig["owner"],
                    },
                )
            try:
                size_bytes += item.stat().st_size
                age_hours = _runtime_age_hours(name, item, metadata)
            except FileNotFoundError:
                continue
            if ttl_hours > 0 and age_hours > ttl_hours:
                expired.append(rel_path(item))
            freshness_window_hours = metadata.get("freshness_window_hours")
            if (
                bool(subconfig["freshness_required"])
                and isinstance(freshness_window_hours, int)
                and age_hours > freshness_window_hours
            ):
                stale.append(rel_path(item))

        if args.apply and not args.normalize_only:
            removal_targets = list(expired)
            for rel in stale:
                if rel not in removal_targets:
                    removal_targets.append(rel)
            for rel in removal_targets:
                target = ROOT / rel
                meta = runtime_metadata_path(target)
                if target.exists():
                    target.unlink()
                if meta.exists():
                    meta.unlink()

        max_total_size_mb = int(subconfig["max_total_size_mb"])
        max_file_count = int(subconfig["max_file_count"])
        over_budget = size_bytes > max_total_size_mb * 1024 * 1024 or len(files) > max_file_count
        if over_budget:
            errors.append(
                f"runtime subdir `{name}` exceeded budget: size={size_bytes} bytes files={len(files)} "
                f"limits={max_total_size_mb}MB/{max_file_count}"
            )
        if args.assert_clean:
            if expired:
                errors.append(
                    f"runtime subdir `{name}` contains ttl-expired artifacts: {', '.join(expired[:10])}"
                )
            if stale:
                errors.append(
                    f"runtime subdir `{name}` contains stale artifacts: {', '.join(stale[:10])}"
                )

        report["subdirectories"][name] = {
            "file_count": len(files),
            "size_bytes": size_bytes,
            "expired_count": len(expired),
            "stale_count": len(stale),
            "ttl_days": int(subconfig["ttl_days"]),
            "max_total_size_mb": max_total_size_mb,
            "max_file_count": max_file_count,
            "classification": subconfig["classification"],
        }

    report["unknown_direct_children"] = unknown_direct_children
    if args.assert_clean and unknown_direct_children:
        errors.append(
            "runtime root contains undeclared direct children: "
            + ", ".join(unknown_direct_children[:10])
        )

    if errors:
        report["status"] = "fail"
        report["errors"] = errors

    report_path = ROOT / args.write_report
    write_json_artifact(
        report_path,
        report,
        source_entrypoint="scripts/runtime/prune_runtime_cache.py",
        verification_scope="runtime-cache-maintenance",
        source_run_id="runtime-cache-maintenance",
        freshness_window_hours=24,
        extra={"report_kind": "runtime-cache-maintenance"},
    )

    if errors:
        print("[runtime-cache-maintenance] FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    print("[runtime-cache-maintenance] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
