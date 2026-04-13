from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_module():
    module_path = _repo_root() / "scripts" / "governance" / "check_run_manifest_completeness.py"
    spec = importlib.util.spec_from_file_location(
        "check_run_manifest_completeness_test", module_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_metadata(path: Path, *, run_id: str) -> None:
    path.with_name(f"{path.name}.meta.json").write_text(
        json.dumps(
            {
                "version": 1,
                "artifact_path": path.as_posix(),
                "created_at": "2026-04-12T08:00:00Z",
                "source_entrypoint": "test",
                "source_run_id": run_id,
                "source_commit": "deadbeef",
                "verification_scope": "test-artifact",
                "freshness_window_hours": 24,
            }
        ),
        encoding="utf-8",
    )


def test_run_manifest_completeness_ignores_shared_multirun_logs_outside_manifest_log_path(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    run_id = "run-main"
    other_run_id = "run-other"

    manifest_root = tmp_path / ".runtime-cache" / "run" / "manifests"
    logs_root = tmp_path / ".runtime-cache" / "logs" / "governance"
    index_root = tmp_path / ".runtime-cache" / "reports" / "evidence-index"
    manifest_root.mkdir(parents=True)
    logs_root.mkdir(parents=True)
    index_root.mkdir(parents=True)

    manifest_log = logs_root / f"{run_id}.jsonl"
    manifest_log.write_text(
        json.dumps({"run_id": run_id, "event": "entrypoint_bootstrap"})
        + "\n"
        + json.dumps({"run_id": run_id, "event": "complete"})
        + "\n",
        encoding="utf-8",
    )
    _write_metadata(manifest_log, run_id=run_id)

    shared_log = logs_root / "strict-ci-entry.jsonl"
    shared_log.write_text(
        json.dumps({"run_id": run_id, "event": "strict_ci_entry_start"})
        + "\n"
        + json.dumps({"run_id": other_run_id, "event": "strict_ci_entry_start"})
        + "\n",
        encoding="utf-8",
    )
    _write_metadata(shared_log, run_id=run_id)

    manifest_path = manifest_root / f"{run_id}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": run_id,
                "entrypoint": "repo-side-strict-ci",
                "channel": "governance",
                "created_at": "2026-04-12T08:00:00Z",
                "repo_commit": "deadbeef",
                "env_profile": "unknown",
                "log_path": manifest_log.relative_to(tmp_path).as_posix(),
            }
        ),
        encoding="utf-8",
    )

    (index_root / f"{run_id}.json").write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": run_id,
                "logs": [manifest_log.relative_to(tmp_path).as_posix()],
                "reports": [],
                "evidence": [],
            }
        ),
        encoding="utf-8",
    )

    contract = {
        "manifest_root": ".runtime-cache/run/manifests",
        "required_manifest_fields": [
            "entrypoint",
            "channel",
            "created_at",
            "repo_commit",
            "env_profile",
            "log_path",
        ],
        "evidence_index": {"root": ".runtime-cache/reports/evidence-index"},
        "buckets": {
            "logs": {"path": ".runtime-cache/logs", "freshness_required": True},
            "reports": {"path": ".runtime-cache/reports", "freshness_required": True},
            "evidence": {"path": ".runtime-cache/evidence", "freshness_required": True},
        },
    }

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_governance_json", lambda _: contract)
    monkeypatch.setattr(module, "rel_path", lambda path: path.relative_to(tmp_path).as_posix())

    assert module.main() == 0


def test_run_manifest_completeness_fail_closes_when_manifest_disappears_during_audit(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_module()
    run_id = "run-vanished"

    manifest_root = tmp_path / ".runtime-cache" / "run" / "manifests"
    logs_root = tmp_path / ".runtime-cache" / "logs" / "governance"
    index_root = tmp_path / ".runtime-cache" / "reports" / "evidence-index"
    manifest_root.mkdir(parents=True)
    logs_root.mkdir(parents=True)
    index_root.mkdir(parents=True)

    manifest_log = logs_root / f"{run_id}.jsonl"
    manifest_log.write_text(
        json.dumps({"run_id": run_id, "event": "entrypoint_bootstrap"})
        + "\n"
        + json.dumps({"run_id": run_id, "event": "complete"})
        + "\n",
        encoding="utf-8",
    )
    _write_metadata(manifest_log, run_id=run_id)

    manifest_path = manifest_root / f"{run_id}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "run_id": run_id,
                "entrypoint": "repo-side-strict-ci",
                "channel": "governance",
                "created_at": "2026-04-12T08:00:00Z",
                "repo_commit": "deadbeef",
                "env_profile": "unknown",
                "log_path": manifest_log.relative_to(tmp_path).as_posix(),
            }
        ),
        encoding="utf-8",
    )

    contract = {
        "manifest_root": ".runtime-cache/run/manifests",
        "required_manifest_fields": [
            "entrypoint",
            "channel",
            "created_at",
            "repo_commit",
            "env_profile",
            "log_path",
        ],
        "evidence_index": {"root": ".runtime-cache/reports/evidence-index"},
        "buckets": {
            "logs": {"path": ".runtime-cache/logs", "freshness_required": True},
            "reports": {"path": ".runtime-cache/reports", "freshness_required": True},
            "evidence": {"path": ".runtime-cache/evidence", "freshness_required": True},
        },
    }

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_governance_json", lambda _: contract)
    monkeypatch.setattr(module, "rel_path", lambda path: path.relative_to(tmp_path).as_posix())

    original_read_text = Path.read_text

    def _flaky_read_text(path: Path, *args, **kwargs):
        if path == manifest_path:
            raise FileNotFoundError("manifest disappeared during audit")
        return original_read_text(path, *args, **kwargs)

    with patch.object(Path, "read_text", _flaky_read_text):
        assert module.main() == 1

    output = capsys.readouterr().out
    assert "[run-manifest-completeness] FAIL" in output
    assert "manifest file missing or unreadable during audit" in output
