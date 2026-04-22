from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(name: str, relative_path: str):
    root = Path(__file__).resolve().parents[3]
    module_path = root / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_declared_dirty_sets_reads_plan_sections() -> None:
    module = _load_module("report_worktree_status", "scripts/governance/report_worktree_status.py")
    plan_text = """
### Current Status

- current dirty sets:
  - in-scope: `README.md`, `docs/index.md`
  - out-of-scope existing drift: `config/governance/upstream-compat-matrix.json`

### Next Actions
"""

    in_scope, out_of_scope = module._extract_declared_dirty_sets(plan_text)

    assert in_scope == ["README.md", "docs/index.md"]
    assert out_of_scope == ["config/governance/upstream-compat-matrix.json"]


def test_latest_plan_path_prefers_ai_ledgers_before_agents_plans(tmp_path: Path) -> None:
    module = _load_module("report_worktree_status", "scripts/governance/report_worktree_status.py")
    module.ROOT = tmp_path
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agents" / "Plans").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                        "compatibility_paths": [".agents/Plans"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    authoritative = (
        tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers" / "authoritative-plan.md"
    )
    compatibility = tmp_path / ".agents" / "Plans" / "compat-plan.md"
    authoritative.write_text("authoritative", encoding="utf-8")
    compatibility.write_text("compatibility", encoding="utf-8")

    result = module._latest_plan_path("")

    assert result == authoritative.resolve()


def test_latest_plan_path_falls_back_to_agents_plans_when_ai_ledgers_empty(tmp_path: Path) -> None:
    module = _load_module("report_worktree_status", "scripts/governance/report_worktree_status.py")
    module.ROOT = tmp_path
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".agents" / "Plans").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                        "compatibility_paths": [".agents/Plans"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    compatibility = tmp_path / ".agents" / "Plans" / "compat-plan.md"
    compatibility.write_text("compatibility", encoding="utf-8")

    result = module._latest_plan_path("")

    assert result == compatibility.resolve()


def test_find_latest_plan_path_returns_none_when_no_plan_exists(tmp_path: Path) -> None:
    module = _load_module("report_worktree_status", "scripts/governance/report_worktree_status.py")
    module.ROOT = tmp_path
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                        "compatibility_paths": [".agents/Plans"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = module._find_latest_plan_path("")

    assert result is None


def test_build_report_fail_closes_when_plan_missing(tmp_path: Path) -> None:
    module = _load_module("report_worktree_status", "scripts/governance/report_worktree_status.py")
    module.ROOT = tmp_path
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                        "compatibility_paths": [".agents/Plans"],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    module.current_git_commit = lambda: "abc123"

    report = module._build_report(
        plan_path=None,
        declared_in_scope=[],
        declared_out_of_scope=[],
        dirty_files=["docs/runbook-local.md"],
    )

    assert report["status"] == "partial"
    assert report["plan_missing"] is True
    assert report["plan_path"] is None
    assert report["undeclared_dirty_files"] == ["docs/runbook-local.md"]
    assert report["summary"]["tracked_dirty_count"] == 1
    assert report["summary"]["undeclared_dirty_count"] == 1
    assert report["recommended_commit_groups"] == []


def test_local_private_ledger_migration_copies_and_then_skips_unchanged(tmp_path: Path) -> None:
    module = _load_module(
        "migrate_local_private_ledgers", "scripts/governance/migrate_local_private_ledgers.py"
    )
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    source_dir = tmp_path / ".agents" / "Plans"
    source_dir.mkdir(parents=True, exist_ok=True)
    plan = source_dir / "2026-03-27__plan.md"
    plan.write_text("plan body", encoding="utf-8")
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "name": "agent-execution-ledger",
                        "compatibility_paths": [".agents/Plans"],
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    first = module.migrate_ledgers(tmp_path)
    second = module.migrate_ledgers(tmp_path)

    target = tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers" / plan.name
    receipts = tmp_path / ".runtime-cache" / "evidence" / "ai-ledgers" / ".migration-receipts.json"
    target_meta = target.with_name(f"{target.name}.meta.json")
    receipts_meta = receipts.with_name(f"{receipts.name}.meta.json")
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "plan body"
    assert plan.is_file()
    assert receipts.is_file()
    assert target_meta.is_file()
    assert receipts_meta.is_file()
    assert first["summary"]["copied_count"] == 1
    assert second["summary"]["up_to_date_count"] == 1


def test_local_private_ledger_migration_check_passes_after_migration(tmp_path: Path) -> None:
    migrate_module = _load_module(
        "migrate_local_private_ledgers", "scripts/governance/migrate_local_private_ledgers.py"
    )
    check_module = _load_module(
        "check_local_private_ledger_migration",
        "scripts/governance/check_local_private_ledger_migration.py",
    )
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    source_dir = tmp_path / ".agents" / "Plans"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "2026-03-27__plan.md").write_text("plan body", encoding="utf-8")
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "name": "agent-execution-ledger",
                        "compatibility_paths": [".agents/Plans"],
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    migrate_module.migrate_ledgers(tmp_path)
    report = check_module.evaluate_local_private_ledger_migration(tmp_path)

    assert report["status"] == "pass"
    assert report["errors"] == []


def test_local_private_ledger_migration_check_fail_closes_when_authoritative_copy_missing(
    tmp_path: Path,
) -> None:
    check_module = _load_module(
        "check_local_private_ledger_migration",
        "scripts/governance/check_local_private_ledger_migration.py",
    )
    (tmp_path / "config" / "governance").mkdir(parents=True, exist_ok=True)
    source_dir = tmp_path / ".agents" / "Plans"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "2026-03-27__plan.md").write_text("plan body", encoding="utf-8")
    (tmp_path / "config" / "governance" / "local-private-ledgers.json").write_text(
        json.dumps(
            {
                "version": 1,
                "ledgers": [
                    {
                        "name": "agent-execution-ledger",
                        "compatibility_paths": [".agents/Plans"],
                        "authoritative_target_path": ".runtime-cache/evidence/ai-ledgers",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = check_module.evaluate_local_private_ledger_migration(tmp_path)

    assert report["status"] == "fail"
    assert any("authoritative target" in error for error in report["errors"])
